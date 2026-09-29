"""Tick storage and aggregation.

Layout on disk:  <data_dir>/<SYMBOL>/<YYYY-MM-DD>.parquet   (one file per UTC day)
Columns:         ts (int64, ms since epoch, UTC), price (float64), size (int32)

Ticks inside a file are sorted by ts; several ticks may share the same ms and
their file order is the order they traded in.
"""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from pathlib import Path

from zoneinfo import ZoneInfo

import numpy as np

from tools.import_ticks import read_day_file

NY = ZoneInfo("America/New_York")

DAY_MS = 86_400_000
SYMBOL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")

# Contract specs used by the UI for P&L. Unknown symbols fall back to DEFAULT_SPEC.
SPECS = {
    "NQ": {"tick_size": 0.25, "point_value": 20.0},
    "MNQ": {"tick_size": 0.25, "point_value": 2.0},
    "ES": {"tick_size": 0.25, "point_value": 50.0},
    "MES": {"tick_size": 0.25, "point_value": 5.0},
}
DEFAULT_SPEC = {"tick_size": 0.01, "point_value": 1.0}


def spec_for(symbol: str) -> dict:
    """Contract spec by root symbol, so "NQ-DEMO" or "NQH4" use the NQ spec."""
    s = symbol.upper()
    for root in sorted(SPECS, key=len, reverse=True):  # MNQ before NQ
        if s.startswith(root):
            return SPECS[root]
    return DEFAULT_SPEC

# How far back /candles may walk looking for history (covers long weekends/holidays).
MAX_LOOKBACK_DAYS = 120


def day_of(ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def day_start_ms(day: dt.date) -> int:
    return int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


class Ticks:
    """Trades of one day. bid/ask are the best quotes just before each trade (NaN if unknown),
    side is the aggressor (+1 buyer, -1 seller, 0 unknown)."""

    __slots__ = ("ts", "price", "size", "bid", "ask", "side")

    def __init__(self, ts, price, size, bid=None, ask=None, side=None):
        n = len(ts)
        self.ts, self.price, self.size = ts, price, size
        self.bid = np.full(n, np.nan) if bid is None else bid
        self.ask = np.full(n, np.nan) if ask is None else ask
        self.side = np.zeros(n, np.int8) if side is None else side

    def __len__(self) -> int:
        return len(self.ts)

    def slice(self, i: int, j: int) -> "Ticks":
        return Ticks(*(getattr(self, f)[i:j] for f in self.__slots__))

    @property
    def has_quotes(self) -> bool:
        return bool(len(self) and not np.isnan(self.bid).all())


EMPTY_TICKS = Ticks(np.empty(0, np.int64), np.empty(0, np.float64), np.empty(0, np.int32))


class Bars:
    """OHLCV bars keyed by bucket start in seconds."""

    __slots__ = ("t", "o", "h", "l", "c", "v")

    def __init__(self, t, o, h, l, c, v):
        self.t, self.o, self.h, self.l, self.c, self.v = t, o, h, l, c, v

    def __len__(self) -> int:
        return len(self.t)

    @staticmethod
    def concat(parts: list["Bars"]) -> "Bars":
        parts = [p for p in parts if len(p)]
        if not parts:
            return Bars(*(np.empty(0, np.int64),) + tuple(np.empty(0) for _ in range(5)))
        return Bars(*(np.concatenate([getattr(p, f) for p in parts]) for f in Bars.__slots__))


def ticks_to_bars(ticks: Ticks, tf_sec: int) -> Bars:
    """Aggregate ticks into tf_sec buckets."""
    return _group(ticks.ts // 1000 // tf_sec * tf_sec, ticks.price, ticks.price, ticks.price, ticks.price,
                  ticks.size.astype(np.float64))


def rebucket(bars: Bars, tf_sec: int) -> Bars:
    """Aggregate finer bars into tf_sec buckets."""
    return _group(bars.t // tf_sec * tf_sec, bars.o, bars.h, bars.l, bars.c, bars.v)


def _group(keys, o, h, l, c, v) -> Bars:
    if len(keys) == 0:
        return Bars.concat([])
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    ends = np.r_[starts[1:], len(keys)] - 1
    return Bars(
        keys[starts],
        o[starts],
        np.maximum.reduceat(h, starts),
        np.minimum.reduceat(l, starts),
        c[ends],
        np.add.reduceat(v, starts),
    )


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        # Bound the per-instance caches (a tick day can be tens of MB, a 1s-bar day ~2 MB).
        self._day_ticks = lru_cache(maxsize=6)(self._load_day)
        self._day_bars = lru_cache(maxsize=256)(self._bars_1s_for_day)
        self._session = lru_cache(maxsize=1024)(self._session_for_day)

    def invalidate(self) -> None:
        """Forget cached day data after files on disk changed."""
        self._day_ticks.cache_clear()
        self._day_bars.cache_clear()
        self._session.cache_clear()

    # ---- catalog -------------------------------------------------------------

    def symbols(self) -> list[dict]:
        out = []
        if not self.data_dir.exists():
            return out
        for d in sorted(p for p in self.data_dir.iterdir() if p.is_dir()):
            days = self.days(d.name)
            if not days:
                continue
            first = self.day_ticks(d.name, days[0])
            last = self.day_ticks(d.name, days[-1])
            out.append({
                "symbol": d.name,
                "days": [x.isoformat() for x in days],
                "first_ts": int(first.ts[0]) if len(first) else None,
                "last_ts": int(last.ts[-1]) if len(last) else None,
                "quotes": last.has_quotes,
                **spec_for(d.name),
            })
        return out

    def days(self, symbol: str) -> list[dt.date]:
        sym_dir = self._sym_dir(symbol)
        if not sym_dir.is_dir():
            return []
        out = []
        for p in sym_dir.glob("*.parquet"):
            try:
                out.append(dt.date.fromisoformat(p.stem))
            except ValueError:
                continue
        return sorted(out)

    def _sym_dir(self, symbol: str) -> Path:
        if not SYMBOL_RE.fullmatch(symbol or ""):
            raise ValueError(f"bad symbol {symbol!r} (use letters, digits, - or _)")
        return self.data_dir / symbol

    # ---- raw ticks -----------------------------------------------------------

    def _load_day(self, symbol: str, day: dt.date) -> Ticks:
        path = self._sym_dir(symbol) / f"{day.isoformat()}.parquet"
        if not path.exists():
            return EMPTY_TICKS
        c = read_day_file(path)
        return Ticks(c["ts"], c["price"], c["size"], c["bid"], c["ask"], c["side"])

    def day_ticks(self, symbol: str, day: dt.date) -> Ticks:
        return self._day_ticks(symbol, day)

    def ticks(self, symbol: str, after: int, until: int, limit: int) -> dict:
        """Ticks with after < ts <= until, at most `limit` of them.

        When the limit cuts the window short, the cut is moved back to a whole
        millisecond so that the next request (after=<returned covered_until>)
        never skips ticks sharing that millisecond.
        """
        days = self.days(symbol)
        parts: list[Ticks] = []
        n = 0
        covered = until
        for day in days:
            d0 = day_start_ms(day)
            if d0 + DAY_MS <= after or d0 > until:
                continue
            tk = self.day_ticks(symbol, day)
            i = np.searchsorted(tk.ts, after, side="right")
            j = np.searchsorted(tk.ts, until, side="right")
            if i >= j:
                continue
            if n + (j - i) > limit:
                j = i + (limit - n)
                cut_ms = tk.ts[j - 1]
                # drop the partially included millisecond, unless it is all we have
                k = np.searchsorted(tk.ts, cut_ms, side="left")
                if k > i or n > 0:
                    j = max(k, i)
                    covered = int(cut_ms) - 1
                else:
                    j = np.searchsorted(tk.ts, cut_ms, side="right")
                    covered = int(cut_ms)
                parts.append(tk.slice(i, j))
                n += j - i
                break
            parts.append(tk.slice(i, j))
            n += j - i

        cat = lambda f: np.concatenate([getattr(p, f) for p in parts]) if parts else getattr(EMPTY_TICKS, f)  # noqa: E731
        bid, ask = cat("bid"), cat("ask")
        quotes = bool(len(bid) and not np.isnan(bid).all())
        return {
            "covered_until": int(covered),
            "ts": cat("ts").tolist(),
            "price": cat("price").tolist(),
            "size": cat("size").tolist(),
            "side": cat("side").tolist(),
            # best bid/ask before each trade; 0 where unknown (JSON has no NaN)
            "bid": np.nan_to_num(bid, nan=0.0).tolist() if quotes else None,
            "ask": np.nan_to_num(ask, nan=0.0).tolist() if quotes else None,
            # first tick after the covered window (lets the client jump over closed hours)
            "next_ts": self.next_tick_after(symbol, int(covered)) if n == 0 else None,
        }

    def next_tick_after(self, symbol: str, ms: int) -> int | None:
        for day in self.days(symbol):
            if day_start_ms(day) + DAY_MS <= ms:
                continue
            tk = self.day_ticks(symbol, day)
            i = np.searchsorted(tk.ts, ms, side="right")
            if i < len(tk):
                return int(tk.ts[i])
        return None

    # ---- candles -------------------------------------------------------------

    def _bars_1s_for_day(self, symbol: str, day: dt.date) -> Bars:
        # read directly (not through the tick cache) so history scans don't evict replay days
        return ticks_to_bars(self._load_day(symbol, day), 1)

    def candles(self, symbol: str, tf_sec: int, end: int, count: int) -> list[dict]:
        """The last `count` candles built from ticks with ts <= end.

        The final candle is partial: exactly what a live chart would have shown at `end`.
        """
        end_sec = end // 1000
        days = [d for d in self.days(symbol) if day_start_ms(d) <= end]
        parts: list[Bars] = []

        # partial current second, straight from ticks
        tk = self.day_ticks(symbol, day_of(end)) if days else EMPTY_TICKS
        i = np.searchsorted(tk.ts, end_sec * 1000, side="left")
        j = np.searchsorted(tk.ts, end, side="right")
        if j > i:
            parts.append(ticks_to_bars(tk.slice(i, j), 1))

        # whole seconds before that, walking back day by day until we have enough buckets
        have = 0
        oldest_needed = day_of(end) - dt.timedelta(days=MAX_LOOKBACK_DAYS)
        for day in reversed(days):
            if day < oldest_needed or have >= count:
                break
            b = self._day_bars(symbol, day)
            k = np.searchsorted(b.t, end_sec, side="left")
            if k == 0:
                continue
            b = Bars(*(getattr(b, f)[:k] for f in Bars.__slots__))
            parts.insert(0, b)
            have += len(np.unique(b.t // tf_sec))

        bars = rebucket(Bars.concat(parts), tf_sec)
        n = len(bars)
        s = max(0, n - count)
        return [
            {"time": int(bars.t[x]), "open": float(bars.o[x]), "high": float(bars.h[x]),
             "low": float(bars.l[x]), "close": float(bars.c[x]), "volume": float(bars.v[x])}
            for x in range(s, n)
        ]

    # ---- sessions ------------------------------------------------------------

    def _session_for_day(self, symbol: str, day: dt.date) -> dict | None:
        """Regular-hours (09:30-16:00 New York) summary of one weekday."""
        if day.weekday() >= 5:
            return None
        o = int(dt.datetime(day.year, day.month, day.day, 9, 30, tzinfo=NY).timestamp())
        c = int(dt.datetime(day.year, day.month, day.day, 16, 0, tzinfo=NY).timestamp())
        b = self._day_bars(symbol, day)
        i, j = np.searchsorted(b.t, o), np.searchsorted(b.t, c)
        if i >= j:
            return None
        t, hi, lo, cl, v = b.t[i:j], b.h[i:j], b.l[i:j], b.c[i:j], b.v[i:j]
        k5 = np.searchsorted(t, o + 300)
        spark = rebucket(Bars(t, b.o[i:j], hi, lo, cl, v), 300)
        # previous close for the day's change: last trade before the open
        prev = float(b.c[i - 1]) if i > 0 else float(b.o[i])
        return {
            "date": day.isoformat(),
            "open_ts": o * 1000,
            "open": float(b.o[i]), "high": float(hi.max()), "low": float(lo.min()), "close": float(cl[-1]),
            "volume": int(v.sum()),
            "pre_open": prev,
            "range_5m": float(hi[:k5].max() - lo[:k5].min()) if k5 else 0.0,
            "spark": [round(float(x), 2) for x in spark.c],
        }

    def sessions(self, symbol: str) -> list[dict]:
        out = [self._session(symbol, d) for d in self.days(symbol)]
        return [x for x in out if x]
