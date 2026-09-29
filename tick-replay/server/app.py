"""HTTP API + static site for the tick replay.

Run from the tick-replay folder:
    python -m uvicorn server.app:app --reload
or start the desktop program with `python desktop.py`.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from tools.import_ticks import clean, concat, read_ticks, write_days

from .backtests import BacktestStore
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TICK_DATA_DIR", ROOT / "data" / "ticks"))
WEB_DIR = Path(os.environ.get("TICK_WEB_DIR", ROOT / "web"))

# Candle sizes the UI offers, in seconds.
TIMEFRAMES = {1, 5, 15, 30, 60, 180, 300, 900, 1800, 3600, 14400}

store = Store(DATA_DIR)
backtests = BacktestStore(Path(os.environ.get("TICK_BACKTESTS", DATA_DIR.parent / "backtests.json")))
app = FastAPI(title="Tick Replay")
app.add_middleware(GZipMiddleware, minimum_size=2048)

@app.middleware("http")
async def no_stale_pages(request: Request, call_next):
    # The app window keeps its browser cache between program versions; make it revalidate
    # the page files every time so an update is never hidden behind old JavaScript.
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


# Last time an open page checked in; the desktop launcher quits when pages stop pinging.
last_ping = {"t": 0.0}


def _check_symbol(symbol: str) -> None:
    try:
        if not store.days(symbol):
            raise HTTPException(404, f"no data for {symbol}")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/ping")
def ping():
    last_ping["t"] = time.monotonic()
    return {"ok": True}


@app.get("/api/symbols")
def symbols():
    return store.symbols()


@app.get("/api/days")
def days(symbol: str):
    """Regular-hours summary per trading day, newest first."""
    _check_symbol(symbol)
    return store.sessions(symbol)[::-1]


# ---- backtest sessions -------------------------------------------------------

class Rules(BaseModel):
    """Prop-firm style evaluation rules, all in dollars. 0 or missing = rule off."""
    target: float = Field(0, ge=0, le=1e8)
    max_dd: float = Field(0, ge=0, le=1e8)       # trailing drawdown from the equity high
    daily_loss: float = Field(0, ge=0, le=1e8)   # per trading day (18:00 New York to 18:00)


class RuleState(BaseModel):
    peak: float
    status: str = Field("active", pattern="^(active|passed|failed)$")
    reason: str | None = Field(None, max_length=200)


class NewBacktest(BaseModel):
    name: str = Field("", max_length=80)
    symbols: list[str] = Field(..., min_length=1, max_length=4)
    start_ts: int
    end_ts: int
    balance: float = Field(50_000, gt=0, le=1e9)
    fee_per_side: float = Field(0, ge=0, le=100)
    rules: Rules | None = None


class EditBacktest(BaseModel):
    name: str | None = Field(None, max_length=80)
    end_ts: int | None = None
    balance: float | None = Field(None, gt=0, le=1e9)
    fee_per_side: float | None = Field(None, ge=0, le=100)
    rules: Rules | None | bool = False   # False = leave unchanged, None = remove


class Progress(BaseModel):
    current_ts: int | None = None
    current_symbol: str | None = None
    add_time_ms: int = 0
    add_replayed_ms: int = 0
    rule_state: RuleState | None = None


class Trade(BaseModel):
    symbol: str
    side: int = Field(..., description="+1 long, -1 short")
    qty: int = Field(..., gt=0)
    entry_ts: int
    entry_px: float
    exit_ts: int
    exit_px: float
    pnl: float
    fees: float = 0
    mae: float | None = None   # worst excursion against the trade, in points
    mfe: float | None = None   # best excursion in favour, in points
    setup: str | None = Field(None, max_length=40)
    note: str | None = Field(None, max_length=1000)


class TradeJournal(BaseModel):
    setup: str | None = Field(None, max_length=40)
    note: str | None = Field(None, max_length=1000)


def _rules(r: Rules | None) -> dict | None:
    if r is None or not (r.target or r.max_dd or r.daily_loss):
        return None
    return r.model_dump()


def _bt(sid: str) -> dict:
    try:
        return backtests.get(sid)
    except KeyError:
        raise HTTPException(404, "session not found")


@app.get("/api/backtests")
def list_backtests():
    return backtests.list()


@app.post("/api/backtests")
def create_backtest(body: NewBacktest):
    syms = [x.strip().upper() for x in body.symbols]
    for x in syms:
        _check_symbol(x)
    if body.end_ts <= body.start_ts:
        raise HTTPException(400, "end must be after start")
    return backtests.create(body.name, syms, body.start_ts, body.end_ts, body.balance, body.fee_per_side,
                            _rules(body.rules))


@app.get("/api/backtests/{sid}")
def get_backtest(sid: str):
    return _bt(sid)


@app.patch("/api/backtests/{sid}")
def edit_backtest(sid: str, body: EditBacktest):
    _bt(sid)
    fields = body.model_dump(exclude={"rules"})
    if body.rules is not False:
        fields["rules"] = _rules(body.rules) if body.rules is not True else False
    return backtests.update(sid, fields)


@app.post("/api/backtests/{sid}/progress")
async def backtest_progress(sid: str, request: Request):
    # accepts text/plain too, so the page can use navigator.sendBeacon when it closes
    try:
        body = Progress.model_validate_json(await request.body())
    except ValueError as e:
        raise HTTPException(422, str(e))
    _bt(sid)
    s = backtests.progress(sid, body.current_ts, body.current_symbol, body.add_time_ms, body.add_replayed_ms,
                            body.rule_state.model_dump() if body.rule_state else None)
    return {"ok": True, "current_ts": s["current_ts"], "rule_state": s.get("rule_state")}


@app.post("/api/backtests/{sid}/trades")
def backtest_trade(sid: str, body: Trade):
    _bt(sid)
    return backtests.add_trade(sid, body.model_dump())


@app.patch("/api/backtests/{sid}/trades/{tid}")
def journal_trade(sid: str, tid: str, body: TradeJournal):
    _bt(sid)
    try:
        return backtests.edit_trade(sid, tid, body.model_dump())
    except KeyError:
        raise HTTPException(404, "trade not found")


@app.post("/api/backtests/{sid}/duplicate")
def duplicate_backtest(sid: str):
    _bt(sid)
    return backtests.duplicate(sid)


@app.delete("/api/backtests/{sid}")
def delete_backtest(sid: str):
    _bt(sid)
    backtests.delete(sid)
    return {"deleted": sid}


@app.get("/api/candles")
def candles(
    symbol: str,
    tf: int = Query(60, description="candle size in seconds"),
    end: int = Query(..., description="replay time, ms since epoch UTC (inclusive)"),
    count: int = Query(500, ge=1, le=5000),
):
    if tf not in TIMEFRAMES:
        raise HTTPException(400, f"tf must be one of {sorted(TIMEFRAMES)}")
    _check_symbol(symbol)
    return store.candles(symbol, tf, end, count)


@app.get("/api/ticks")
def ticks(
    symbol: str,
    after: int = Query(..., description="exclusive, ms since epoch UTC"),
    until: int = Query(..., description="inclusive, ms since epoch UTC"),
    limit: int = Query(200_000, ge=1, le=1_000_000),
):
    if until < after:
        raise HTTPException(400, "until must be >= after")
    _check_symbol(symbol)
    return store.ticks(symbol, after, until, limit)


@app.post("/api/import")
def import_ticks(
    files: list[UploadFile] = File(...),
    symbol: str = Form(...),
    tz: str = Form("UTC"),
):
    """Import uploaded tick files. Days they cover replace what is stored for those days."""
    symbol = symbol.strip().upper()
    try:
        store.days(symbol)  # validates the name
    except ValueError as e:
        raise HTTPException(400, str(e))

    parts, report = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for f in files:
            path = Path(tmp) / Path(f.filename or "upload.csv").name
            with open(path, "wb") as out:
                shutil.copyfileobj(f.file, out, 4 * 1024 * 1024)
            try:
                t = clean(read_ticks(path, tz))
            except SystemExit as e:  # the CLI reader reports bad files this way
                raise HTTPException(400, str(e))
            except Exception as e:
                raise HTTPException(400, f"{f.filename}: could not read file ({e})")
            parts.append(t)
            report.append({"file": f.filename, "ticks": int(len(t["ts"]))})

    t = concat(parts)
    ts = t["ts"]
    if not len(ts):
        raise HTTPException(400, "no ticks found in the uploaded files")
    days = write_days(DATA_DIR, symbol, ts, t["price"], t["size"], replace=True,
                      bid=t["bid"], ask=t["ask"], side=t["side"])
    store.invalidate()
    has_quotes = bool((~np.isnan(t["bid"])).any())
    return {"symbol": symbol, "files": report, "ticks": int(len(ts)), "days": days,
            "first_ts": int(ts.min()), "last_ts": int(ts.max()), "has_quotes": has_quotes}


@app.delete("/api/symbols/{symbol}")
def delete_symbol(symbol: str):
    _check_symbol(symbol)
    shutil.rmtree(store._sym_dir(symbol))
    store.invalidate()
    return {"deleted": symbol}


@app.get("/version.json")
def version():
    """Build stamp written by the Windows build; "dev" when running from source."""
    import json

    try:
        return json.loads((WEB_DIR / "version.json").read_text())
    except (OSError, ValueError):
        return {"version": "dev"}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
