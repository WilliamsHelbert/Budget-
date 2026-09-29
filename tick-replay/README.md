# Tick Replay

Replays historical NQ / ES futures ticks at millisecond resolution in a TradingView-style chart.
Each tick has a millisecond timestamp, and the price stays on screen until the next tick's timestamp is reached.
Candles form tick by tick, just like a live market, and you can place simulated trades while it plays.

## Install the program (Windows)

1. Go to the repo's **Releases** page and open **Tick Replay (latest build)**
   (or: Actions → *Tick Replay – Windows program* → latest run → *TickReplay-windows*).
2. Download **TickReplay-windows.zip** and unzip it somewhere, e.g. `Documents\TickReplay`.
3. Double-click **TickReplay.exe**. The first time, Windows SmartScreen may say "Windows protected your PC".
   Click **More info → Run anyway** (the program isn't code-signed).

The program opens in its own window (it uses Microsoft Edge, which is built into Windows, in app mode).
Close the window to quit. Your data is stored in the `data` folder next to `TickReplay.exe`.
Demo data (`NQ-DEMO`, `ES-DEMO`) is created on first start. Import your own ticks from the start page.
Once you have real data, you can delete the demo data there too.

A new build is made automatically every time the `tick-replay` folder changes on GitHub.

## Run from source (developers)

```bash
cd tick-replay
pip install -r requirements.txt
python desktop.py                    # same as the program: own window, demo data, quits when closed
# or the plain web server:
python tools/make_sample.py && python -m uvicorn server.app:app   # http://localhost:8000
```

Build the .exe yourself on Windows: `pip install pyinstaller` and then `pyinstaller --noconfirm TickReplay.spec`.

## Importing your real tick data

In the program, use **Import tick data** on the start page. Choose the symbol and the time zone the file was
saved in, then pick the files. From the command line:

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

* **Databento:** choose Encoding **CSV** (plain or zstd-compressed). The **TBBO** schema is best: the best bid/ask
  before every trade is stored, so market orders fill at the ask (buy) or bid (sell) and Time & Sales shows the aggressor.
  Parent downloads like `NQ.FUT` hold every expiry and spread; only the most-traded contract of each day is kept
  (the same selection as `NQ.v.0`).
* Numeric timestamps are read as epoch UTC. The importer works out whether they're in seconds, ms, µs or ns.
* Text timestamps without a timezone are read in `--tz`, which defaults to **UTC**. NinjaTrader exports use your PC's timezone.
* After importing, check the printed first and last times (UTC). If they're off by a few hours, the `--tz` was wrong. Re-import with `--replace`.
* Importing the same days again merges the ticks into the existing data. Use `--replace` to overwrite instead.

Data is stored as one Parquet file per UTC day in `data/ticks/<SYMBOL>/<YYYY-MM-DD>.parquet`
with the columns `ts` (int64 ms UTC), `price` and `size`. The `data/` folder is git-ignored.
Set `TICK_DATA_DIR` to keep the data somewhere else.

## The workspace

The start page is a workspace with a sidebar:

| Page | What's there |
|---|---|
| **Dashboard** | Time invested, historical time replayed, trades taken (long/short), win rate, net P&L, profit factor; time invested per month, win rate and P&L by month, trades by symbol; a live 1x preview of the latest open; recent sessions |
| **Sessions** | Backtest sessions (name, symbols, date range, starting balance, commission). ▶ continues exactly where you stopped. Edit, duplicate (fresh start), summary, delete |
| **Trades** | Every closed trade across sessions, filter by session, export CSV |
| **Analytics** | Equity curve, expectancy, profit factor, max drawdown, P&L by weekday and by entry hour (New York), long vs short |
| **Data** | Your tick data (BID/ASK or TRADES badge) and drag & drop import |

Inside a session the chart shows the session name and your balance. Closed trades are saved immediately,
and progress (replay position, time spent, market time replayed) is saved every 10 seconds and when you leave.
Sessions are stored in `data/backtests.json`.


The start page (`/`) lists your data. Pick a symbol and session and press **🔔 Market Open**.
The chart opens at 09:25 New York with the whole overnight session as history and plays **live at 1x,
tick by tick**, so you sit through the last minutes before the bell and trade the open as it happens.
A countdown shows the time left to 09:30. The same button is on the chart page and uses the date in the date field.

| Control | What it does |
|---|---|
| Date/time + **Go** | Jump to that moment (New York time). Everything before it shows as history. |
| ▶ / **Space** | Play or pause |
| **+1 tick** / **→** | Advance exactly one tick |
| **+1 bar** / **Shift+→** | Advance to the close of the next candle |
| Speed | 0.25x to 3600x real time |
| skip closed | Jumps over closed-market periods (no trades for 5+ minutes). Shorter quiet stretches play out in real time. |
| 1s … 4h | Candle timeframe. The current candle stays partial, as it was at the replay time. |
| **B** / **S** / **F** | Buy, sell, or flatten at the last traded price (NQ $20/pt, ES $50/pt) |

## The chart

* **Top bar:** symbol, timeframes (1s–4h), chart type (candles, hollow candles, bars, line, area), indicators
  (EMA 9/21/50, session VWAP that resets at 18:00 New York), jump to a time, Market Open, screenshot (PNG incl. drawings),
  settings, side panel toggle, full screen.
* **Drawing tools (left), grouped like TradingView:** each button remembers the last tool used; hover and click › (or long-press)
  for the group menu.
  Cursors (cross, dot, arrow, eraser) · Lines (trend, ray, info line, extended, trend angle, horizontal line/ray, vertical line,
  cross line, parallel channel, rectangle) · Fibonacci (retracement, trend-based extension) · Patterns (XABCD, ABCD, triangle, with ratios) ·
  Projection & measurers (long/short position with target, stop, R:R, ticks and $; date range, price range, date & price range) ·
  Brushes (brush, highlighter) · Text (text, callout, price label, arrow, arrow marks) · Icons (emoji stickers) · Measure · Zoom in/out ·
  Magnet (off/weak/strong) · Stay in drawing mode · Lock all · Hide (drawings, indicators, trade markers) · Share drawings across
  sessions · Remove (drawings, indicators). Drag drawings or handles, right-click for colour, line width, clone, bring to front,
  remove. Shortcuts: Alt+T trend, Alt+H horizontal line, Alt+J horizontal ray, Alt+V vertical, Alt+C cross line, Alt+F fib,
  Alt+Shift+R rectangle, Del removes the selected drawing, Esc cancels.
* **Replay controls (chart toolbar):** play/pause, next tick, next candle, speed, 📅 jump to a date (with "skip closed
  market"), 🔔 Open and the replay clock.
* **Drawing settings (double-click a drawing, or right-click → Settings):** Style (colour, width, solid/dotted/dashed, extend
  left/right, fill and opacity for boxes and channels, price label on/off), Text (text along the line or inside the box, colour,
  size, bold, position and alignment), Coordinates (exact price and time of each point), Visibility (seconds / minutes / hours
  timeframes). Fib retracement and extension: every level can be switched on/off, re-valued and re-coloured, levels can be added,
  plus extend left/right, reverse, prices, levels as values or percents, labels left/right, background and trend line.
* **Drawing templates:** Template ▾ → "Save drawing template as…" stores the look (incl. text and Fib levels) under a name per tool;
  "Save as default" makes every new drawing of that tool use it; saved templates are one click away; "Reset to factory default".
* **Settings (gear):** candle colours, volume, background, grid, crosshair, watermark, scale text and lines, right margin,
  side panel, fill markers, default drawing colour and default R:R for the position tool. Saved on this PC.
* **Layout (Tradesea style):** account strip (session, Bal, RP&L, UP&L, version), app menu on the left, chart card with
  tools, Bid/Ask labels on the price axis, Orders / Positions / Fills tabs below, DOM + order panel on the right.
* **Orders on the chart:** hover next to the price axis and click ⊕ to place a Buy/Sell Limit or Stop at that price (the type
  follows the price vs. the market), or click a price in the DOM's My Bid / My Ask column (right-click cancels). Drag an order label
  to move it (an entry dragged across the market switches limit ↔ stop); ✕ cancels. The position label shows avg price and live P&L
  with +TP, +SL, reverse and close.
* **Brackets:** tick "Bracket" and set TP/SL in ticks; every entry (market, limit or stop) gets a take-profit limit and stop-loss
  stop as an OCO pair. Exits never grow the position and disappear when you are flat.
* **Fills:** limits fill when price trades through them (or touches, see Settings → Trading); stops fill at the trade that triggers
  them, so slippage is real; market orders fill at the ask/bid.
* **Order panel:** lots with quick sizes, Buy / Sell, Join Bid / Join Ask, Close Position / Reverse, Cancel All / Flatten All,
  and an Order tab for exact limit/stop prices.

## Licenses

Tick Replay's own code is yours. It builds on open-source parts that allow commercial use:
TradingView Lightweight Charts (Apache-2.0; keep the "Charts by TradingView" attribution and link),
FastAPI, Starlette, Pydantic, uvicorn, NumPy, pandas, zstandard (MIT/BSD), PyArrow (Apache-2.0) and
PyInstaller (GPL with an exception that allows distributing the built program under your own terms).
Market data is licensed separately by its vendor (e.g. Databento/CME) and is not redistributable with the program.

## How it works

* `server/store.py` loads day files, cuts tick windows (`after < ts <= until`), and builds candles
  from 1-second bars plus the raw ticks of the current second, so the last candle is exactly partial.
* `server/app.py` has a FastAPI backend with `/api/symbols`, `/api/candles` and `/api/ticks`. It also serves `web/`:
  `index.html` is the start page and `chart.html` is the replay (URL options: `?symbol=NQ&date=YYYY-MM-DD&open=1&tf=60`).
* `web/app.js` runs the replay clock in the browser. It fetches ticks in chunks ahead of the clock.
  On every frame it applies all ticks with `ts <= clock` to the forming candle, using
  [Lightweight Charts](https://github.com/tradingview/lightweight-charts) (Apache-2.0, bundled in `web/vendor/`).

```bash
python -m pytest tests
```

## Known limits / next steps

* Market orders fill at the ask/bid when the data has quotes (TBBO, NinjaTrader), otherwise at the last trade.
  Market orders bigger than the quoted size don't slip yet. Limit and stop orders, commissions, and a trade log with stats come next.
* The chart shows New York time using one UTC offset per load, so history across a DST change is off by one hour.
* Contract rolls aren't handled. Import one continuous series per symbol.
