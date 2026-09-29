/* Tick replay: plays historical ticks through a TradingView-style chart.
 *
 * The browser owns the replay clock. Ticks are fetched in chunks ahead of the
 * clock; every animation frame the clock advances by (elapsed real ms * speed)
 * and every tick with ts <= clock is applied to the forming candle, so a price
 * stays on screen exactly until the next tick's millisecond is reached.
 */
(() => {
  "use strict";

  const TIMEFRAMES = [
    [1, "1s"], [5, "5s"], [15, "15s"], [30, "30s"],
    [60, "1m"], [180, "3m"], [300, "5m"], [900, "15m"], [1800, "30m"],
    [3600, "1h"], [14400, "4h"],
  ];
  const SPEEDS = [0.25, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800, 3600];
  const HISTORY_CANDLES = 600;
  const TICK_LIMIT = 200000;
  const CLOSED_GAP_MS = 5 * 60 * 1000; // "skip gaps" only jumps over silences at least this long
  const TAPE_ROWS = 40;
  const BIG_PRINT = 20;             // highlight aggressive prints of at least this many contracts
  const TZ = "America/New_York";
  const RTH_OPEN = "09:30:00";      // CME equity index regular session open, New York
  const PRE_OPEN = "09:25:00";      // Market Open mode starts here, so the open is lived through at 1x

  const $ = (id) => document.getElementById(id);

  // ---- time helpers ---------------------------------------------------------

  const tzFmt = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });

  /** Seconds to add to a UTC instant to get New York wall-clock time. */
  function nyOffsetSec(ms) {
    const p = Object.fromEntries(tzFmt.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
    const wall = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
    return Math.round((wall - Math.floor(ms / 1000) * 1000) / 1000);
  }

  /** "YYYY-MM-DD HH:MM:SS.mmm" in New York time. */
  function fmtNY(ms, withDate = true) {
    const s = new Date(ms + nyOffsetSec(ms) * 1000).toISOString();
    return withDate ? s.slice(0, 10) + " " + s.slice(11, 23) : s.slice(11, 23);
  }

  /** datetime-local value (New York wall time) -> UTC ms. */
  function parseNY(value) {
    const [d, t = "00:00:00"] = value.split("T");
    const [Y, M, D] = d.split("-").map(Number);
    const [h, m, s = 0] = t.split(":").map(Number);
    const wall = Date.UTC(Y, M - 1, D, h, m, s);
    let ms = wall - nyOffsetSec(wall) * 1000;
    ms = wall - nyOffsetSec(ms) * 1000; // second pass settles DST edges
    return ms;
  }

  function toInputNY(ms) {
    return new Date(ms + nyOffsetSec(ms) * 1000).toISOString().slice(0, 19);
  }

  async function api(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  }

  function status(msg, ms = 2500) {
    const el = $("status");
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(status._t);
    if (ms) status._t = setTimeout(() => el.classList.remove("show"), ms);
  }

  const money = (v) => (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // ---- state ----------------------------------------------------------------

  const S = {
    symbols: [],
    sym: null,          // symbol info from /api/symbols
    tf: 60,
    t: 0,               // replay clock, ms UTC
    playing: false,
    speed: 1,
    skipGaps: true,
    dispOffset: 0,      // seconds added to candle times for display (fixed per load, keeps times ascending)
    bar: null,          // forming candle {bucket, open, high, low, close, volume}
    firstBucket: null,
    last: null,         // last traded price
    bid: null,          // best bid / ask (only with quote data)
    ask: null,
    lastDir: 0,
    tape: [],
    vap: new Map(),     // price -> {b: buy-aggressor volume, s: sell-aggressor volume}
    dirty: false,
    buf: null,
    pos: { qty: 0, avg: 0, realized: 0, fills: [], openTs: 0 },
    bt: null,           // backtest session (?bt=<id>): range, balance, saved trades
    spentMs: 0,         // real time spent / market time replayed since the last save
    replayedMs: 0,
  };

  function newBuffer(t) {
    return { gen: (S.buf ? S.buf.gen : 0) + 1, ts: [], price: [], size: [], side: [], bid: [], ask: [], i: 0, covered: t, nextTs: null, eof: false, pending: null };
  }

  // ---- settings -------------------------------------------------------------

  const DEFAULTS = {
    upColor: "#26a69a", downColor: "#ef5350", wickUp: "#26a69a", wickDown: "#ef5350",
    border: false, borderUp: "#26a69a", borderDown: "#ef5350", volume: true,
    bg: "#111318", grid: "both", gridColor: "#1b1f27", crosshair: "normal", crossColor: "#758696",
    watermark: "hidden", text: "#b2b5be", fontSize: "12", scaleLine: "#242b39", rightOffset: 8,
    sidePanel: true, markers: true, drawColor: "#2962ff", rr: 2, bidAsk: true, limitFill: "through",
    chartType: "candles", indicators: [],
    bgType: "solid", bg2: "#05070d", gridColorH: "#1b1f27", gridStyle: "0", scaleMode: "0", lastLine: true,
    slSymbol: true, slOhlc: true, slChange: true, slVolume: true, slInd: true,
  };
  // one-click looks for the Canvas tab; each only sets colours, never layout or trading options
  const THEMES = {
    dark: { bgType: "solid", bg: "#111318", gridColor: "#1b1f27", gridColorH: "#1b1f27", text: "#b2b5be", scaleLine: "#242b39", crossColor: "#758696",
      upColor: "#26a69a", downColor: "#ef5350", wickUp: "#26a69a", wickDown: "#ef5350", borderUp: "#26a69a", borderDown: "#ef5350" },
    tradesea: { bgType: "solid", bg: "#e4e2d6", gridColor: "#d3d0c2", gridColorH: "#d3d0c2", text: "#3b3d44", scaleLine: "#c5c2b3", crossColor: "#6b6e78",
      upColor: "#1f9d55", downColor: "#111111", wickUp: "#1f9d55", wickDown: "#111111", borderUp: "#1f9d55", borderDown: "#111111" },
    tv: { bgType: "solid", bg: "#ffffff", gridColor: "#f0f3fa", gridColorH: "#f0f3fa", text: "#131722", scaleLine: "#e0e3eb", crossColor: "#9598a1",
      upColor: "#089981", downColor: "#f23645", wickUp: "#089981", wickDown: "#f23645", borderUp: "#089981", borderDown: "#f23645" },
    fxr: { bgType: "solid", bg: "#d9d6bf", gridColor: "#cbc7ae", gridColorH: "#cbc7ae", text: "#2b2b2b", scaleLine: "#bdb99f", crossColor: "#55585f",
      upColor: "#4caf50", downColor: "#e53935", wickUp: "#4caf50", wickDown: "#e53935", borderUp: "#4caf50", borderDown: "#e53935" },
    midnight: { bgType: "gradient", bg: "#0e1a33", bg2: "#05070d", gridColor: "#15213b", gridColorH: "#15213b", text: "#aab4c8", scaleLine: "#1d2a45", crossColor: "#5f7194",
      upColor: "#26c6da", downColor: "#ff5277", wickUp: "#26c6da", wickDown: "#ff5277", borderUp: "#26c6da", borderDown: "#ff5277" },
  };
  const SETTINGS_KEY = "tickreplay.chartSettings";
  let cfg = { ...DEFAULTS };
  try { cfg = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}") }; } catch { /* defaults */ }
  const saveCfg = () => { try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(cfg)); } catch { /* ignore */ } };

  const CHART_TYPES = {
    candles: { label: "Candles", icon: '<path d="M7 4v16M17 4v16"/><rect x="5" y="7" width="4" height="9" fill="currentColor"/><rect x="15" y="9" width="4" height="6"/>' },
    hollow: { label: "Hollow candles", icon: '<path d="M7 4v16M17 4v16"/><rect x="5" y="7" width="4" height="9"/><rect x="15" y="9" width="4" height="6"/>' },
    bars: { label: "Bars", icon: '<path d="M7 4v16M4 8h3M7 16h3M17 4v16M14 7h3M17 14h3"/>' },
    line: { label: "Line", icon: '<path d="M3 17l5-6 4 3 5-8 4 5"/>' },
    area: { label: "Area", icon: '<path d="M3 17l5-6 4 3 5-8 4 5v7H3z" fill="currentColor" fill-opacity=".25"/>' },
  };
  const INDICATORS = {
    ema9: { label: "EMA 9", color: "#f5a623", len: 9 },
    ema21: { label: "EMA 21", color: "#4f7cff", len: 21 },
    ema50: { label: "EMA 50", color: "#e040fb", len: 50 },
    vwap: { label: "VWAP (session)", color: "#00bcd4" },
  };

  // ---- chart ----------------------------------------------------------------

  const chart = LightweightCharts.createChart($("chart"), {
    autoSize: true,
    localization: { locale: "en-US" },
    timeScale: { timeVisible: true, secondsVisible: true },
  });
  let main = null;                  // price series (type depends on cfg.chartType)
  const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  let avgLine = null;
  const indSeries = {};             // id -> line series
  const indVals = {};               // id -> values per bar index (EMA) / {pv, v} (VWAP)

  // every displayed bar, for indicators, drawings and switching chart type
  const bars = [];                  // {time, open, high, low, close, volume}
  const barTimes = [];

  const bucketOf = (ms) => Math.floor(ms / 1000 / S.tf) * S.tf;
  const dispTime = (bucket) => bucket + S.dispOffset;
  const volColor = (b) => (b.close >= b.open ? cfg.upColor : cfg.downColor) + "73";
  const mainPoint = (b) => (cfg.chartType === "line" || cfg.chartType === "area")
    ? { time: b.time, value: b.close }
    : { time: b.time, open: b.open, high: b.high, low: b.low, close: b.close };

  function makeMainSeries() {
    if (main) chart.removeSeries(main);
    avgLine = null;
    const t = cfg.chartType;
    if (t === "bars") main = chart.addBarSeries({ upColor: cfg.upColor, downColor: cfg.downColor, thinBars: false });
    else if (t === "line") main = chart.addLineSeries({ color: cfg.drawColor, lineWidth: 2 });
    else if (t === "area") main = chart.addAreaSeries({ lineColor: cfg.drawColor, topColor: cfg.drawColor + "55", bottomColor: cfg.drawColor + "05", lineWidth: 2 });
    else {
      main = chart.addCandlestickSeries({
        upColor: t === "hollow" ? "rgba(0,0,0,0)" : cfg.upColor, downColor: cfg.downColor,
        wickUpColor: cfg.wickUp, wickDownColor: cfg.wickDown,
        borderVisible: cfg.border || t === "hollow", borderUpColor: t === "hollow" ? cfg.upColor : cfg.borderUp, borderDownColor: cfg.borderDown,
      });
    }
    main.applyOptions({ priceLineVisible: !!cfg.lastLine });
    main.setData(bars.map(mainPoint));
    refreshMarkers();
    shownQuote = null;   // bid/ask price lines belonged to the old series
  }

  function applySettings() {
    const g = cfg.grid, style = +cfg.gridStyle || 0;
    const background = cfg.bgType === "gradient"
      ? { type: LightweightCharts.ColorType.VerticalGradient, topColor: cfg.bg, bottomColor: cfg.bg2 }
      : { type: LightweightCharts.ColorType.Solid, color: cfg.bg };
    chart.applyOptions({
      layout: { background, textColor: cfg.text, fontSize: +cfg.fontSize },
      grid: {
        vertLines: { visible: g === "both" || g === "vert", color: cfg.gridColor, style },
        horzLines: { visible: g === "both" || g === "horz", color: cfg.gridColorH || cfg.gridColor, style },
      },
      crosshair: {
        mode: cfg.crosshair === "magnet" ? LightweightCharts.CrosshairMode.Magnet : LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: cfg.crossColor, labelBackgroundColor: "#2a2e39" }, horzLine: { color: cfg.crossColor, labelBackgroundColor: "#2a2e39" },
      },
      rightPriceScale: { borderColor: cfg.scaleLine, mode: +cfg.scaleMode || 0 },
      timeScale: { borderColor: cfg.scaleLine, rightOffset: +cfg.rightOffset },
      watermark: {
        visible: cfg.watermark === "symbol", color: "rgba(255,255,255,.06)", fontSize: 64,
        text: S.sym ? `${S.sym.symbol} · ${tfLabel(S.tf)}` : "",
      },
    });
    if (typeof applyCrosshair === "function" && cursorMode !== "cross") applyCrosshair();
    volume.applyOptions({ visible: cfg.volume });
    volume.setData(bars.map((b) => ({ time: b.time, value: b.volume, color: volColor(b) })));
    $("side").hidden = !cfg.sidePanel;
    $("legend").style.color = cfg.text;
    makeMainSeries();
    syncIndicators();
  }

  // ---- indicators (recomputed on load, updated incrementally per tick) --------

  function syncIndicators() {
    for (const id of Object.keys(indSeries)) {
      if (!cfg.indicators.includes(id)) { chart.removeSeries(indSeries[id]); delete indSeries[id]; delete indVals[id]; }
    }
    for (const id of cfg.indicators) {
      if (!INDICATORS[id]) continue;
      if (!indSeries[id]) {
        indSeries[id] = chart.addLineSeries({ color: INDICATORS[id].color, lineWidth: id === "vwap" ? 2 : 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, visible: !indHidden });
      }
      recomputeIndicator(id);
    }
  }

  /** VWAP resets at the 18:00 New York Globex open. */
  const vwapSession = (dispSec) => Math.floor((dispSec - 18 * 3600) / 86400);

  function indicatorAt(id, i) {
    const b = bars[i], def = INDICATORS[id];
    if (id === "vwap") {
      const tp = (b.high + b.low + b.close) / 3, prev = i > 0 ? indVals[id][i - 1] : null;
      const same = prev && vwapSession(bars[i - 1].time) === vwapSession(b.time);
      const pv = (same ? prev.pv : 0) + tp * b.volume, v = (same ? prev.v : 0) + b.volume;
      indVals[id][i] = { pv, v };
      return v ? pv / v : b.close;
    }
    const k = 2 / (def.len + 1), prev = i > 0 ? indVals[id][i - 1] : b.close;
    indVals[id][i] = i > 0 ? b.close * k + prev * (1 - k) : b.close;
    return indVals[id][i];
  }

  function recomputeIndicator(id) {
    indVals[id] = [];
    indSeries[id].setData(bars.map((b, i) => ({ time: b.time, value: indicatorAt(id, i) })));
  }

  function pushBar(b) {
    const d = { time: dispTime(b.bucket), open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume };
    const n = bars.length;
    if (n && bars[n - 1].time === d.time) bars[n - 1] = d;
    else { bars.push(d); barTimes.push(d.time); }
    main.update(mainPoint(d));
    volume.update({ time: d.time, value: d.volume, color: volColor(d) });
    const i = bars.length - 1;
    for (const id of Object.keys(indSeries)) indSeries[id].update({ time: d.time, value: indicatorAt(id, i) });
  }

  function applyTick(buf, k) {
    const ts = buf.ts[k], px = buf.price[k], sz = buf.size[k], side = buf.side[k];
    if (buf.bid[k] > 0 && buf.ask[k] > 0) {
      // quote before the trade, moved by the trade itself: a buyer lifting the offer
      // leaves the ask at least at the trade price, a seller hitting the bid likewise
      S.bid = side < 0 ? Math.min(buf.bid[k], px) : buf.bid[k];
      S.ask = side > 0 ? Math.max(buf.ask[k], px) : buf.ask[k];
    }
    const b = bucketOf(ts);
    if (!S.bar || b > S.bar.bucket) {
      if (S.bar && S.dirty) pushBar(S.bar);
      S.bar = { bucket: b, open: px, high: px, low: px, close: px, volume: sz };
    } else {
      const bar = S.bar;
      if (px > bar.high) bar.high = px;
      if (px < bar.low) bar.low = px;
      bar.close = px;
      bar.volume += sz;
    }
    if (S.last !== null && px !== S.last) S.lastDir = px > S.last ? 1 : -1;
    S.last = px;
    // volume traded at each price since the replay started, split by aggressor (DOM ladder)
    const aggr = side || S.lastDir || 1, key = px.toFixed(2);
    const v = S.vap.get(key) || { b: 0, s: 0 };
    if (aggr > 0) v.b += sz; else v.s += sz;
    S.vap.set(key, v);
    S.dirty = true;
    if (TR.orders.length) checkOrders(px, ts);
  }

  // ---- tick buffer ----------------------------------------------------------

  function fetchMore() {
    const buf = S.buf;
    if (buf.pending) return buf.pending;
    if (buf.eof) return Promise.resolve();
    const span = Math.max(120000, S.speed * 20000); // ~20 s of real playback ahead
    const url = `/api/ticks?symbol=${encodeURIComponent(S.sym.symbol)}&after=${buf.covered}&until=${buf.covered + span}&limit=${TICK_LIMIT}`;
    buf.pending = api(url).then((r) => {
      if (buf !== S.buf) return; // a seek replaced the buffer meanwhile
      buf.ts = buf.ts.slice(buf.i).concat(r.ts);
      buf.price = buf.price.slice(buf.i).concat(r.price);
      buf.size = buf.size.slice(buf.i).concat(r.size);
      buf.side = buf.side.slice(buf.i).concat(r.side);
      // bid/ask only exist for quote data (e.g. Databento TBBO); 0 = unknown
      buf.bid = buf.bid.slice(buf.i).concat(r.bid || r.ts.map(() => 0));
      buf.ask = buf.ask.slice(buf.i).concat(r.ask || r.ts.map(() => 0));
      buf.i = 0;
      buf.covered = r.covered_until;
      if (r.ts.length === 0) {
        if (r.next_ts === null) buf.eof = true;
        else buf.covered = Math.max(buf.covered, r.next_ts - 1); // nothing trades before next_ts
      }
      buf.nextTs = r.next_ts;
    }).catch((e) => {
      status("Tick load failed: " + e.message, 5000);
      S.playing = false;
    }).finally(() => { if (buf === S.buf) buf.pending = null; });
    return buf.pending;
  }

  /** Apply every buffered tick up to `target` (never past what the buffer covers). */
  function consumeUpTo(target) {
    const buf = S.buf;
    const lim = buf.eof ? target : Math.min(target, buf.covered);
    while (buf.i < buf.ts.length && buf.ts[buf.i] <= lim) {
      applyTick(buf, buf.i);
      buf.i++;
    }
    if (lim > S.t) S.t = lim;
  }

  function nextTickTs() {
    const buf = S.buf;
    return buf.i < buf.ts.length ? buf.ts[buf.i] : null;
  }

  /**
   * Jump the clock over closed-market stretches (no trade for 5+ minutes). Shorter quiet
   * periods are played out in full so the tape keeps its real rhythm.
   */
  function maybeSkipGap() {
    if (!S.skipGaps || S.buf.eof) return;
    // with the buffer drained, everything up to `covered` is known to be empty
    const nt = nextTickTs() ?? S.buf.covered + 1;
    if (nt - S.t >= CLOSED_GAP_MS && (nt - S.t) / S.speed > 1500) {
      S.t = Math.max(S.t, nt - Math.min(500 * S.speed, 60000));
    }
  }

  async function advanceTo(target) {
    for (;;) {
      consumeUpTo(target);
      if (S.t >= target || S.buf.eof) break;
      await fetchMore();
    }
  }

  async function ensureNextTick() {
    while (nextTickTs() === null && !S.buf.eof) await fetchMore();
    return nextTickTs();
  }

  // ---- load / seek ----------------------------------------------------------

  // ---- loading screen (first load) and a small chart spinner (later loads) -----

  const boot = {
    on: true,
    step(pct, text, title) {
      if (!this.on) return;
      $("bootBar").style.width = pct + "%";
      if (text) $("bootStep").textContent = text;
      if (title) $("bootTitle").textContent = title;
    },
    done() {
      if (!this.on) return;
      this.on = false;
      this.step(100, "Ready");
      setTimeout(() => $("boot").classList.add("hide"), 180);
    },
    fail(msg) {
      $("boot").classList.remove("hide");
      $("boot").classList.add("failed");
      $("bootTitle").textContent = "Could not open the chart";
      $("bootStep").textContent = "";
      $("bootErrMsg").textContent = msg;
      $("bootErr").hidden = false;
      this.on = false;
    },
  };
  let cloadT = null;
  const chartLoading = (on, text = "Loading…") => {
    clearTimeout(cloadT);
    if (!on) { $("cload").hidden = true; return; }
    $("cloadTxt").textContent = text;
    cloadT = setTimeout(() => { $("cload").hidden = false; }, 150);   // only for loads you would notice
  };

  async function load(t) {
    S.playing = false;
    S.t = t;
    S.buf = newBuffer(t);
    S.dispOffset = nyOffsetSec(t);
    const buf = S.buf;
    const what = `${S.sym.symbol} · ${tfLabel(S.tf)}`;
    boot.step(55, `Loading ${what} history…`);
    if (!boot.on) chartLoading(true, `Loading ${what}…`);
    let hist;
    try {
      hist = await api(`/api/candles?symbol=${encodeURIComponent(S.sym.symbol)}&tf=${S.tf}&end=${t}&count=${HISTORY_CANDLES}`);
    } finally {
      if (buf === S.buf) chartLoading(false);
    }
    if (buf !== S.buf) return;
    boot.step(78, `${hist.length} candles loaded · preparing ticks…`);
    bars.length = 0;
    barTimes.length = 0;
    for (const c of hist) {
      bars.push({ time: dispTime(c.time), open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume });
      barTimes.push(dispTime(c.time));
    }
    main.setData(bars.map(mainPoint));
    volume.setData(bars.map((b) => ({ time: b.time, value: b.volume, color: volColor(b) })));
    for (const id of Object.keys(indSeries)) recomputeIndicator(id);
    draw.load(`tickreplay.drawings.${S.bt ? S.bt.id : "free"}.${S.sym.symbol}`, `tickreplay.drawings.shared.${S.sym.symbol}`);
    chart.applyOptions({ watermark: { text: `${S.sym.symbol} · ${tfLabel(S.tf)}` } });
    const lastC = hist[hist.length - 1];
    S.bar = lastC ? { bucket: lastC.time, open: lastC.open, high: lastC.high, low: lastC.low, close: lastC.close, volume: lastC.volume } : null;
    S.firstBucket = hist.length ? hist[0].time : null;
    S.last = lastC ? lastC.close : null;
    S.bid = S.ask = null;
    S.dirty = false;
    S.tape = [];
    S.vap = new Map();
    domCenterPx = null;
    refreshMarkers();
    chart.timeScale().scrollToRealTime();
    const first = fetchMore();
    render(true);
    if (boot.on) { await first; boot.done(); }
  }

  // ---- trading engine ---------------------------------------------------------
  //
  // Working orders are checked against every replayed trade:
  //   buy limit  fills when a trade prints below its price (or at it, with "touch" fills)
  //   sell limit fills when a trade prints above its price
  //   buy stop   triggers when a trade prints at/above its price and fills at that trade (slippage)
  //   sell stop  triggers when a trade prints at/below its price
  // Entry orders can carry a bracket: on fill, a take-profit limit and a stop-loss stop are
  // attached as an OCO pair; exits never grow a position and vanish when it is flat.

  const TR = { orders: [], seq: 1, fillLog: [] };
  const tick = () => (S.sym ? S.sym.tick_size : 0.25);
  const roundTick = (p) => Math.round(p / tick()) * tick();
  const lots = () => Math.max(1, Math.min(100, +$("qty").value | 0 || 1));
  const bracketCfg = () => ($("brOn").checked ? { tp: Math.max(1, +$("brTp").value | 0), sl: Math.max(1, +$("brSl").value | 0) } : null);
  const refPx = (side) => (side > 0 ? (S.ask ?? S.last) : (S.bid ?? S.last));

  /** Execute a fill against the position (the old market-order logic). */
  function execute(signedQty, px, how) {
    const pos = S.pos, pv = S.sym.point_value;
    const p = pos.qty, q = signedQty;
    const feePerSide = S.bt ? S.bt.fee_per_side || 0 : 0;
    if (p === 0 || Math.sign(p) === Math.sign(q)) {
      if (p === 0) pos.openTs = S.t;
      pos.avg = (pos.avg * Math.abs(p) + px * Math.abs(q)) / Math.abs(p + q);
    } else {
      const closing = Math.min(Math.abs(q), Math.abs(p));
      const gross = closing * (px - pos.avg) * Math.sign(p) * pv;
      const fees = closing * feePerSide * 2; // entry + exit commission for the closed contracts
      pos.realized += gross - fees;
      recordTrade({
        symbol: S.sym.symbol, side: Math.sign(p), qty: closing,
        entry_ts: pos.openTs, entry_px: pos.avg, exit_ts: S.t, exit_px: px,
        pnl: Math.round((gross - fees) * 100) / 100, fees,
      });
      if (Math.abs(q) > Math.abs(p)) { pos.avg = px; pos.openTs = S.t; } // flipped
    }
    pos.qty = p + q;
    if (pos.qty === 0) pos.avg = 0;
    pos.fills.push({ t: S.t, qty: q, px });
    TR.fillLog.unshift({ t: S.t, qty: q, px, how });
    syncExits();
    refreshMarkers();
    ordersDirty = true;
  }

  function market(signedQty, bracket = bracketCfg()) {
    if (S.last === null) return status("No price yet");
    const side = Math.sign(signedQty), px = refPx(side);
    execute(signedQty, px, "Market");
    if (bracket) attachBracket(side, Math.abs(signedQty), px, bracket);
    render(true);
  }

  function attachBracket(side, qty, entryPx, br) {
    const oco = "oco" + TR.seq;
    addOrder({ side: -side, type: "limit", price: roundTick(entryPx + side * br.tp * tick()), qty, role: "tp", oco });
    addOrder({ side: -side, type: "stop", price: roundTick(entryPx - side * br.sl * tick()), qty, role: "sl", oco });
  }

  function addOrder(o) {
    const ord = { id: TR.seq++, placed: S.t, ...o, price: roundTick(o.price) };
    // a limit on the wrong side of the market is marketable: fill it now at the quote
    if (ord.role === "entry" && ord.type === "limit" && S.last !== null) {
      const q = refPx(ord.side);
      if ((ord.side > 0 && ord.price >= q) || (ord.side < 0 && ord.price <= q)) {
        execute(ord.side * ord.qty, q, "Limit");
        if (ord.bracket) attachBracket(ord.side, ord.qty, q, ord.bracket);
        render(true);
        return null;
      }
    }
    TR.orders.push(ord);
    ordersDirty = true;
    return ord;
  }

  /** Place an entry order at a price; limit or stop is picked from where the price is vs. the market. */
  function placeAt(side, price, qty = lots()) {
    if (S.last === null) return status("No price yet");
    price = roundTick(price);
    const q = refPx(side);
    const type = side > 0 ? (price <= q ? "limit" : "stop") : (price >= q ? "limit" : "stop");
    addOrder({ side, type, price, qty, role: "entry", bracket: bracketCfg() });
    render(true);
  }

  function cancelOrder(id) {
    const o = TR.orders.find((x) => x.id === id);
    TR.orders = TR.orders.filter((x) => x.id !== id);
    // cancelling one side of a bracket keeps the other: it is still a valid exit
    if (o) ordersDirty = true;
  }
  function cancelAll() { TR.orders = []; ordersDirty = true; render(true); }

  /** Exits never outsize the position; with no position they are gone. */
  function syncExits() {
    const q = S.pos.qty;
    TR.orders = TR.orders.filter((o) => {
      if (o.role === "entry") return true;
      if (q === 0 || Math.sign(o.side) === Math.sign(q)) return false;
      o.qty = Math.min(o.qty, Math.abs(q));
      return true;
    });
  }

  function checkOrders(px) {
    const touch = cfg.limitFill === "touch";
    for (const o of TR.orders.slice()) {
      if (!TR.orders.includes(o)) continue;          // cancelled by an OCO sibling this tick
      let fillPx = null;
      if (o.type === "limit") {
        if (o.side > 0 ? (px < o.price || (touch && px === o.price)) : (px > o.price || (touch && px === o.price))) fillPx = o.price;
      } else if (o.side > 0 ? px >= o.price : px <= o.price) {
        fillPx = o.side > 0 ? Math.max(o.price, px) : Math.min(o.price, px);   // stops slip to the trade that triggered them
      }
      if (fillPx === null) continue;
      TR.orders = TR.orders.filter((x) => x !== o && (!o.oco || x.oco !== o.oco));
      let qty = o.qty;
      if (o.role !== "entry") {
        qty = Math.min(qty, Math.abs(S.pos.qty));
        if (!qty || Math.sign(S.pos.qty) === o.side) continue;
      }
      const how = o.role === "tp" ? "Take profit" : o.role === "sl" ? "Stop loss" : o.type === "limit" ? "Limit" : "Stop";
      execute(o.side * qty, fillPx, how);
      if (o.role === "entry" && o.bracket) attachBracket(o.side, qty, fillPx, o.bracket);
      status(`${how} filled: ${o.side > 0 ? "bought" : "sold"} ${qty} @ ${fillPx.toFixed(2)}`, 2500);
    }
  }

  // In a backtest session the open position and working orders survive closing the window.
  const liveKey = () => (S.bt ? `tickreplay.live.${S.bt.id}` : null);
  let liveRestored = false;   // never overwrite the saved state before it has been read back
  function saveLive() {
    const k = liveKey();
    if (!k || !S.sym || !liveRestored) return;
    const live = { symbol: S.sym.symbol, pos: { qty: S.pos.qty, avg: S.pos.avg, openTs: S.pos.openTs }, orders: TR.orders, seq: TR.seq };
    try { localStorage.setItem(k, JSON.stringify(live)); } catch { /* storage blocked */ }
  }
  function restoreLive() {
    const k = liveKey();
    if (!k) return;
    liveRestored = true;
    try {
      const live = JSON.parse(localStorage.getItem(k) || "null");
      if (!live || live.symbol !== S.sym.symbol) return;
      Object.assign(S.pos, live.pos);
      TR.orders = live.orders || [];
      TR.seq = Math.max(TR.seq, live.seq || 1);
      ordersDirty = true;
      if (S.pos.qty || TR.orders.length) status(`Restored ${S.pos.qty ? "your open position" : ""}${S.pos.qty && TR.orders.length ? " and " : ""}${TR.orders.length ? TR.orders.length + " working order" + (TR.orders.length === 1 ? "" : "s") : ""}`, 4000);
    } catch { /* ignore */ }
  }

  function closePosition() { if (S.pos.qty) market(-S.pos.qty, null); }
  function reversePosition() { if (S.pos.qty) market(-2 * S.pos.qty, null); }
  function flattenAll() { TR.orders = []; closePosition(); ordersDirty = true; render(true); }

  function recordTrade(trade) {
    if (!S.bt) return;
    S.bt.trades.push(trade);
    fetch(`/api/backtests/${S.bt.id}/trades`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(trade),
    }).catch(() => status("Could not save the trade", 4000));
  }

  // ---- backtest session progress ------------------------------------------

  function progressBody() {
    const body = JSON.stringify({
      current_ts: Math.round(S.t), current_symbol: S.sym ? S.sym.symbol : null,
      add_time_ms: Math.round(S.spentMs), add_replayed_ms: Math.round(S.replayedMs),
    });
    S.spentMs = 0;
    S.replayedMs = 0;
    return body;
  }

  function saveProgress() {
    if (!S.bt || !S.sym) return;
    fetch(`/api/backtests/${S.bt.id}/progress`, { method: "POST", body: progressBody() }).catch(() => {});
  }

  function saveProgressOnExit() {
    if (!S.bt || !S.sym) return;
    navigator.sendBeacon(`/api/backtests/${S.bt.id}/progress`, progressBody());
  }

  function refreshMarkers() {
    if (!main) return;
    const cur = S.bar ? S.bar.bucket : Infinity;
    const markers = !cfg.markers ? [] : S.pos.fills
      .map((f) => ({ f, b: bucketOf(f.t) }))
      .filter(({ b }) => b <= cur && (S.firstBucket === null || b >= S.firstBucket))
      .map(({ f, b }) => ({
        time: dispTime(b),
        position: f.qty > 0 ? "belowBar" : "aboveBar",
        color: f.qty > 0 ? "#26a69a" : "#ef5350",
        shape: f.qty > 0 ? "arrowUp" : "arrowDown",
        text: `${f.qty > 0 ? "B" : "S"} ${Math.abs(f.qty)} @ ${f.px}`,
      }))
      .sort((a, b) => a.time - b.time);
    main.setMarkers(markers);

    if (avgLine) { main.removePriceLine(avgLine); avgLine = null; }
    if (S.pos.qty !== 0) {
      avgLine = main.createPriceLine({
        price: S.pos.avg, color: S.pos.qty > 0 ? "#26a69a" : "#ef5350",
        lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true,
        title: `${S.pos.qty > 0 ? "LONG" : "SHORT"} ${Math.abs(S.pos.qty)}`,
      });
    }
  }

  // ---- render ---------------------------------------------------------------

  let lastPanelRender = 0, playShown = null, hovering = false;

  const tfLabel = (tf) => (TIMEFRAMES.find(([s]) => s === tf) || [0, tf + "s"])[1];

  function renderLegend(i) {
    const b = bars[i];
    if (!b || !S.sym) { $("legend").innerHTML = ""; return; }
    const up = b.close >= b.open, c = up ? cfg.upColor : cfg.downColor;
    const chg = i > 0 ? b.close - bars[i - 1].close : 0;
    const v = (x) => `<b style="color:${c}">${x.toFixed(2)}</b>`;
    // what shows is chosen in Settings → Status line
    let html = `<div class="l1">${cfg.slSymbol ? `<span class="name">${S.sym.symbol} · ${tfLabel(S.tf)}</span>` : ""}
      ${cfg.slOhlc ? `<span>O ${v(b.open)}</span><span>H ${v(b.high)}</span><span>L ${v(b.low)}</span><span>C ${v(b.close)}</span>` : ""}
      ${cfg.slChange ? `<span style="color:${c}">${chg >= 0 ? "+" : ""}${chg.toFixed(2)}</span>` : ""}
      ${cfg.slVolume ? `<span>Vol <b>${b.volume.toLocaleString("en-US")}</b></span>` : ""}</div>`;
    const ind = !cfg.slInd ? "" : Object.keys(indSeries).map((id) => {
      const val = id === "vwap" ? (indVals[id][i] && indVals[id][i].v ? indVals[id][i].pv / indVals[id][i].v : null) : indVals[id][i];
      return val == null ? "" : `<span style="color:${INDICATORS[id].color}">${INDICATORS[id].label} <b>${val.toFixed(2)}</b></span>`;
    }).join("");
    if (ind) html += `<div class="ind">${ind}</div>`;
    $("legend").innerHTML = html;
  }

  function render(force = false) {
    if (S.dirty && S.bar) {
      pushBar(S.bar);
      S.dirty = false;
    }
    draw.redraw();
    placeOrderLabels();
    $("clock").textContent = S.sym ? fmtNY(S.t) : "--";
    $("countdown").textContent = S.sym ? openCountdown(S.t) : "";
    if (playShown !== S.playing) {
      playShown = S.playing;
      $("play").innerHTML = S.playing ? '<svg viewBox="0 0 24 24"><rect x="6" y="5" width="4" height="14"/><rect x="14" y="5" width="4" height="14"/></svg>'
        : '<svg viewBox="0 0 24 24"><path d="M7 4.5v15l13-7.5z"/></svg>';
    }

    const now = performance.now();
    if (!force && now - lastPanelRender < 100) return; // DOM panels at ~10 fps
    lastPanelRender = now;
    if (!hovering) renderLegend(bars.length - 1);
    renderHeader();
    renderBidAsk();
    renderLadder();
    // labels carry live P&L, so refresh them while anything is on the chart (not mid-click)
    if ((ordersDirty || force || TR.orders.length || S.pos.qty || ordLabels.size) && !layerBusy) buildOrderLabels();
    if (ordersDirty) saveLive();
    if (ordersDirty || force || now - lastBottom > 500) { renderBottom(); ordersDirty = false; }
    $("askLbl").textContent = S.ask !== null ? S.ask.toFixed(2) : S.last !== null ? S.last.toFixed(2) : "";
    $("bidLbl").textContent = S.bid !== null ? S.bid.toFixed(2) : S.last !== null ? S.last.toFixed(2) : "";
  }

  const openPnl = () => (S.pos.qty && S.last !== null ? (S.last - S.pos.avg) * S.pos.qty * S.sym.point_value : 0);
  const signed$ = (v) => (v > 0 ? "+" : v < 0 ? "−" : "") + "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const cls = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "");

  function renderHeader() {
    if (!S.sym) return;
    const start = S.bt ? S.bt.balance : 50000, open = openPnl();
    $("hBal").textContent = money(start + S.pos.realized + open);
    $("hRpl").textContent = signed$(S.pos.realized); $("hRpl").className = cls(S.pos.realized);
    $("hUpl").textContent = S.pos.qty ? signed$(open) : "$ --"; $("hUpl").className = cls(open);
  }

  // ---- bid / ask labels on the price axis ------------------------------------

  let bidLine = null, askLine = null, shownQuote = "";
  function renderBidAsk() {
    const want = cfg.bidAsk && S.bid !== null && main ? `${S.bid}|${S.ask}` : "";
    if (want === shownQuote && (!want || (bidLine && askLine))) return;
    shownQuote = want;
    if (bidLine) { try { main.removePriceLine(bidLine); } catch { /* series replaced */ } bidLine = null; }
    if (askLine) { try { main.removePriceLine(askLine); } catch { /* series replaced */ } askLine = null; }
    if (!want) return;
    const common = { lineVisible: false, axisLabelVisible: true, lineWidth: 1 };
    askLine = main.createPriceLine({ ...common, price: S.ask, color: "#e0474c", title: "Ask" });
    bidLine = main.createPriceLine({ ...common, price: S.bid, color: "#2f6bff", title: "Bid" });
  }

  // ---- orders on the chart -----------------------------------------------------

  let ordersDirty = true, lastBottom = 0, dragOrd = null, layerBusy = false;
  const ordLabels = new Map();   // id -> {el, line}
  const ordTitle = (o) => o.role === "tp" ? "TP" : o.role === "sl" ? "SL" : `${o.side > 0 ? "BUY" : "SELL"} ${o.type === "limit" ? "LMT" : "STP"}`;
  const ordClass = (o) => o.role === "tp" ? "tp" : o.role === "sl" ? "sl" : o.side > 0 ? "buy" : "sell";
  const ordColor = (o) => ({ tp: "#0f9d76", sl: "#e0474c", buy: "#2f6bff", sell: "#e0474c" })[ordClass(o)];

  /** What an order is worth vs. the position (exits) or the market (entries). */
  function ordDetail(o) {
    const pv = S.sym.point_value;
    if (o.role !== "entry" && S.pos.qty) {
      const pnl = (o.price - S.pos.avg) * Math.sign(S.pos.qty) * o.qty * pv;
      const t = Math.round((o.price - S.pos.avg) / tick()) * Math.sign(S.pos.qty);
      return `<span class="pnl ${cls(pnl)}">${t > 0 ? "+" : ""}${t}t ${signed$(pnl)}</span>`;
    }
    const ref = S.last ?? o.price, t = Math.round(Math.abs(o.price - ref) / tick());
    return `<span class="muted">${t}t away</span>`;
  }

  function buildOrderLabels() {
    const layer = $("ordersLayer");
    const wanted = new Set();
    const items = TR.orders.map((o) => ({ key: "o" + o.id, o }));
    if (S.pos.qty) items.push({ key: "pos", pos: true });
    for (const it of items) {
      wanted.add(it.key);
      let rec = ordLabels.get(it.key);
      if (!rec) {
        const line = document.createElement("div"); line.className = "ord-line";
        const el = document.createElement("div");
        layer.append(line, el);
        rec = { el, line };
        ordLabels.set(it.key, rec);
      }
      if (it.pos) {
        const q = S.pos.qty, open = openPnl();
        rec.el.className = "ord posl";
        rec.el.innerHTML = `<span class="side">${q > 0 ? "LONG" : "SHORT"} ${Math.abs(q)}</span>
          <span class="body">${S.pos.avg.toFixed(2)} <span class="pnl ${cls(open)}">${signed$(open)}</span></span>
          <span class="act" data-pact="tp" title="Add a take profit">+TP</span><span class="act" data-pact="sl" title="Add a stop loss">+SL</span>
          <span class="act" data-pact="rev" title="Reverse">⇅</span><span class="x" data-pact="close" title="Close position">✕</span>`;
        rec.price = S.pos.avg; rec.color = q > 0 ? "#0f9d76" : "#e0474c"; rec.el.dataset.key = "pos";
      } else {
        const o = it.o;
        rec.el.className = `ord ${ordClass(o)}`;
        rec.el.innerHTML = `<span class="side">${ordTitle(o)}</span><span class="body">${o.qty} @ ${o.price.toFixed(2)} ${ordDetail(o)}</span><span class="x" data-cancel="${o.id}" title="Cancel">✕</span>`;
        rec.price = o.price; rec.color = ordColor(o); rec.el.dataset.key = it.key; rec.el.dataset.id = o.id;
      }
      rec.line.style.borderColor = rec.color;
    }
    for (const [k, rec] of ordLabels) if (!wanted.has(k)) { rec.el.remove(); rec.line.remove(); ordLabels.delete(k); }
    placeOrderLabels();
  }

  /** Keep labels on their price every frame (the price scale moves while playing). */
  function placeOrderLabels() {
    if (!main || !ordLabels.size) return;
    const w = chart.timeScale().width(), paneR = $("chart").clientWidth - w;  // price-scale width
    const placed = [];   // labels that sit close in price slide left instead of overlapping
    const items = [...ordLabels].map(([k, rec]) => {
      const price = dragOrd && dragOrd.key === k ? dragOrd.price : rec.price;
      return { k, rec, y: main.priceToCoordinate(price) };
    }).sort((a, b) => (a.k === "pos" ? -1 : b.k === "pos" ? 1 : (a.y ?? 0) - (b.y ?? 0)));
    for (const { k, rec, y } of items) {
      const vis = y !== null && y > 0 && y < $("chart").clientHeight - 26;
      rec.el.style.display = rec.line.style.display = vis ? "" : "none";
      if (!vis) continue;
      const width = rec.el.offsetWidth || 180;
      let right = paneR + (k === "pos" ? 240 : 12);
      for (let guard = 0; guard < 8; guard++) {
        const hit = placed.find((q) => Math.abs(q.y - y) < 24 && right < q.right + q.width + 6 && right + width + 6 > q.right);
        if (!hit) break;
        right = hit.right + hit.width + 8;
      }
      placed.push({ y, right, width });
      rec.el.style.top = y + "px";
      rec.el.style.right = right + "px";
      rec.line.style.top = y + "px";
      rec.line.style.width = w + "px";
    }
  }

  // ---- DOM ladder --------------------------------------------------------------

  let domCenterPx = null;
  function renderLadder() {
    if (!S.sym || $("side").hidden) return;
    const lad = $("ladder");
    const rows = Math.max(5, Math.floor(lad.clientHeight / 22));
    const tk = tick(), last = S.last;
    if (last === null) return;
    if ($("domCenter").checked || domCenterPx === null) domCenterPx = last;
    const top = roundTick(domCenterPx + Math.floor(rows / 2) * tk);
    let maxV = 1;
    for (const v of S.vap.values()) maxV = Math.max(maxV, v.b + v.s);
    const my = new Map();
    for (const o of TR.orders) {
      const k = o.price.toFixed(2) + (o.side > 0 ? "b" : "a");
      const e = my.get(k) || { q: 0, role: o.role };
      e.q += o.qty; if (o.role !== "entry") e.role = o.role;
      my.set(k, e);
    }
    // rows stay in place and only their contents change, so clicks never land on a replaced element
    if (lad.children.length !== rows) {
      lad.innerHTML = Array.from({ length: rows }, () =>
        '<div class="lrow"><span class="mb"></span><span class="bv"></span><span class="p"></span><span class="av"></span><span class="ma"></span><span class="v"><i></i><b></b></span></div>').join("");
    }
    const avgPx = S.pos.qty ? roundTick(S.pos.avg) : null;
    for (let r = 0; r < rows; r++) {
      const row = lad.children[r], c = row.children;
      const p = roundTick(top - r * tk), key = p.toFixed(2), v = S.vap.get(key) || { b: 0, s: 0 };
      const mb = my.get(key + "b"), ma = my.get(key + "a"), tot = v.b + v.s;
      row.dataset.p = key;
      row.className = "lrow" + (p === last ? " last" : "") + (S.bid !== null && p === S.bid ? " bidrow" : "")
        + (S.ask !== null && p === S.ask ? " askrow" : "") + (avgPx !== null && Math.abs(p - avgPx) < tk / 2 ? " avg" : "");
      c[0].className = "mb" + (mb ? " " + (mb.role === "entry" ? "has" : mb.role) : ""); c[0].textContent = mb ? mb.q : "";
      c[1].textContent = v.s || "";
      c[2].textContent = key;
      c[3].textContent = v.b || "";
      c[4].className = "ma" + (ma ? " " + (ma.role === "entry" ? "has" : ma.role) : ""); c[4].textContent = ma ? ma.q : "";
      c[5].firstChild.style.width = tot ? Math.round((tot / maxV) * 100) + "%" : "0";
      c[5].lastChild.textContent = tot || "";
    }
  }

  // ---- bottom tabs --------------------------------------------------------------

  let btab = "orders";
  function renderBottom() {
    lastBottom = performance.now();
    $("cntOrders").textContent = TR.orders.length || "";
    $("cntPos").textContent = S.pos.qty ? 1 : "";
    $("cntFills").textContent = TR.fillLog.length || "";
    const body = $("btabsBody");
    if (btab === "orders") {
      body.innerHTML = TR.orders.length ? `<table class="bt"><thead><tr><th>Side</th><th>Type</th><th>Qty</th><th>Price</th><th>Role</th><th>Distance</th><th>Placed (NY)</th><th></th></tr></thead><tbody>${
        TR.orders.map((o) => `<tr><td class="${o.side > 0 ? "b" : "s"}">${o.side > 0 ? "Buy" : "Sell"}</td><td>${o.type === "limit" ? "Limit" : "Stop"}</td>
          <td class="num">${o.qty}</td><td class="num">${o.price.toFixed(2)}</td><td>${o.role === "tp" ? "Take profit" : o.role === "sl" ? "Stop loss" : "Entry" + (o.bracket ? " + bracket" : "")}</td>
          <td class="num">${S.last !== null ? Math.round(Math.abs(o.price - S.last) / tick()) + "t" : ""}</td><td class="num">${fmtNY(o.placed, false).slice(0, 8)}</td>
          <td><button data-cancel="${o.id}">Cancel</button></td></tr>`).join("")}</tbody></table>`
        : `<div class="empty-row">No working orders. Click ⊕ next to the price axis, a price in the DOM, or use Join Bid / Join Ask.</div>`;
    } else if (btab === "positions") {
      const q = S.pos.qty, open = openPnl();
      body.innerHTML = q ? `<table class="bt"><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Avg price</th><th>Last</th><th>Ticks</th><th>Open P&amp;L</th><th></th></tr></thead><tbody>
        <tr><td><b>${S.sym.symbol}</b></td><td class="${q > 0 ? "b" : "s"}">${q > 0 ? "Long" : "Short"}</td><td class="num">${Math.abs(q)}</td>
        <td class="num">${S.pos.avg.toFixed(2)}</td><td class="num">${S.last.toFixed(2)}</td><td class="num">${Math.round(((S.last - S.pos.avg) * Math.sign(q)) / tick())}</td>
        <td class="num ${cls(open)}">${signed$(open)}</td><td><button data-pact="close">Close</button> <button data-pact="rev">Reverse</button></td></tr></tbody></table>`
        : `<div class="empty-row">Flat. Realized P&amp;L this session: <b class="${cls(S.pos.realized)}">${signed$(S.pos.realized)}</b></div>`;
    } else {
      body.innerHTML = TR.fillLog.length ? `<table class="bt"><thead><tr><th>Time (NY)</th><th>Side</th><th>Qty</th><th>Price</th><th>Order</th></tr></thead><tbody>${
        TR.fillLog.slice(0, 200).map((f) => `<tr><td class="num">${fmtNY(f.t)}</td><td class="${f.qty > 0 ? "b" : "s"}">${f.qty > 0 ? "Buy" : "Sell"}</td>
          <td class="num">${Math.abs(f.qty)}</td><td class="num">${f.px.toFixed(2)}</td><td>${f.how}</td></tr>`).join("")}</tbody></table>`
        : `<div class="empty-row">No fills yet.</div>`;
    }
  }

  /** "Open in 04:12" during the 30 minutes before the 09:30 New York open. */
  function openCountdown(t) {
    const open = parseNY(toInputNY(t).slice(0, 10) + "T" + RTH_OPEN);
    const left = open - t;
    if (left <= 0 || left > 30 * 60 * 1000) return "";
    const s = Math.ceil(left / 1000);
    return `Open in ${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  }

  // ---- main loop ------------------------------------------------------------

  let lastFrame = performance.now();

  function frame(now) {
    const dt = Math.min(now - lastFrame, 250); // don't leap after a background tab
    lastFrame = now;
    if (!document.hidden && S.bt) S.spentMs += dt;
    if (S.playing && S.buf) {
      const buf = S.buf, t0 = S.t;
      maybeSkipGap();
      consumeUpTo(S.t + dt * S.speed);
      maybeSkipGap();
      S.replayedMs += S.t - t0;
      if (S.bt && S.t >= S.bt.end_ts) {
        S.playing = false;
        status("End of this session's date range", 5000);
      }
      if (!buf.eof && buf.covered - S.t < S.speed * 8000) fetchMore();
      if (buf.eof && buf.i >= buf.ts.length) {
        S.playing = false;
        status("End of data");
      }
    }
    render();
    requestAnimationFrame(frame);
  }

  // ---- controls -------------------------------------------------------------

  function togglePlay() {
    if (!S.buf) return;
    S.playing = !S.playing;
    lastFrame = performance.now();
    render(true);
  }

  async function stepTick() {
    S.playing = false;
    const nt = await ensureNextTick();
    if (nt === null) return status("End of data");
    const buf = S.buf;
    applyTick(buf, buf.i);
    buf.i++;
    S.t = Math.max(S.t, nt);
    render(true);
  }

  async function stepBar() {
    S.playing = false;
    const nt = await ensureNextTick();
    if (nt === null) return status("End of data");
    // finish the candle that the next tick belongs to
    const target = (bucketOf(nt) + S.tf) * 1000 - 1;
    await advanceTo(target);
    render(true);
  }

  function setTf(tf, reload = true) {
    S.tf = tf;
    $("tfBtn").textContent = tfLabel(tf);
    for (const b of $("tfDrop").querySelectorAll("[data-tf]")) b.classList.toggle("on", +b.dataset.tf === tf);
    chart.applyOptions({ timeScale: { secondsVisible: tf < 60 } });
    if (S.sym && reload) return load(S.t);
  }

  function setSpeed(speed) {
    S.speed = speed;
    $("speed").value = String(speed);
  }

  /** Jump to just before the open of `day` (YYYY-MM-DD, New York) and play live, tick by tick. */
  async function marketOpen(day) {
    const t = parseNY(`${day}T${PRE_OPEN}`);
    if (t < S.sym.first_ts || t > S.sym.last_ts) {
      const msg = `No ${S.sym.symbol} data around the open on ${day}`;
      return boot.on ? boot.fail(msg + ". Pick another day on the dashboard.") : status(msg, 4000);
    }
    boot.step(45, `09:25 New York · plays live at 1x`, `${S.sym.symbol} · ${day} open`);
    $("start").value = toInputNY(t);
    setSpeed(1);
    await load(t);
    S.playing = true;
    lastFrame = performance.now();
    render(true);
  }

  /** Keep a time inside the data and, in a backtest session, inside its date range. */
  function clampToRange(t) {
    let lo = S.sym.first_ts, hi = S.sym.last_ts;
    if (S.bt) { lo = Math.max(lo, S.bt.start_ts); hi = Math.min(hi, S.bt.end_ts); }
    return Math.min(Math.max(t, lo), Math.max(lo, hi));
  }

  function defaultStart(sym) {
    // 09:30 New York on the second session in the data (so there is history to the left)
    const guess = sym.first_ts + 36 * 3600 * 1000;
    const day = toInputNY(guess).slice(0, 10);
    const t = parseNY(`${day}T09:30:00`);
    return Math.min(Math.max(t, sym.first_ts), sym.last_ts);
  }

  async function init() {
    const tfGroups = [["Seconds", (s) => s < 60], ["Minutes", (s) => s >= 60 && s < 3600], ["Hours", (s) => s >= 3600]];
    $("tfDrop").innerHTML = tfGroups.map(([ttl, f]) => `<div class="ttl">${ttl}</div>` +
      TIMEFRAMES.filter(([s]) => f(s)).map(([s, l]) => `<button data-tf="${s}">${l}</button>`).join("")).join("");
    $("tfBtn").addEventListener("click", (e) => { e.stopPropagation(); openDrop($("tfBtn"), $("tfDrop")); });
    $("tfDrop").addEventListener("click", (e) => {
      const b = e.target.closest("[data-tf]");
      if (!b) return;
      $("tfDrop").classList.remove("open");
      setTf(+b.dataset.tf);
    });
    $("speed").innerHTML = SPEEDS.map((s) => `<option value="${s}" ${s === 1 ? "selected" : ""}>${s}x</option>`).join("");
    $("speed").addEventListener("change", (e) => setSpeed(+e.target.value));
    $("skipGaps").addEventListener("change", (e) => { S.skipGaps = e.target.checked; });
    $("play").addEventListener("click", togglePlay);
    $("stepTick").addEventListener("click", stepTick);
    $("stepBar").addEventListener("click", stepBar);
    $("go").addEventListener("click", () => {
      if (!$("start").value) return;
      load(clampToRange(parseNY($("start").value)));
    });
    $("marketOpen").addEventListener("click", () => {
      const day = ($("start").value || toInputNY(S.t)).slice(0, 10);
      marketOpen(day).catch((e) => status("Load failed: " + e.message, 5000));
    });
    const sideAction = (side) => {
      const onOrderTab = !$("side").querySelector('[data-dpane="order"]').hidden;
      const type = $("ordType").querySelector(".on").dataset.otype;
      if (onOrderTab && type !== "market") {
        const price = +$("ordPrice").value;
        if (!price) return status("Enter a price");
        const q = refPx(side);
        if (type === "limit" && (side > 0 ? price > q : price < q)) return status("A buy limit goes below the market, a sell limit above", 3000);
        if (type === "stop" && (side > 0 ? price <= q : price >= q)) return status("A buy stop goes above the market, a sell stop below", 3000);
        addOrder({ side, type, price, qty: lots(), role: "entry", bracket: bracketCfg() });
        return render(true);
      }
      market(side * lots());
    };
    $("buy").addEventListener("click", () => sideAction(1));
    $("sell").addEventListener("click", () => sideAction(-1));
    $("flat").addEventListener("click", flattenAll);
    $("closePos").addEventListener("click", closePosition);
    $("reverse").addEventListener("click", reversePosition);
    $("cancelAll").addEventListener("click", cancelAll);
    $("joinBid").addEventListener("click", () => { const p = S.bid ?? S.last; if (p !== null) { addOrder({ side: 1, type: "limit", price: p, qty: lots(), role: "entry", bracket: bracketCfg() }); render(true); } });
    $("joinAsk").addEventListener("click", () => { const p = S.ask ?? S.last; if (p !== null) { addOrder({ side: -1, type: "limit", price: p, qty: lots(), role: "entry", bracket: bracketCfg() }); render(true); } });
    $("symbol").addEventListener("change", (e) => {
      if (S.pos.qty !== 0) {
        e.target.value = S.sym.symbol;
        return status("Close your position before switching symbol", 3000);
      }
      S.sym = S.symbols.find((s) => s.symbol === e.target.value);
      S.pos = { qty: 0, avg: 0, realized: S.bt ? S.pos.realized : 0, fills: [], openTs: 0 };
      TR.orders = []; ordersDirty = true;
      $("domSym").textContent = S.sym.symbol;
      const t = clampToRange(S.t);
      $("start").value = toInputNY(t);
      load(t);
    });

    setupChrome();

    document.addEventListener("keydown", (e) => {
      if (draw.onKey(e)) { e.preventDefault(); return; }
      if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName) || document.querySelector("dialog[open]")) return;
      if (e.code === "Space") { e.preventDefault(); togglePlay(); }
      else if (e.code === "ArrowRight") { e.preventDefault(); e.shiftKey ? stepBar() : stepTick(); }
      else if (e.key === "b" || e.key === "B") $("buy").click();
      else if (e.key === "s" || e.key === "S") $("sell").click();
      else if (e.key === "f" || e.key === "F") $("flat").click();
      else if (e.key === "Escape") { $("orderMenu").hidden = true; }
    });

    boot.step(12, "Connecting to the replay engine…");
    S.symbols = await api("/api/symbols");
    if (!S.symbols.length) return boot.fail("No tick data yet. Import your tick files on the Data page first.");
    // URL options: ?bt=<session id> or ?symbol=NQ&date=2024-03-05&open=1&tf=60&t=<ms>
    const q = new URLSearchParams(location.search);
    boot.step(28, `${S.symbols.length} symbol${S.symbols.length === 1 ? "" : "s"} available`, q.get("open") ? "Market Open practice" : "Free replay");
    if (q.get("bt")) {
      S.bt = await api(`/api/backtests/${encodeURIComponent(q.get("bt"))}`);
      boot.step(40, `Session loaded · ${S.bt.trades.length} trades so far`, S.bt.name);
      S.symbols = S.symbols.filter((s) => S.bt.symbols.includes(s.symbol));
      if (!S.symbols.length) return boot.fail("The data for this session's symbols was deleted. Import it again on the Data page.");
      S.pos.realized = S.bt.trades.reduce((a, t) => a + t.pnl, 0);
      $("acctName").textContent = S.bt.name;
      document.title = `${S.bt.name} · Tick Replay`;
      setInterval(saveProgress, 10000);
      addEventListener("pagehide", () => { saveProgressOnExit(); saveLive(); });
    }
    $("symbol").innerHTML = S.symbols.map((s) => `<option>${s.symbol}</option>`).join("");
    const wanted = (q.get("symbol") || (S.bt && S.bt.current_symbol) || "").toUpperCase();
    S.sym = S.symbols.find((s) => s.symbol === wanted) || S.symbols[0];
    $("symbol").value = S.sym.symbol;
    $("domSym").textContent = S.sym.symbol;
    if (TIMEFRAMES.some(([s]) => s === +q.get("tf"))) S.tf = +q.get("tf");
    setTf(S.tf, false);
    applySettings();
    requestAnimationFrame(frame);

    if (q.get("open") && q.get("date")) return marketOpen(q.get("date"));
    let start = S.bt ? S.bt.current_ts : defaultStart(S.sym);
    if (q.get("date")) start = parseNY(`${q.get("date")}T${RTH_OPEN}`);
    if (q.get("t")) start = +q.get("t");
    start = clampToRange(start);
    $("start").value = toInputNY(start);
    await load(start);
    restoreLive();
    refreshMarkers();
  }

  // ---- drawings ---------------------------------------------------------------

  let cursorMode = "cross", indHidden = false;
  function applyCrosshair() {
    const lines = cursorMode === "cross";
    chart.applyOptions({ crosshair: { vertLine: { visible: lines, labelVisible: true }, horzLine: { visible: lines, labelVisible: true } } });
  }

  const draw = Drawings.create({
    chart, canvas: $("draw"), wrap: document.querySelector(".chart-wrap"),
    series: () => main, times: () => barTimes, barAt: (i) => bars[i], tf: () => S.tf,
    tickSize: () => (S.sym ? S.sym.tick_size : 0.25), pointValue: () => (S.sym ? S.sym.point_value : 1),
    color: () => cfg.drawColor, rr: () => +cfg.rr || 2, status,
    setCursor: (mode) => {
      cursorMode = mode;
      applyCrosshair();
      const wrap = document.querySelector(".chart-wrap");
      wrap.classList.toggle("cur-dot", mode === "dot");
      wrap.classList.toggle("cur-arrow", mode === "arrow");
    },
    onIndicators: (action) => {
      if (action === "remove") { cfg.indicators = []; saveCfg(); syncIndicators(); renderIndMenu(); }
      else { indHidden = !indHidden; for (const sr of Object.values(indSeries)) sr.applyOptions({ visible: !indHidden }); }
      renderLegend(bars.length - 1);
    },
    onMarkers: () => { cfg.markers = !cfg.markers; saveCfg(); refreshMarkers(); status(cfg.markers ? "Trade markers shown" : "Trade markers hidden"); },
  });

  // ---- top bar, menus, settings, replay bar -------------------------------------

  function openDrop(btn, drop) {
    const open = !drop.classList.contains("open");
    document.querySelectorAll(".dropdown.open").forEach((d) => d.classList.remove("open"));
    if (!open) return;
    const r = btn.getBoundingClientRect();
    drop.style.left = r.left + "px";
    drop.style.top = r.bottom + 4 + "px";
    drop.classList.add("open");
  }

  function renderTypeMenu() {
    $("typeBtn").innerHTML = `<svg viewBox="0 0 24 24">${CHART_TYPES[cfg.chartType].icon}</svg>`;
    $("typeDrop").innerHTML = Object.entries(CHART_TYPES).map(([k, v]) =>
      `<button data-type="${k}" class="${k === cfg.chartType ? "on" : ""}"><svg viewBox="0 0 24 24">${v.icon}</svg>${v.label}</button>`).join("");
  }
  function renderIndMenu() {
    $("indDrop").innerHTML = Object.entries(INDICATORS).map(([k, v]) =>
      `<button data-ind="${k}"><span class="chk">${cfg.indicators.includes(k) ? "✓" : ""}</span><span style="color:${v.color}">━</span> ${v.label}</button>`).join("");
  }

  function setupChrome() {
    renderTypeMenu();
    renderIndMenu();
    $("typeBtn").addEventListener("click", (e) => { e.stopPropagation(); openDrop($("typeBtn"), $("typeDrop")); });
    $("indBtn").addEventListener("click", (e) => { e.stopPropagation(); openDrop($("indBtn"), $("indDrop")); });
    document.addEventListener("click", (e) => { if (!e.target.closest(".dropdown")) document.querySelectorAll(".dropdown.open").forEach((d) => d.classList.remove("open")); });
    $("typeDrop").addEventListener("click", (e) => {
      const b = e.target.closest("[data-type]");
      if (!b) return;
      cfg.chartType = b.dataset.type; saveCfg();
      makeMainSeries(); renderTypeMenu();
      $("typeDrop").classList.remove("open");
    });
    $("indDrop").addEventListener("click", (e) => {
      e.stopPropagation(); // the menu re-renders; keep it open for toggling several
      const b = e.target.closest("[data-ind]");
      if (!b) return;
      const id = b.dataset.ind;
      cfg.indicators = cfg.indicators.includes(id) ? cfg.indicators.filter((x) => x !== id) : [...cfg.indicators, id];
      saveCfg(); syncIndicators(); renderIndMenu(); renderLegend(bars.length - 1);
    });

    draw.mountToolbar($("tools"));
    setupTradingUI();

    chart.subscribeCrosshairMove((p) => {
      if (!p || p.time === undefined) { hovering = false; return; }
      const i = barTimes.indexOf(p.time);
      if (i >= 0) { hovering = true; renderLegend(i); }
    });

    $("shotBtn").addEventListener("click", () => {
      const src = chart.takeScreenshot();
      const out = document.createElement("canvas");
      out.width = src.width; out.height = src.height;
      const g = out.getContext("2d");
      g.drawImage(src, 0, 0);
      g.drawImage($("draw"), 0, 0, src.width, src.height);
      const a = document.createElement("a");
      a.href = out.toDataURL("image/png");
      a.download = `${S.sym ? S.sym.symbol : "chart"}-${fmtNY(S.t).replace(/[: ]/g, "-")}.png`;
      a.click();
    });
    $("panelBtn").addEventListener("click", () => { cfg.sidePanel = !cfg.sidePanel; saveCfg(); $("side").hidden = !cfg.sidePanel; });
    $("fullBtn").addEventListener("click", () => {
      if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {});
    });

    // date picker lives in a small dropdown next to the replay buttons
    $("dateBtn").addEventListener("click", (e) => { e.stopPropagation(); openDrop($("dateBtn"), $("dateDrop")); });
    $("dateDrop").addEventListener("click", (e) => e.stopPropagation());
    $("go").addEventListener("click", () => $("dateDrop").classList.remove("open"));
    $("start").addEventListener("keydown", (e) => { if (e.key === "Enter") $("go").click(); });

    // settings dialog
    const dlg = $("settings");
    const fields = () => dlg.querySelectorAll("[data-set]");
    const fill = (src) => fields().forEach((el) => {
      const v = src[el.dataset.set];
      if (el.type === "checkbox") el.checked = !!v; else el.value = v;
    });
    let before = null;
    const preview = () => {
      fields().forEach((el) => { cfg[el.dataset.set] = el.type === "checkbox" ? el.checked : el.value; });
      applySettings();
    };
    $("settingsBtn").addEventListener("click", () => { before = { ...cfg }; fill(cfg); dlg.showModal(); });
    dlg.addEventListener("input", preview);
    dlg.addEventListener("change", preview);
    $("setReset").addEventListener("click", () => {
      fill({ ...DEFAULTS, chartType: cfg.chartType, indicators: cfg.indicators });
      preview();
    });
    $("presets").addEventListener("click", (e) => {
      const b = e.target.closest("[data-preset]");
      if (!b) return;
      fill({ ...cfg, ...THEMES[b.dataset.preset] });
      preview();
    });
    // the dialog can also be opened from the chart's right-click menu
    window.openChartSettings = () => $("settingsBtn").click();
    // the two background colours only matter for a gradient
    const syncBg = () => { dlg.querySelector('[data-set="bg2"]').style.display = dlg.querySelector('[data-set="bgType"]').value === "gradient" ? "" : "none"; };
    dlg.addEventListener("change", syncBg);
    $("settingsBtn").addEventListener("click", syncBg);
    $("setTabs").addEventListener("click", (e) => {
      const t = e.target.dataset.tab;
      if (!t) return;
      for (const b of $("setTabs").children) b.classList.toggle("on", b.dataset.tab === t);
      dlg.querySelectorAll(".set-pane").forEach((p) => { p.hidden = p.dataset.pane !== t; });
    });
    dlg.addEventListener("close", () => {
      if (dlg.returnValue === "ok") saveCfg();
      else if (before) { cfg = before; applySettings(); renderTypeMenu(); }
    });
  }

  // ---- trading UI: DOM, order labels, ⊕ at the axis, tabs, nav -------------------

  function setupTradingUI() {
    // app nav + version
    const nav = $("nav");
    try { if (localStorage.getItem("tickreplay.navMin") === "1") nav.classList.add("min"); } catch { /* ignore */ }
    $("navCollapse").addEventListener("click", () => {
      nav.classList.toggle("min");
      try { localStorage.setItem("tickreplay.navMin", nav.classList.contains("min") ? "1" : "0"); } catch { /* ignore */ }
    });
    fetch("version.json").then((r) => r.json()).then((v) => { $("ver").textContent = v.version === "dev" ? "dev build" : "v" + v.version; }).catch(() => {});
    $("settingsBtn2").addEventListener("click", () => $("settingsBtn").click());

    // lots
    $("qtyUp").addEventListener("click", () => { $("qty").value = Math.min(100, lots() + 1); });
    $("qtyDown").addEventListener("click", () => { $("qty").value = Math.max(1, lots() - 1); });
    $("quickQty").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") $("qty").value = e.target.textContent; });
    // bracket settings are remembered
    try {
      const br = JSON.parse(localStorage.getItem("tickreplay.bracket") || "null");
      if (br) { $("brOn").checked = br.on; $("brTp").value = br.tp; $("brSl").value = br.sl; }
    } catch { /* ignore */ }
    const saveBr = () => { try { localStorage.setItem("tickreplay.bracket", JSON.stringify({ on: $("brOn").checked, tp: $("brTp").value, sl: $("brSl").value })); } catch { /* ignore */ } };
    ["brOn", "brTp", "brSl"].forEach((id) => $(id).addEventListener("change", saveBr));

    // DOM / Order tabs
    document.querySelector(".dom-tabs").addEventListener("click", (e) => {
      const t = e.target.dataset.dtab;
      if (!t) return;
      document.querySelectorAll(".dom-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.dtab === t));
      document.querySelectorAll(".dpane").forEach((p) => { p.hidden = p.dataset.dpane !== t; });
      if (t === "order" && S.last !== null && !$("ordPrice").value) $("ordPrice").value = S.last.toFixed(2);
    });
    $("ordType").addEventListener("click", (e) => {
      const t = e.target.dataset.otype;
      if (!t) return;
      $("ordType").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.otype === t));
      $("ordHint").textContent = t === "market" ? "Market orders fill at the ask (buy) or bid (sell)."
        : t === "limit" ? "Buy limits go below the market, sell limits above. They fill when price trades through."
        : "Buy stops go above the market, sell stops below. They fill at the trade that triggers them (slippage included).";
      if (S.last !== null) $("ordPrice").value = S.last.toFixed(2);
    });

    // ladder: click My Bid / My Ask to place, right-click to cancel, wheel to scroll
    $("ladder").addEventListener("click", (e) => {
      const cell = e.target.closest(".mb, .ma"), row = e.target.closest(".lrow");
      if (!cell || !row) return;
      placeAt(cell.classList.contains("mb") ? 1 : -1, +row.dataset.p);
    });
    $("ladder").addEventListener("contextmenu", (e) => {
      const cell = e.target.closest(".mb, .ma"), row = e.target.closest(".lrow");
      if (!cell || !row) return;
      e.preventDefault();
      const side = cell.classList.contains("mb") ? 1 : -1, p = +row.dataset.p;
      TR.orders = TR.orders.filter((o) => !(o.side === side && Math.abs(o.price - p) < tick() / 2));
      ordersDirty = true; render(true);
    });
    $("ladder").addEventListener("wheel", (e) => {
      e.preventDefault();
      $("domCenter").checked = false;
      domCenterPx = roundTick((domCenterPx ?? S.last ?? 0) + (e.deltaY < 0 ? 3 : -3) * tick());
      renderLadder();
    }, { passive: false });

    // bottom tabs
    document.querySelector(".btabs-head").addEventListener("click", (e) => {
      const t = e.target.closest("[data-btab]");
      if (!t) return;
      btab = t.dataset.btab;
      document.querySelectorAll("[data-btab]").forEach((b) => b.classList.toggle("on", b.dataset.btab === btab));
      $("btabs").classList.remove("min");
      renderBottom();
    });
    $("btabsToggle").addEventListener("click", () => $("btabs").classList.toggle("min"));

    // cancel / position actions anywhere (labels, tables)
    document.addEventListener("click", (e) => {
      const c = e.target.closest("[data-cancel]");
      if (c) { cancelOrder(+c.dataset.cancel); render(true); return; }
      const a = e.target.closest("[data-pact]");
      if (!a) return;
      const act = a.dataset.pact, side = Math.sign(S.pos.qty), q = Math.abs(S.pos.qty);
      if (!side) return;
      if (act === "close") closePosition();
      if (act === "rev") reversePosition();
      if (act === "tp") addOrder({ side: -side, type: "limit", price: S.pos.avg + side * (+$("brTp").value || 40) * tick(), qty: q, role: "tp", oco: "pos" + TR.seq });
      if (act === "sl") addOrder({ side: -side, type: "stop", price: S.pos.avg - side * (+$("brSl").value || 20) * tick(), qty: q, role: "sl", oco: "pos" + TR.seq });
      render(true);
    });

    // drag order labels to move the order
    const layer = $("ordersLayer"), wrap = document.querySelector(".chart-wrap");
    layer.addEventListener("mousedown", (e) => {
      layerBusy = true;
      const el = e.target.closest(".ord");
      if (!el || e.target.closest("[data-cancel],[data-pact]") || el.dataset.key === "pos") return;
      e.preventDefault();
      const o = TR.orders.find((x) => x.id === +el.dataset.id);
      if (!o) return;
      dragOrd = { key: el.dataset.key, o, price: o.price };
      el.classList.add("drag");
    });
    addEventListener("mousemove", (e) => {
      if (!dragOrd) return;
      const y = e.clientY - wrap.getBoundingClientRect().top;
      const p = main.coordinateToPrice(y);
      if (p !== null) dragOrd.price = roundTick(p);
    });
    addEventListener("mouseup", () => {
      layerBusy = false;
      if (!dragOrd) return;
      const { o, price } = dragOrd;
      dragOrd = null;
      const q = refPx(o.side);
      // an entry dragged across the market switches between limit and stop, like on a real DOM
      if (o.role === "entry" && S.last !== null) o.type = o.side > 0 ? (price <= q ? "limit" : "stop") : (price >= q ? "limit" : "stop");
      if (o.role === "tp" && S.pos.qty && (price - S.pos.avg) * Math.sign(S.pos.qty) <= 0) o.type = "stop";
      o.price = price;
      ordersDirty = true;
      render(true);
    });

    // ⊕ next to the price axis: place an order at the hovered price
    const plus = $("axisPlus"), menu = $("orderMenu");
    let plusPrice = null;
    wrap.addEventListener("mousemove", (e) => {
      if (!main || !menu.hidden || dragOrd) return;
      const r = wrap.getBoundingClientRect(), y = e.clientY - r.top, x = e.clientX - r.left;
      const w = chart.timeScale().width();
      const p = y < $("chart").clientHeight - 28 ? main.coordinateToPrice(y) : null;
      if (p === null || x > w + 2 || e.target.closest(".ord, .axis-plus")) {
        if (!e.target.closest(".axis-plus")) plus.hidden = true;
        return;
      }
      plusPrice = roundTick(p);
      plus.hidden = false;
      $("axisPlusPx").textContent = plusPrice.toFixed(2);
      plus.style.top = main.priceToCoordinate(plusPrice) + "px";
      plus.style.left = w - plus.offsetWidth - 4 + "px";
    });
    wrap.addEventListener("mouseleave", () => { plus.hidden = true; });
    plus.addEventListener("mousedown", (e) => e.stopPropagation());
    plus.addEventListener("click", (e) => {
      e.stopPropagation();
      if (plusPrice === null || S.last === null) return;
      const p = plusPrice, q = lots(), px = p.toFixed(2);
      const buyType = p <= refPx(1) ? "Limit" : "Stop", sellType = p >= refPx(-1) ? "Limit" : "Stop";
      menu.innerHTML = `<button data-om="1"><span class="b">Buy ${buyType} ${q}</span><span class="px">@ ${px}</span></button>
        <button data-om="-1"><span class="s">Sell ${sellType} ${q}</span><span class="px">@ ${px}</span></button>
        ${S.pos.qty ? `<button data-om="exit"><span>${(p - S.pos.avg) * Math.sign(S.pos.qty) > 0 ? "Take profit" : "Stop loss"} for position</span><span class="px">@ ${px}</span></button>` : ""}
        <div class="sepl"></div><button data-om="settings"><span>⚙ Chart settings…</span><span class="px">colours · grid</span></button>`;
      menu.hidden = false;
      menu.style.top = plus.offsetTop + 14 + "px";
      menu.style.left = Math.max(8, plus.offsetLeft - 150) + "px";
      menu.onclick = (ev) => {
        const b = ev.target.closest("[data-om]");
        if (!b) return;
        if (b.dataset.om === "settings") { menu.hidden = true; return window.openChartSettings(); }
        if (b.dataset.om === "exit") {
          const side = Math.sign(S.pos.qty), profit = (p - S.pos.avg) * side > 0;
          addOrder({ side: -side, type: profit ? "limit" : "stop", price: p, qty: Math.abs(S.pos.qty), role: profit ? "tp" : "sl" });
        } else placeAt(+b.dataset.om, p);
        menu.hidden = true;
        render(true);
      };
    });
    document.addEventListener("mousedown", (e) => { if (!menu.hidden && !menu.contains(e.target)) menu.hidden = true; });

    // right-click on empty chart space: same order menu at that price (drawings keep their own menu)
    wrap.addEventListener("contextmenu", (e) => {
      if (e.defaultPrevented || !main || S.last === null) return;
      const r = wrap.getBoundingClientRect(), y = e.clientY - r.top;
      const p = main.coordinateToPrice(y);
      if (p === null || e.clientX - r.left > chart.timeScale().width()) return;
      e.preventDefault();
      plusPrice = roundTick(p);
      plus.style.top = main.priceToCoordinate(plusPrice) + "px";
      plus.click();
      menu.style.left = Math.min(e.clientX - r.left, r.width - 240) + "px";
      menu.style.top = y + 6 + "px";
    });
  }

  // tells the desktop program a window is still open
  const ping = () => fetch("/api/ping").catch(() => {});
  ping();
  setInterval(ping, 20000);

  init().catch((e) => boot.on ? boot.fail(/session not found/.test(e.message) ? "This session no longer exists. It may have been deleted." : e.message) : status("Startup failed: " + e.message, 0));
})();
