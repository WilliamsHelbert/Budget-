"""Backtest sessions: a named replay over a date range with a starting balance.

Each session remembers where the replay stopped, how much real time was spent in it,
how much market time was replayed, and every closed trade. Stored as one JSON file
(data/backtests.json) next to the tick data; writes are atomic.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

TRADE_FIELDS = ("symbol", "side", "qty", "entry_ts", "entry_px", "exit_ts", "exit_px", "pnl", "fees")


class BacktestStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    # ---- persistence ---------------------------------------------------------

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"sessions": []}

    def _save(self, db: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f)
        os.replace(tmp, self.path)

    def _find(self, db: dict, sid: str) -> dict:
        for s in db["sessions"]:
            if s["id"] == sid:
                return s
        raise KeyError(sid)

    # ---- api -----------------------------------------------------------------

    def list(self) -> list[dict]:
        with self._lock:
            return sorted(self._load()["sessions"], key=lambda s: s.get("updated", 0), reverse=True)

    def get(self, sid: str) -> dict:
        with self._lock:
            return self._find(self._load(), sid)

    def create(self, name: str, symbols: list[str], start_ts: int, end_ts: int,
               balance: float, fee_per_side: float) -> dict:
        now = int(time.time() * 1000)
        s = {
            "id": uuid.uuid4().hex[:12],
            "name": name.strip() or "Untitled session",
            "symbols": symbols,
            "start_ts": int(start_ts),
            "end_ts": int(end_ts),
            "balance": float(balance),
            "fee_per_side": float(fee_per_side),
            "current_ts": int(start_ts),
            "current_symbol": symbols[0],
            "time_spent_ms": 0,
            "replayed_ms": 0,
            "trades": [],
            "created": now,
            "updated": now,
        }
        with self._lock:
            db = self._load()
            db["sessions"].append(s)
            self._save(db)
        return s

    def update(self, sid: str, fields: dict) -> dict:
        allowed = {"name", "end_ts", "balance", "fee_per_side"}
        with self._lock:
            db = self._load()
            s = self._find(db, sid)
            for k, v in fields.items():
                if k in allowed and v is not None:
                    s[k] = v
            s["updated"] = int(time.time() * 1000)
            self._save(db)
            return s

    def progress(self, sid: str, current_ts: int | None, current_symbol: str | None,
                 add_time_ms: int, add_replayed_ms: int) -> dict:
        with self._lock:
            db = self._load()
            s = self._find(db, sid)
            if current_ts is not None:
                s["current_ts"] = int(min(max(current_ts, s["start_ts"]), s["end_ts"]))
            if current_symbol and current_symbol in s["symbols"]:
                s["current_symbol"] = current_symbol
            # clamp increments so a bad client can't inflate stats
            spent = int(min(max(add_time_ms, 0), 10 * 60_000))
            s["time_spent_ms"] += spent
            if spent:  # per calendar day (local), for the "time invested" chart
                day = time.strftime("%Y-%m-%d")
                by_day = s.setdefault("time_by_day", {})
                by_day[day] = by_day.get(day, 0) + spent
            s["replayed_ms"] += int(min(max(add_replayed_ms, 0), 7 * 86_400_000))
            s["updated"] = int(time.time() * 1000)
            self._save(db)
            return s

    def add_trade(self, sid: str, trade: dict) -> dict:
        t = {k: trade.get(k) for k in TRADE_FIELDS}
        t["id"] = uuid.uuid4().hex[:10]
        with self._lock:
            db = self._load()
            s = self._find(db, sid)
            s["trades"].append(t)
            s["updated"] = int(time.time() * 1000)
            self._save(db)
            return t

    def delete(self, sid: str) -> None:
        with self._lock:
            db = self._load()
            before = len(db["sessions"])
            db["sessions"] = [s for s in db["sessions"] if s["id"] != sid]
            if len(db["sessions"]) == before:
                raise KeyError(sid)
            self._save(db)

    def duplicate(self, sid: str) -> dict:
        s = self.get(sid)
        return self.create(s["name"] + " (copy)", s["symbols"], s["start_ts"], s["end_ts"],
                           s["balance"], s.get("fee_per_side", 0))
