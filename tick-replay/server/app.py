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

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from tools.import_ticks import read_any, write_days

from .store import Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TICK_DATA_DIR", ROOT / "data" / "ticks"))
WEB_DIR = Path(os.environ.get("TICK_WEB_DIR", ROOT / "web"))

# Candle sizes the UI offers, in seconds.
TIMEFRAMES = {1, 5, 15, 30, 60, 180, 300, 900, 1800, 3600, 14400}

store = Store(DATA_DIR)
app = FastAPI(title="Tick Replay")
app.add_middleware(GZipMiddleware, minimum_size=2048)

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
    import numpy as np

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
                ts, px, sz = read_any(path, tz)
            except SystemExit as e:  # the CLI reader reports bad files this way
                raise HTTPException(400, str(e))
            except Exception as e:
                raise HTTPException(400, f"{f.filename}: could not read file ({e})")
            ok = ~np.isnan(px) & (px > 0)
            parts.append((ts[ok], px[ok], sz[ok]))
            report.append({"file": f.filename, "ticks": int(ok.sum())})

    ts = np.concatenate([p[0] for p in parts])
    if not len(ts):
        raise HTTPException(400, "no ticks found in the uploaded files")
    px = np.concatenate([p[1] for p in parts])
    sz = np.concatenate([p[2] for p in parts])
    days = write_days(DATA_DIR, symbol, ts, px, sz, replace=True)
    store.invalidate()
    return {"symbol": symbol, "files": report, "ticks": int(len(ts)), "days": days,
            "first_ts": int(ts.min()), "last_ts": int(ts.max())}


@app.delete("/api/symbols/{symbol}")
def delete_symbol(symbol: str):
    _check_symbol(symbol)
    shutil.rmtree(store._sym_dir(symbol))
    store.invalidate()
    return {"deleted": symbol}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
