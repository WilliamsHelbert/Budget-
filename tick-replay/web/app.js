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
    bg: "#0b0e14", grid: "both", gridColor: "#1a1f2b", crosshair: "normal", crossColor: "#758696",
    watermark: "hidden", text: "#b2b5be", fontSize: "12", scaleLine: "#242b39", rightOffset: 8,
    sidePanel: true, markers: true, drawColor: "#2962ff", rr: 2,
    chartType: "candles", indicators: [],
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
    main.setData(bars.map(mainPoint));
    refreshMarkers();
  }

  function applySettings() {
    const g = cfg.grid;
    chart.applyOptions({
      layout: { background: { color: cfg.bg }, textColor: cfg.text, fontSize: +cfg.fontSize },
      grid: { vertLines: { visible: g === "both" || g === "vert", color: cfg.gridColor }, horzLines: { visible: g === "both" || g === "horz", color: cfg.gridColor } },
      crosshair: {
        mode: cfg.crosshair === "magnet" ? LightweightCharts.CrosshairMode.Magnet : LightweightCharts.CrosshairMode.Normal,
        vertLine: { color: cfg.crossColor, labelBackgroundColor: "#2a2e39" }, horzLine: { color: cfg.crossColor, labelBackgroundColor: "#2a2e39" },
      },
      rightPriceScale: { borderColor: cfg.scaleLine },
      timeScale: { borderColor: cfg.scaleLine, rightOffset: +cfg.rightOffset },
      watermark: {
        visible: cfg.watermark === "symbol", color: "rgba(255,255,255,.06)", fontSize: 64,
        text: S.sym ? `${S.sym.symbol} · ${tfLabel(S.tf)}` : "",
      },
    });
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
        indSeries[id] = chart.addLineSeries({ color: INDICATORS[id].color, lineWidth: id === "vwap" ? 2 : 1.5, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
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
    // colour by aggressor when the data has it, else by uptick/downtick
    S.tape.push([ts, px, sz, side || S.lastDir, side !== 0]);
    if (S.tape.length > TAPE_ROWS * 2) S.tape.splice(0, S.tape.length - TAPE_ROWS);
    S.dirty = true;
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

  async function load(t) {
    S.playing = false;
    S.t = t;
    S.buf = newBuffer(t);
    S.dispOffset = nyOffsetSec(t);
    const buf = S.buf;
    const hist = await api(`/api/candles?symbol=${encodeURIComponent(S.sym.symbol)}&tf=${S.tf}&end=${t}&count=${HISTORY_CANDLES}`);
    if (buf !== S.buf) return;
    bars.length = 0;
    barTimes.length = 0;
    for (const c of hist) {
      bars.push({ time: dispTime(c.time), open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume });
      barTimes.push(dispTime(c.time));
    }
    main.setData(bars.map(mainPoint));
    volume.setData(bars.map((b) => ({ time: b.time, value: b.volume, color: volColor(b) })));
    for (const id of Object.keys(indSeries)) recomputeIndicator(id);
    draw.load(`tickreplay.drawings.${S.bt ? S.bt.id : "free"}.${S.sym.symbol}`);
    chart.applyOptions({ watermark: { text: `${S.sym.symbol} · ${tfLabel(S.tf)}` } });
    const lastC = hist[hist.length - 1];
    S.bar = lastC ? { bucket: lastC.time, open: lastC.open, high: lastC.high, low: lastC.low, close: lastC.close, volume: lastC.volume } : null;
    S.firstBucket = hist.length ? hist[0].time : null;
    S.last = lastC ? lastC.close : null;
    S.bid = S.ask = null;
    S.dirty = false;
    S.tape = [];
    refreshMarkers();
    chart.timeScale().scrollToRealTime();
    fetchMore();
    render(true);
  }

  // ---- trading --------------------------------------------------------------

  function order(signedQty) {
    if (S.last === null) return status("No price yet");
    // with quotes, market orders pay the spread: buys fill at the ask, sells at the bid
    const quoted = S.bid !== null && S.ask !== null;
    const pos = S.pos, px = quoted ? (signedQty > 0 ? S.ask : S.bid) : S.last, pv = S.sym.point_value;
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
    refreshMarkers();
    render(true);
  }

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
    let html = `<div class="l1"><span class="name">${S.sym.symbol} · ${tfLabel(S.tf)}</span>
      <span>O ${v(b.open)}</span><span>H ${v(b.high)}</span><span>L ${v(b.low)}</span><span>C ${v(b.close)}</span>
      <span style="color:${c}">${chg >= 0 ? "+" : ""}${chg.toFixed(2)}</span><span>Vol <b>${b.volume.toLocaleString("en-US")}</b></span></div>`;
    const ind = Object.keys(indSeries).map((id) => {
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

    const pos = S.pos, pv = S.sym ? S.sym.point_value : 1;
    const open = pos.qty && S.last !== null ? (S.last - pos.avg) * pos.qty * pv : 0;
    $("last").textContent = S.last === null ? "--" : S.last.toFixed(2);
    $("last").className = "last " + (S.lastDir > 0 ? "pos" : S.lastDir < 0 ? "neg" : "");
    $("posQty").textContent = pos.qty;
    $("posAvg").textContent = pos.qty ? pos.avg.toFixed(2) : "--";
    $("pnlOpen").textContent = money(open);
    $("pnlOpen").className = open > 0 ? "pos" : open < 0 ? "neg" : "";
    $("pnlClosed").textContent = money(pos.realized);
    $("pnlClosed").className = pos.realized > 0 ? "pos" : pos.realized < 0 ? "neg" : "";
    $("fills").textContent = pos.fills.length;
    if (S.bt) {
      const bal = S.bt.balance + pos.realized + open;
      $("balance").textContent = money(bal);
      $("balance").className = bal > S.bt.balance ? "pos" : bal < S.bt.balance ? "neg" : "";
    }

    const rows = S.tape.slice(-TAPE_ROWS).reverse();
    $("tape").innerHTML = rows.map(([ts, px, sz, dir, aggr]) =>
      `<tr class="${dir > 0 ? "up" : dir < 0 ? "down" : ""}${aggr && sz >= BIG_PRINT ? " big" : ""}"><td>${fmtNY(ts, false)}</td><td>${px.toFixed(2)}</td><td>${sz}</td></tr>`
    ).join("");
    $("quote").textContent = S.bid !== null ? `${S.bid.toFixed(2)} × ${S.ask.toFixed(2)}` : "--";
    $("askLbl").textContent = S.ask !== null ? S.ask.toFixed(2) : S.last !== null ? S.last.toFixed(2) : "";
    $("bidLbl").textContent = S.bid !== null ? S.bid.toFixed(2) : S.last !== null ? S.last.toFixed(2) : "";
    $("bbPos").innerHTML = pos.qty
      ? `<span class="${pos.qty > 0 ? "pos" : "neg"}">${pos.qty > 0 ? "LONG" : "SHORT"} ${Math.abs(pos.qty)} @ ${pos.avg.toFixed(2)}</span> · <span class="${open > 0 ? "pos" : open < 0 ? "neg" : ""}">${money(open)}</span>`
      : "";
    if (S.bt) {
      const bal = S.bt.balance + pos.realized + open;
      $("bbBalance").hidden = false;
      $("bbBalance").textContent = money(bal);
    }
    $("fillNote").textContent = S.bid !== null
      ? "Market orders fill at the ask (buy) / bid (sell)."
      : "No bid/ask in this data: market orders fill at the last trade.";
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
    for (const b of $("tfs").children) b.classList.toggle("active", +b.dataset.tf === tf);
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
    if (t < S.sym.first_ts || t > S.sym.last_ts) return status(`No ${S.sym.symbol} data around the open on ${day}`, 4000);
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
    $("tfs").innerHTML = TIMEFRAMES.map(([s, l]) => `<button data-tf="${s}">${l}</button>`).join("");
    $("tfs").addEventListener("click", (e) => { if (e.target.dataset.tf) setTf(+e.target.dataset.tf); });
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
    $("buy").addEventListener("click", () => order(Math.max(1, +$("qty").value | 0)));
    $("sell").addEventListener("click", () => order(-Math.max(1, +$("qty").value | 0)));
    $("flat").addEventListener("click", () => { if (S.pos.qty) order(-S.pos.qty); });
    $("symbol").addEventListener("change", (e) => {
      if (S.pos.qty !== 0) {
        e.target.value = S.sym.symbol;
        return status("Close your position before switching symbol", 3000);
      }
      S.sym = S.symbols.find((s) => s.symbol === e.target.value);
      S.pos = { qty: 0, avg: 0, realized: S.bt ? S.pos.realized : 0, fills: [], openTs: 0 };
      const t = clampToRange(S.t);
      $("start").value = toInputNY(t);
      load(t);
    });

    setupChrome();

    document.addEventListener("keydown", (e) => {
      if (draw.onKey(e)) { e.preventDefault(); return; }
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
      if (e.code === "Space") { e.preventDefault(); togglePlay(); }
      else if (e.code === "ArrowRight") { e.preventDefault(); e.shiftKey ? stepBar() : stepTick(); }
      else if (e.key === "b" || e.key === "B") $("buy").click();
      else if (e.key === "s" || e.key === "S") $("sell").click();
      else if (e.key === "f" || e.key === "F") $("flat").click();
    });

    S.symbols = await api("/api/symbols");
    if (!S.symbols.length) {
      status("No tick data yet. Go to the start page (Home) to import your tick files.", 0);
      return;
    }
    // URL options: ?bt=<session id> or ?symbol=NQ&date=2024-03-05&open=1&tf=60&t=<ms>
    const q = new URLSearchParams(location.search);
    if (q.get("bt")) {
      S.bt = await api(`/api/backtests/${encodeURIComponent(q.get("bt"))}`);
      S.symbols = S.symbols.filter((s) => S.bt.symbols.includes(s.symbol));
      if (!S.symbols.length) return status("The data for this session's symbols was deleted.", 0);
      S.pos.realized = S.bt.trades.reduce((a, t) => a + t.pnl, 0);
      $("btName").textContent = S.bt.name;
      $("btName").hidden = false;
      $("balanceRow").hidden = false;
      $("balanceRowVal").hidden = false;
      $("homeLink").href = "./#sessions";
      document.title = `${S.bt.name} · Tick Replay`;
      setInterval(saveProgress, 10000);
      addEventListener("pagehide", saveProgressOnExit);
    }
    $("symbol").innerHTML = S.symbols.map((s) => `<option>${s.symbol}</option>`).join("");
    const wanted = (q.get("symbol") || (S.bt && S.bt.current_symbol) || "").toUpperCase();
    S.sym = S.symbols.find((s) => s.symbol === wanted) || S.symbols[0];
    $("symbol").value = S.sym.symbol;
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
  }

  // ---- drawings ---------------------------------------------------------------

  const draw = Drawings.create({
    chart, canvas: $("draw"), wrap: document.querySelector(".chart-wrap"),
    series: () => main, times: () => barTimes, barAt: (i) => bars[i], tf: () => S.tf,
    tickSize: () => (S.sym ? S.sym.tick_size : 0.25), pointValue: () => (S.sym ? S.sym.point_value : 1),
    color: () => cfg.drawColor, rr: () => +cfg.rr || 2, status,
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
    $("qtyUp").addEventListener("click", () => { $("qty").value = Math.min(100, (+$("qty").value || 1) + 1); });
    $("qtyDown").addEventListener("click", () => { $("qty").value = Math.max(1, (+$("qty").value || 1) - 1); });

    // draggable replay bar
    const rb = $("replayBar");
    $("grip").addEventListener("mousedown", (e) => {
      e.preventDefault();
      const wrap = rb.parentElement.getBoundingClientRect(), r = rb.getBoundingClientRect();
      const dx = e.clientX - r.left, dy = e.clientY - r.top;
      const move = (ev) => {
        rb.style.transform = "none";
        rb.style.left = Math.max(0, Math.min(wrap.width - r.width, ev.clientX - wrap.left - dx)) + "px";
        rb.style.top = Math.max(0, Math.min(wrap.height - r.height, ev.clientY - wrap.top - dy)) + "px";
      };
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move);
      addEventListener("mouseup", up);
    });

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

  // tells the desktop program a window is still open
  const ping = () => fetch("/api/ping").catch(() => {});
  ping();
  setInterval(ping, 20000);

  init().catch((e) => status("Startup failed: " + e.message, 0));
})();
