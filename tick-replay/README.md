# Tick Replay

Replays historical NQ / ES futures ticks at millisecond resolution in a TradingView-style chart.
Each tick has a millisecond timestamp, and the price stays on screen until the next tick's timestamp is reached.
Candles form tick by tick, just like a live market, and you can place simulated trades while it plays.

## Quick start

```bash
cd tick-replay
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python tools/make_sample.py          # fake NQ + ES ticks so you can try it right away
uvicorn server.app:app --reload      # then open http://localhost:8000
```

## Importing your real tick data

```bash
python tools/import_ticks.py --symbol NQ path/to/NQ_ticks.csv --tz America/New_York
python tools/import_ticks.py --symbol ES path/to/ES_*.txt --tz America/New_York
```

Formats the importer recognises:

| Source | Example line |
|---|---|
| NinjaTrader tick export (`.txt`) | `20240305 093000 1230000;18123.25;18123;18123.25;2` |
| Databento trades CSV | `ts_event,...,price,size` (ns timestamps, fixed-point prices handled) |
| Sierra Chart export | `Date, Time, ..., Last, Volume` |
| Any CSV with a header | a `timestamp`/`time`/`ts` column, a `price`/`last` column, and optionally `size`/`volume` |

* Numeric timestamps are read as epoch UTC. The importer works out whether they're in seconds, ms, µs or ns.
* Text timestamps without a timezone are read in `--tz`, which defaults to **UTC**. NinjaTrader exports use your PC's timezone.
* After importing, check the printed first and last times (UTC). If they're off by a few hours, the `--tz` was wrong. Re-import with `--replace`.
* Importing the same days again merges the ticks into the existing data. Use `--replace` to overwrite instead.

Data is stored as one Parquet file per UTC day in `data/ticks/<SYMBOL>/<YYYY-MM-DD>.parquet`
with the columns `ts` (int64 ms UTC), `price` and `size`. The `data/` folder is git-ignored.
Set `TICK_DATA_DIR` to keep the data somewhere else.

## Using the replay

| Control | What it does |
|---|---|
| Date/time + **Go** | Jump to that moment (New York time). Everything before it shows as history. |
| ▶ / **Space** | Play or pause |
| **+1 tick** / **→** | Advance exactly one tick |
| **+1 bar** / **Shift+→** | Advance to the close of the next candle |
| Speed | 0.25x to 3600x real time |
| skip gaps | Jumps over closed hours and quiet stretches instead of waiting through them |
| 1s … 4h | Candle timeframe. The current candle stays partial, as it was at the replay time. |
| **B** / **S** / **F** | Buy, sell, or flatten at the last traded price (NQ $20/pt, ES $50/pt) |

## How it works

* `server/store.py` loads day files, cuts tick windows (`after < ts <= until`), and builds candles
  from 1-second bars plus the raw ticks of the current second, so the last candle is exactly partial.
* `server/app.py` has a FastAPI backend with `/api/symbols`, `/api/candles` and `/api/ticks`, and it also serves `web/`.
* `web/app.js` runs the replay clock in the browser. It fetches ticks in chunks ahead of the clock.
  On every frame it applies all ticks with `ts <= clock` to the forming candle, using
  [Lightweight Charts](https://github.com/tradingview/lightweight-charts) (Apache-2.0, bundled in `web/vendor/`).

```bash
python -m pytest tests
```

## Known limits / next steps

* Market orders fill at the last trade, without bid/ask or slippage. Limit and stop orders, commissions, and a trade log with stats come next.
* The chart shows New York time using one UTC offset per load, so history across a DST change is off by one hour.
* Contract rolls aren't handled. Import one continuous series per symbol.
