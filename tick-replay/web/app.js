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
    lastDir: 0,
    tape: [],
    dirty: false,
    buf: null,
    pos: { qty: 0, avg: 0, realized: 0, fills: [] },
  };

  function newBuffer(t) {
    return { gen: (S.buf ? S.buf.gen : 0) + 1, ts: [], price: [], size: [], i: 0, covered: t, nextTs: null, eof: false, pending: null };
  }

  // ---- chart ----------------------------------------------------------------

  const chart = LightweightCharts.createChart($("chart"), {
    autoSize: true,
    localization: { locale: "en-US" },
    layout: { background: { color: "#131722" }, textColor: "#d1d4dc" },
    grid: { vertLines: { color: "#1e222d" }, horzLines: { color: "#1e222d" } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#2a2e39" },
    timeScale: { borderColor: "#2a2e39", timeVisible: true, secondsVisible: true, rightOffset: 8 },
  });
  const candles = chart.addCandlestickSeries({
    upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
    wickUpColor: "#26a69a", wickDownColor: "#ef5350",
  });
  const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
  volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  let avgLine = null;

  const bucketOf = (ms) => Math.floor(ms / 1000 / S.tf) * S.tf;
  const dispTime = (bucket) => bucket + S.dispOffset;
  const volBar = (b) => ({ time: dispTime(b.bucket), value: b.volume, color: b.close >= b.open ? "rgba(38,166,154,.45)" : "rgba(239,83,80,.45)" });

  function pushBar(b) {
    const d = { time: dispTime(b.bucket), open: b.open, high: b.high, low: b.low, close: b.close };
    candles.update(d);
    volume.update(volBar(b));
  }

  function applyTick(ts, px, sz) {
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
    S.tape.push([ts, px, sz, S.lastDir]);
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
      applyTick(buf.ts[buf.i], buf.price[buf.i], buf.size[buf.i]);
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
    candles.setData(hist.map((c) => ({ time: dispTime(c.time), open: c.open, high: c.high, low: c.low, close: c.close })));
    volume.setData(hist.map((c) => volBar({ bucket: c.time, ...c })));
    const lastC = hist[hist.length - 1];
    S.bar = lastC ? { bucket: lastC.time, open: lastC.open, high: lastC.high, low: lastC.low, close: lastC.close, volume: lastC.volume } : null;
    S.firstBucket = hist.length ? hist[0].time : null;
    S.last = lastC ? lastC.close : null;
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
    const pos = S.pos, px = S.last, pv = S.sym.point_value;
    const p = pos.qty, q = signedQty;
    if (p === 0 || Math.sign(p) === Math.sign(q)) {
      pos.avg = (pos.avg * Math.abs(p) + px * Math.abs(q)) / Math.abs(p + q);
    } else {
      const closing = Math.min(Math.abs(q), Math.abs(p));
      pos.realized += closing * (px - pos.avg) * Math.sign(p) * pv;
      if (Math.abs(q) > Math.abs(p)) pos.avg = px; // flipped
    }
    pos.qty = p + q;
    if (pos.qty === 0) pos.avg = 0;
    pos.fills.push({ t: S.t, qty: q, px });
    refreshMarkers();
    render(true);
  }

  function refreshMarkers() {
    const cur = S.bar ? S.bar.bucket : Infinity;
    const markers = S.pos.fills
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
    candles.setMarkers(markers);

    if (avgLine) { candles.removePriceLine(avgLine); avgLine = null; }
    if (S.pos.qty !== 0) {
      avgLine = candles.createPriceLine({
        price: S.pos.avg, color: S.pos.qty > 0 ? "#26a69a" : "#ef5350",
        lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true,
        title: `${S.pos.qty > 0 ? "LONG" : "SHORT"} ${Math.abs(S.pos.qty)}`,
      });
    }
  }

  // ---- render ---------------------------------------------------------------

  let lastPanelRender = 0;

  function render(force = false) {
    if (S.dirty && S.bar) {
      pushBar(S.bar);
      S.dirty = false;
    }
    $("clock").textContent = S.sym ? fmtNY(S.t) : "--";
    $("countdown").textContent = S.sym ? openCountdown(S.t) : "";
    $("play").textContent = S.playing ? "❚❚" : "▶";

    const now = performance.now();
    if (!force && now - lastPanelRender < 100) return; // DOM panels at ~10 fps
    lastPanelRender = now;

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

    const rows = S.tape.slice(-TAPE_ROWS).reverse();
    $("tape").innerHTML = rows.map(([ts, px, sz, dir]) =>
      `<tr class="${dir > 0 ? "up" : dir < 0 ? "down" : ""}"><td>${fmtNY(ts, false)}</td><td>${px.toFixed(2)}</td><td>${sz}</td></tr>`
    ).join("");
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
    if (S.playing && S.buf) {
      const buf = S.buf;
      maybeSkipGap();
      consumeUpTo(S.t + dt * S.speed);
      maybeSkipGap();
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
    applyTick(buf.ts[buf.i], buf.price[buf.i], buf.size[buf.i]);
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
      load(parseNY($("start").value));
    });
    $("marketOpen").addEventListener("click", () => {
      const day = ($("start").value || toInputNY(S.t)).slice(0, 10);
      marketOpen(day).catch((e) => status("Load failed: " + e.message, 5000));
    });
    $("buy").addEventListener("click", () => order(Math.max(1, +$("qty").value | 0)));
    $("sell").addEventListener("click", () => order(-Math.max(1, +$("qty").value | 0)));
    $("flat").addEventListener("click", () => { if (S.pos.qty) order(-S.pos.qty); });
    $("symbol").addEventListener("change", (e) => {
      S.sym = S.symbols.find((s) => s.symbol === e.target.value);
      S.pos = { qty: 0, avg: 0, realized: 0, fills: [] };
      const t = Math.min(Math.max(S.t, S.sym.first_ts), S.sym.last_ts);
      $("start").value = toInputNY(t);
      load(t);
    });

    document.addEventListener("keydown", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
      if (e.code === "Space") { e.preventDefault(); togglePlay(); }
      else if (e.code === "ArrowRight") { e.preventDefault(); e.shiftKey ? stepBar() : stepTick(); }
      else if (e.key === "b" || e.key === "B") $("buy").click();
      else if (e.key === "s" || e.key === "S") $("sell").click();
      else if (e.key === "f" || e.key === "F") $("flat").click();
    });

    S.symbols = await api("/api/symbols");
    if (!S.symbols.length) {
      status("No tick data found. Run tools/make_sample.py or tools/import_ticks.py first.", 0);
      return;
    }
    // URL options from the start page: ?symbol=NQ&date=2024-03-05&open=1&tf=60&t=<ms>
    const q = new URLSearchParams(location.search);
    $("symbol").innerHTML = S.symbols.map((s) => `<option>${s.symbol}</option>`).join("");
    S.sym = S.symbols.find((s) => s.symbol === (q.get("symbol") || "").toUpperCase()) || S.symbols[0];
    $("symbol").value = S.sym.symbol;
    if (TIMEFRAMES.some(([s]) => s === +q.get("tf"))) S.tf = +q.get("tf");
    setTf(S.tf, false);
    requestAnimationFrame(frame);

    if (q.get("open") && q.get("date")) return marketOpen(q.get("date"));
    let start = defaultStart(S.sym);
    if (q.get("date")) start = parseNY(`${q.get("date")}T${RTH_OPEN}`);
    if (q.get("t")) start = +q.get("t");
    start = Math.min(Math.max(start, S.sym.first_ts), S.sym.last_ts);
    $("start").value = toInputNY(start);
    await load(start);
  }

  init().catch((e) => status("Startup failed: " + e.message, 0));
})();
