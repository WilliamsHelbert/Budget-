"""HTTP API + static site for the tick replay.

Run from the tick-replay folder:
    uvicorn server.app:app --reload
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .store import Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TICK_DATA_DIR", ROOT / "data" / "ticks"))

# Candle sizes the UI offers, in seconds.
TIMEFRAMES = {1, 5, 15, 30, 60, 180, 300, 900, 1800, 3600, 14400}

store = Store(DATA_DIR)
app = FastAPI(title="Tick Replay")
app.add_middleware(GZipMiddleware, minimum_size=2048)


def _check_symbol(symbol: str) -> None:
    try:
        if not store.days(symbol):
            raise HTTPException(404, f"no data for {symbol}")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/symbols")
def symbols():
    return store.symbols()


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


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
