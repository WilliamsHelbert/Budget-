/* Drawing tools for Lightweight Charts (which has none built in).
 *
 * Drawings live in chart space: time (display seconds, same axis as the candles) and
 * price. They are painted on a canvas over the chart every frame, so they follow
 * panning, zooming and live candles. Time <-> x goes through the candles' logical
 * index, which also works to the right of the last candle and across timeframes.
 *
 * The toolbar works like TradingView's: each button is a group that remembers the last
 * tool used from it, and a › flyout lists every tool in the group.
 */
(() => {
  "use strict";

  const HIT = 6;          // px tolerance for picking lines
  const HANDLE = 5;       // handle radius
  const SWATCHES = ["#2962ff", "#f5a623", "#26a69a", "#ef5350", "#e040fb", "#ffffff", "#9598a1", "#000000"];
  // Fibonacci levels as TradingView lists them: value, colour, shown by default
  const lv = (list) => list.map(([v, c, on]) => ({ v, c, on }));
  const FIB_LEVELS = lv([
    [-0.618, "#9c27b0", false], [-0.272, "#673ab7", false], [0, "#787b86", true], [0.236, "#f23645", true],
    [0.382, "#ff9800", true], [0.5, "#4caf50", true], [0.618, "#089981", true], [0.705, "#00bcd4", false],
    [0.786, "#00bcd4", true], [1, "#787b86", true], [1.272, "#2962ff", false], [1.414, "#f23645", false],
    [1.618, "#2962ff", true], [2, "#9c27b0", false], [2.618, "#f23645", false], [3.618, "#9c27b0", false], [4.236, "#e91e63", false],
  ]);
  const FIBEXT_LEVELS = lv([
    [0, "#787b86", true], [0.382, "#f23645", false], [0.5, "#ff9800", false], [0.618, "#f23645", true], [1, "#ff9800", true],
    [1.272, "#4caf50", true], [1.414, "#089981", false], [1.618, "#089981", true], [2, "#00bcd4", true], [2.618, "#2962ff", true],
    [3.618, "#9c27b0", false], [4.236, "#e91e63", false],
  ]);
  const FIB_OPTS = { fibExtLeft: false, fibExtRight: false, fibReverse: false, fibPrices: true, fibLevelsFmt: "values", fibLabels: "left", fibFill: true, fibFillOpacity: 0.08, fibTrend: true };
  const DASH = { 0: [], 1: [2, 3], 2: [7, 5] };
  const LINE_TYPES = new Set(["trend", "ray", "info", "extended", "angle", "arrowline", "hline", "hray", "vline", "crossline"]);
  const TEXT_ON = new Set(["trend", "ray", "info", "extended", "arrowline", "hline", "hray", "vline", "rect", "channel"]);
  const TPL_KEY = "tickreplay.drawTemplates", DEF_KEY = "tickreplay.drawDefaults";
  const readJSON = (k) => { try { return JSON.parse(localStorage.getItem(k) || "{}"); } catch { return {}; } };
  const writeJSON = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };
  const clone = (x) => JSON.parse(JSON.stringify(x));
  /** Everything about a drawing's look (what templates store): not its id, type or position. */
  const styleOf = (d) => { const s = clone(d); delete s.id; delete s.type; delete s.pts; delete s.target; delete s.emoji; return s; };
  const EMOJIS = ["🚀", "🔥", "✅", "❌", "⚠️", "💰", "📈", "📉", "🎯", "⭐", "👍", "👎", "😀", "😬", "🤔", "💡", "🔔", "🛑", "⏰", "📰"];

  // ---- icons (28×28, stroked) ----------------------------------------------------
  const I = {
    cross: '<path d="M14 4v20M4 14h20"/>',
    dot: '<circle cx="14" cy="14" r="2.5" fill="currentColor"/>',
    arrow: '<path d="M8 5l13 8-6 1.8L12 21z"/>',
    eraser: '<path d="M6 19l9-10 7 6-7 8H9z"/><path d="M11 13l6 5M5 23h18"/>',
    trend: '<path d="M6 22 22 6"/><circle cx="6" cy="22" r="2"/><circle cx="22" cy="6" r="2"/>',
    ray: '<path d="M6 21 25 7"/><circle cx="6" cy="21" r="2"/><circle cx="14" cy="15" r="2"/>',
    info: '<path d="M5 21 20 8"/><circle cx="5" cy="21" r="2"/><circle cx="20" cy="8" r="2"/><rect x="15" y="16" width="9" height="6" rx="1"/>',
    extended: '<path d="M3 24 25 4"/><circle cx="10" cy="18" r="2"/><circle cx="18" cy="11" r="2"/>',
    angle: '<path d="M5 21 21 9M5 21h17"/><path d="M13 21a8 8 0 0 0-1.4-4.5"/>',
    hline: '<path d="M3 14h22"/><circle cx="14" cy="14" r="2"/>',
    hray: '<path d="M8 14h17"/><circle cx="8" cy="14" r="2"/>',
    vline: '<path d="M14 3v22"/><circle cx="14" cy="14" r="2"/>',
    crossline: '<path d="M14 3v22M3 14h22"/><circle cx="14" cy="14" r="2"/>',
    channel: '<path d="M4 17 18 7M10 23 24 13"/><circle cx="4" cy="17" r="1.8"/><circle cx="18" cy="7" r="1.8"/><circle cx="24" cy="13" r="1.8"/>',
    rect: '<rect x="5" y="8" width="18" height="12" rx="1"/><circle cx="5" cy="8" r="1.8"/><circle cx="23" cy="20" r="1.8"/>',
    fib: '<path d="M4 6h20M4 11h20M4 16h20M4 21h20"/><path d="M6 21 22 6" stroke-dasharray="2 2"/>',
    fibext: '<path d="M4 8h20M4 13h20M4 18h20"/><path d="M5 22l6-12 6 8" stroke-dasharray="2 2"/>',
    xabcd: '<path d="M3 20l5-12 5 8 5-10 7 12"/><circle cx="3" cy="20" r="1.6"/><circle cx="25" cy="18" r="1.6"/>',
    abcd: '<path d="M4 20l7-12 6 7 7-10"/><circle cx="4" cy="20" r="1.6"/><circle cx="24" cy="5" r="1.6"/>',
    triangle: '<path d="M4 21 12 6l12 13z"/>',
    long: '<rect x="5" y="5" width="18" height="9" fill="rgba(38,166,154,.35)" stroke="#26a69a"/><rect x="5" y="14" width="18" height="8" fill="rgba(239,83,80,.3)" stroke="#ef5350"/>',
    short: '<rect x="5" y="6" width="18" height="8" fill="rgba(239,83,80,.3)" stroke="#ef5350"/><rect x="5" y="14" width="18" height="9" fill="rgba(38,166,154,.35)" stroke="#26a69a"/>',
    daterange: '<path d="M6 5v18M22 5v18M9 14h10M16 11l3 3-3 3"/>',
    pricerange: '<path d="M5 6h18M5 22h18M14 9v10M11 16l3 3 3-3"/>',
    measure: '<path d="M5 23 23 5M8 23l-3-3M12 19l-2-2M16 15l-2-2M20 11l-2-2"/>',
    brush: '<path d="M5 22c3 0 4-2 4-4 0-1.6 1-3 3-3 1.5 0 2.5 1 2.5 2.5C14.5 20 12 22 9 22"/><path d="M13 15 23 5"/>',
    highlighter: '<path d="M9 19l-3 4h6l1-2M9 19l9-11 4 3-9 11z"/>',
    text: '<path d="M7 8V6h14v2M14 6v16M11 22h6"/>',
    callout: '<path d="M5 6h18v11H13l-5 5v-5H5z"/>',
    pricelabel: '<path d="M4 9h14l6 5-6 5H4z"/>',
    arrowline: '<path d="M5 22 22 6M14 6h8v8"/>',
    arrowup: '<path d="M14 5l7 9h-4v9h-6v-9H7z"/>',
    arrowdown: '<path d="M14 23l7-9h-4V5h-6v9H7z"/>',
    icons: '<circle cx="14" cy="14" r="9"/><path d="M10 16.5c1 1.5 2.3 2.2 4 2.2s3-.7 4-2.2"/><circle cx="11" cy="12" r="1" fill="currentColor"/><circle cx="17" cy="12" r="1" fill="currentColor"/>',
    ruler: '<path d="M4 19 19 4l5 5L9 24z"/><path d="M9 14l2 2M12 11l3 3M15 8l2 2"/>',
    zoomin: '<circle cx="12" cy="12" r="7"/><path d="M17 17l6 6M9 12h6M12 9v6"/>',
    zoomout: '<circle cx="12" cy="12" r="7"/><path d="M17 17l6 6M9 12h6"/>',
    magnet: '<path d="M7 5v9a7 7 0 0 0 14 0V5h-5v9a2 2 0 0 1-4 0V5z"/><path d="M7 9h5M16 9h5"/>',
    magnetStrong: '<path d="M7 5v9a7 7 0 0 0 14 0V5h-5v9a2 2 0 0 1-4 0V5z" fill="currentColor" fill-opacity=".3"/><path d="M7 9h5M16 9h5"/>',
    stay: '<path d="M6 22l2-6 11-11 4 4-11 11z"/><path d="M16 8l4 4"/><rect x="17" y="18" width="7" height="6" rx="1"/><path d="M18.5 18v-1.5a2 2 0 0 1 4 0V18"/>',
    lock: '<rect x="7" y="13" width="14" height="10" rx="2"/><path d="M10 13V9a4 4 0 0 1 8 0v4"/>',
    unlock: '<rect x="7" y="13" width="14" height="10" rx="2"/><path d="M10 13V9a4 4 0 0 1 7.5-2"/>',
    eye: '<path d="M3 14s4-7 11-7 11 7 11 7-4 7-11 7S3 14 3 14z"/><circle cx="14" cy="14" r="3"/>',
    eyeOff: '<path d="M3 14s4-7 11-7c2 0 3.7.6 5.2 1.4M25 14s-4 7-11 7c-2 0-3.7-.6-5.2-1.4"/><path d="M5 23 23 5"/>',
    link: '<path d="M12 16a4 4 0 0 0 6 .5l3.5-3.5a4 4 0 0 0-5.6-5.6L14 9.3"/><path d="M16 12a4 4 0 0 0-6-.5L6.5 15a4 4 0 0 0 5.6 5.6l1.9-1.9"/>',
    trash: '<path d="M6 8h16M11 8V5h6v3M8 8l1 15h10l1-15"/>',
  };

  // ---- tool registry ---------------------------------------------------------------
  // n: points to click (0 = freehand drag), kind decides paint/hit behaviour
  const T = {
    cross: { name: "Cross", cursor: true }, dot: { name: "Dot", cursor: true }, arrow: { name: "Arrow", cursor: true },
    eraser: { name: "Eraser", cursor: true },
    trend: { name: "Trend line", n: 2, key: "Alt + T" }, ray: { name: "Ray", n: 2 }, info: { name: "Info line", n: 2 },
    extended: { name: "Extended line", n: 2 }, angle: { name: "Trend angle", n: 2 },
    hline: { name: "Horizontal line", n: 1, key: "Alt + H" }, hray: { name: "Horizontal ray", n: 1, key: "Alt + J" },
    vline: { name: "Vertical line", n: 1, key: "Alt + V" }, crossline: { name: "Cross line", n: 1, key: "Alt + C" },
    channel: { name: "Parallel channel", n: 3 }, rect: { name: "Rectangle", n: 2, key: "Alt + Shift + R" },
    fib: { name: "Fib retracement", n: 2, key: "Alt + F" }, fibext: { name: "Trend-based fib extension", n: 3 },
    xabcd: { name: "XABCD pattern", n: 5 }, abcd: { name: "ABCD pattern", n: 4 }, triangle: { name: "Triangle pattern", n: 3 },
    long: { name: "Long position", n: 2 }, short: { name: "Short position", n: 2 },
    daterange: { name: "Date range", n: 2 }, pricerange: { name: "Price range", n: 2 }, measure: { name: "Date and price range", n: 2 },
    brush: { name: "Brush", n: 0 }, highlighter: { name: "Highlighter", n: 0 },
    text: { name: "Text", n: 1 }, callout: { name: "Callout", n: 2 }, pricelabel: { name: "Price label", n: 1 },
    arrowline: { name: "Arrow", n: 2 }, arrowup: { name: "Arrow mark up", n: 1 }, arrowdown: { name: "Arrow mark down", n: 1 },
    emoji: { name: "Icon", n: 1 },
    ruler: { name: "Measure", n: 2, alias: "measure" },
    zoomin: { name: "Zoom in", n: 2 }, zoomout: { name: "Zoom out", action: true },
  };

  const GROUPS = [
    { id: "cursor", items: [["Cursors", ["cross", "dot", "arrow"]], ["", ["eraser"]]] },
    { id: "lines", items: [["Lines", ["trend", "ray", "info", "extended", "angle", "hline", "hray", "vline", "crossline"]], ["Channels", ["channel"]], ["Shapes", ["rect"]]] },
    { id: "fibs", items: [["Fibonacci", ["fib", "fibext"]]] },
    { id: "patterns", items: [["Patterns", ["xabcd", "abcd", "triangle"]]] },
    { id: "projection", items: [["Projection", ["long", "short"]], ["Measurers", ["daterange", "pricerange", "measure"]]] },
    { id: "brushes", items: [["Brushes", ["brush", "highlighter"]]] },
    { id: "texts", items: [["Text & notes", ["text", "callout", "pricelabel"]], ["Arrows", ["arrowline", "arrowup", "arrowdown"]]] },
    { id: "icons", emoji: true },
    "-",
    { id: "ruler", single: "ruler" },
    { id: "zoom", items: [["", ["zoomin", "zoomout"]]] },
    "-",
    { id: "magnet", toggle: "magnet" },
    { id: "stay", toggle: "stay", title: "Stay in drawing mode" },
    { id: "lock", toggle: "lock", title: "Lock all drawings" },
    { id: "hide", menu: "hide" },
    { id: "sync", toggle: "sync", title: "Share drawings across all sessions" },
    "-",
    { id: "trash", menu: "trash" },
  ];

  function create(o) {
    // o: { chart, series(), canvas, wrap, times(), barAt(i), tf(), tickSize(), pointValue(), color(), rr(), status(msg),
    //      setCursor(mode), onIndicators(action), onMarkers(visible) }
    const cv = o.canvas, ctx = cv.getContext("2d");
    const PREF = "tickreplay.tools";
    let pref = { groups: {}, magnet: "off", stay: false, lock: false, sync: false, cursor: "cross", emoji: "🚀" };
    try { pref = { ...pref, ...JSON.parse(localStorage.getItem(PREF) || "{}") }; } catch { /* defaults */ }
    const savePref = () => { try { localStorage.setItem(PREF, JSON.stringify(pref)); } catch { /* ignore */ } };

    let drawings = [], keys = null, tool = pref.cursor, selected = null, creating = null, drag = null, zoomBox = null;
    let visible = true, hoverD = null, bar = null, flyout = null;
    let uid = Date.now();

    // ---- coordinate conversion ------------------------------------------------------

    const ts = () => o.chart.timeScale();
    function timeToX(t) {
      const times = o.times(), n = times.length, tf = o.tf();
      if (!n) return null;
      let l;
      if (t <= times[0]) l = (t - times[0]) / tf;
      else if (t >= times[n - 1]) l = n - 1 + (t - times[n - 1]) / tf;
      else {
        let lo = 0, hi = n - 1;
        while (hi - lo > 1) { const m = (lo + hi) >> 1; if (times[m] <= t) lo = m; else hi = m; }
        l = lo + (t - times[lo]) / (times[hi] - times[lo]);
      }
      return ts().logicalToCoordinate(l);
    }
    function xToTime(x) {
      const times = o.times(), n = times.length, tf = o.tf();
      const l = ts().coordinateToLogical(x);
      if (!n || l === null) return null;
      if (l <= 0) return times[0] + l * tf;
      if (l >= n - 1) return times[n - 1] + (l - (n - 1)) * tf;
      const i = Math.floor(l);
      return times[i] + (l - i) * (times[i + 1] - times[i]);
    }
    const priceToY = (p) => o.series().priceToCoordinate(p);
    const yToPrice = (y) => o.series().coordinateToPrice(y);
    const roundTick = (p) => { const s = o.tickSize(); return Math.round(p / s) * s; };
    const pane = () => ({ w: ts().width(), h: o.wrap.clientHeight - ts().height() });

    function snap(x, y, free = false) {
      let t = xToTime(x), p = yToPrice(y);
      if (t === null || p === null) return null;
      if (pref.magnet !== "off" && !free) {
        const l = Math.round(ts().coordinateToLogical(x)), b = o.barAt(l);
        if (b) {
          const best = [b.open, b.high, b.low, b.close].reduce((a, v) => (Math.abs(priceToY(v) - y) < Math.abs(priceToY(a) - y) ? v : a));
          if (pref.magnet === "strong" || Math.abs(priceToY(best) - y) < 16) { t = b.time; p = best; }
        }
      }
      return { t, p: free ? p : roundTick(p) };
    }

    // ---- persistence ------------------------------------------------------------------

    const storeKey = () => (keys ? (pref.sync ? keys.shared : keys.own) : null);
    function save() {
      const k = storeKey();
      if (k) try { localStorage.setItem(k, JSON.stringify(drawings)); } catch { /* storage full */ }
    }
    function reload() {
      selected = creating = drag = null;
      try { drawings = JSON.parse(localStorage.getItem(storeKey()) || "[]"); } catch { drawings = []; }
    }
    function load(own, shared) { keys = { own, shared }; reload(); }

    // ---- geometry ---------------------------------------------------------------------

    function xy(pt) {
      if (!pt || pt.t === null || pt.p === null) return null;
      const x = timeToX(pt.t), y = priceToY(pt.p);
      return x === null || y === null ? null : { x, y };
    }
    function distSeg(px, py, a, b) {
      const dx = b.x - a.x, dy = b.y - a.y, len = dx * dx + dy * dy;
      let k = len ? ((px - a.x) * dx + (py - a.y) * dy) / len : 0;
      k = Math.max(0, Math.min(1, k));
      return Math.hypot(px - (a.x + k * dx), py - (a.y + k * dy));
    }
    function extend(a, b, w, both) {
      // points where the line a→b leaves the pane (to the right, and to the left when `both`)
      if (b.x === a.x) return [{ x: a.x, y: -1e5 }, { x: a.x, y: 1e5 }];
      const k = (b.y - a.y) / (b.x - a.x);
      const at = (x) => ({ x, y: a.y + k * (x - a.x) });
      const fwd = at(b.x > a.x ? w : 0);
      return both ? [at(b.x > a.x ? 0 : w), fwd] : [a, fwd];
    }
    const XYs = (d) => d.pts.map(xy);
    function inPoly(x, y, poly) {
      let inside = false;
      for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const a = poly[i], b = poly[j];
        if ((a.y > y) !== (b.y > y) && x < ((b.x - a.x) * (y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
      }
      return inside;
    }
    function channelPts(d) {
      const [a, b, c] = XYs(d);
      if (!a || !b || !c) return null;
      const k = b.x === a.x ? 0 : (b.y - a.y) / (b.x - a.x);
      const off = c.y - (a.y + k * (c.x - a.x));
      return { a, b, a2: { x: a.x, y: a.y + off }, b2: { x: b.x, y: b.y + off } };
    }

    /** Draggable points of a drawing, in chart space. */
    function handles(d) {
      const [a, b] = d.pts;
      switch (d.type) {
        case "hline": return [{ t: xToTime(pane().w / 2), p: a.p }];
        case "vline": return [{ t: a.t, p: yToPrice(pane().h / 2) }];
        case "long": case "short": return [a, { t: a.t, p: b.p }, { t: a.t, p: d.target }, { t: b.t, p: a.p }];
        case "rect": return [a, b, { t: a.t, p: b.p }, { t: b.t, p: a.p }];
        case "brush": case "highlighter": return [];
        default: return d.pts;
      }
    }
    function setHandle(d, i, pt) {
      const [a, b] = d.pts;
      if (d.type === "hline") { a.p = pt.p; return; }
      if (d.type === "vline") { a.t = pt.t; return; }
      if (d.type === "long" || d.type === "short") {
        if (i === 0) { const dp = pt.p - a.p; a.p = pt.p; a.t = pt.t; b.p += dp; d.target += dp; }
        else if (i === 1) b.p = pt.p;
        else if (i === 2) d.target = pt.p;
        else b.t = pt.t;
        return;
      }
      if (d.type === "rect" && i >= 2) {
        if (i === 2) { a.t = pt.t; b.p = pt.p; } else { b.t = pt.t; a.p = pt.p; }
        return;
      }
      d.pts[i] = { t: pt.t, p: pt.p };
    }

    function hitHandle(d, x, y) {
      const hs = handles(d);
      for (let i = 0; i < hs.length; i++) {
        const q = xy(hs[i]);
        if (q && Math.hypot(q.x - x, q.y - y) <= HANDLE + 4) return i;
      }
      return -1;
    }

    function textBox(d, A) {
      ctx.font = d.type === "emoji" ? "26px sans-serif" : "600 13px sans-serif";
      const s = d.type === "emoji" ? d.emoji : d.type === "pricelabel" ? d.pts[0].p.toFixed(2) : d.text || "";
      const w = ctx.measureText(s).width;
      if (d.type === "emoji") return { x1: A.x - w / 2 - 2, x2: A.x + w / 2 + 2, y1: A.y - 16, y2: A.y + 16 };
      if (d.type === "pricelabel") return { x1: A.x, x2: A.x + w + 22, y1: A.y - 26, y2: A.y };
      return { x1: A.x - 4, x2: A.x + w + 4, y1: A.y - 16, y2: A.y + 4 };
    }

    function hitBody(d, x, y) {
      const { w } = pane();
      const P = XYs(d), A = P[0];
      switch (d.type) {
        case "hline": { const yy = priceToY(d.pts[0].p); return yy !== null && Math.abs(yy - y) < HIT; }
        case "vline": return A && Math.abs(A.x - x) < HIT;
        case "crossline": return A && (Math.abs(A.x - x) < HIT || Math.abs(A.y - y) < HIT);
        case "hray": return A && Math.abs(A.y - y) < HIT && x >= A.x - HIT;
        case "text": case "emoji": case "pricelabel": {
          if (!A) return false;
          const b = textBox(d, A);
          return x >= b.x1 && x <= b.x2 && y >= b.y1 && y <= b.y2;
        }
        case "arrowup": case "arrowdown": return A && Math.abs(A.x - x) < 10 && Math.abs(A.y - y) < 18;
        case "brush": case "highlighter": {
          const tol = d.type === "highlighter" ? 10 : HIT;
          for (let i = 1; i < P.length; i++) if (P[i - 1] && P[i] && distSeg(x, y, P[i - 1], P[i]) < tol) return true;
          return false;
        }
      }
      if (P.some((q) => !q)) return false;
      const [a, b] = P;
      switch (d.type) {
        case "trend": case "info": case "angle": case "arrowline": return distSeg(x, y, a, b) < HIT;
        case "ray": { const [, e] = extend(a, b, w, false); return distSeg(x, y, a, e) < HIT; }
        case "extended": { const [s, e] = extend(a, b, w, true); return distSeg(x, y, s, e) < HIT; }
        case "callout": {
          const bx = textBox({ ...d, type: "text" }, b);
          return distSeg(x, y, a, b) < HIT || (x >= bx.x1 - 6 && x <= bx.x2 + 6 && y >= bx.y1 - 6 && y <= bx.y2 + 6);
        }
        case "channel": {
          const c = channelPts(d);
          return c && (distSeg(x, y, c.a, c.b) < HIT || distSeg(x, y, c.a2, c.b2) < HIT || inPoly(x, y, [c.a, c.b, c.b2, c.a2]));
        }
        case "xabcd": case "abcd": case "triangle": {
          for (let i = 1; i < P.length; i++) if (distSeg(x, y, P[i - 1], P[i]) < HIT) return true;
          if (d.type === "triangle" && P.length === 3) return inPoly(x, y, P);
          if (d.type === "xabcd" && P.length === 5) return inPoly(x, y, P.slice(0, 3)) || inPoly(x, y, P.slice(2, 5));
          return false;
        }
      }
      let ys = P.map((q) => q.y);
      if (d.type === "long" || d.type === "short") ys = ys.concat(priceToY(d.target));
      const xs = P.map((q) => q.x);
      return x >= Math.min(...xs) - HIT && x <= Math.max(...xs) + HIT && y >= Math.min(...ys) - HIT && y <= Math.max(...ys) + HIT;
    }

    function pick(x, y) {
      if (!visible) return null;
      if (selected) {
        const h = hitHandle(selected, x, y);
        if (h >= 0) return { d: selected, handle: h };
      }
      for (let i = drawings.length - 1; i >= 0; i--) {
        const d = drawings[i];
        const h = hitHandle(d, x, y);
        if (h >= 0) return { d, handle: h };
        if (hitBody(d, x, y)) return { d, handle: -1 };
      }
      return null;
    }

    // ---- painting -----------------------------------------------------------------------

    function alpha(hex, a) {
      if (!/^#[0-9a-f]{6}$/i.test(hex)) return hex;
      const n = parseInt(hex.slice(1), 16);
      return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
    }
    function label(text, x, y, bg, fg = "#fff", align = "left") {
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      const w = ctx.measureText(text).width + 10, h = 18;
      const lx = align === "center" ? x - w / 2 : align === "right" ? x - w : x;
      ctx.fillStyle = bg;
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(lx, y - h / 2, w, h, 4); else ctx.rect(lx, y - h / 2, w, h);
      ctx.fill();
      ctx.fillStyle = fg;
      ctx.textBaseline = "middle";
      ctx.fillText(text, lx + 5, y + 0.5);
    }
    const fmtP = (p) => p.toFixed(2);
    const line = (a, b) => { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); };
    function arrowHead(a, b, size = 10) {
      const ang = Math.atan2(b.y - a.y, b.x - a.x);
      ctx.beginPath();
      ctx.moveTo(b.x, b.y);
      ctx.lineTo(b.x - size * Math.cos(ang - 0.45), b.y - size * Math.sin(ang - 0.45));
      ctx.lineTo(b.x - size * Math.cos(ang + 0.45), b.y - size * Math.sin(ang + 0.45));
      ctx.closePath();
      ctx.fill();
    }
    function span(d) {
      const dp = d.pts[1].p - d.pts[0].p, secs = Math.abs(d.pts[1].t - d.pts[0].t);
      const dur = secs < 60 ? `${Math.round(secs)}s` : secs < 3600 ? `${Math.floor(secs / 60)}m ${Math.round(secs % 60)}s`
        : secs < 86400 ? `${Math.floor(secs / 3600)}h ${Math.round((secs % 3600) / 60)}m` : `${Math.floor(secs / 86400)}d ${Math.round((secs % 86400) / 3600)}h`;
      return {
        dp, bars: Math.round(secs / o.tf()), dur,
        price: `${dp >= 0 ? "+" : ""}${dp.toFixed(2)} (${((dp / d.pts[0].p) * 100).toFixed(2)}%) ${Math.round(dp / o.tickSize())}t · $${(Math.abs(dp) * o.pointValue()).toFixed(0)}`,
      };
    }
    function ratio(a, b, c) {
      const r = Math.abs(c.p - b.p) / (Math.abs(b.p - a.p) || 1);
      return r.toFixed(3);
    }

    function paintPosition(d, A, B) {
      const T2 = priceToY(d.target), long = d.type === "long";
      const x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x), w = Math.max(x2 - x1, 1);
      ctx.fillStyle = "rgba(38,166,154,.18)";
      ctx.fillRect(x1, Math.min(A.y, T2), w, Math.abs(T2 - A.y));
      ctx.fillStyle = "rgba(239,83,80,.18)";
      ctx.fillRect(x1, Math.min(A.y, B.y), w, Math.abs(B.y - A.y));
      ctx.strokeStyle = "#9598a1"; ctx.lineWidth = 1;
      line({ x: x1, y: A.y }, { x: x2, y: A.y });
      const risk = Math.abs(d.pts[0].p - d.pts[1].p), reward = Math.abs(d.target - d.pts[0].p);
      const tick = o.tickSize(), pv = o.pointValue(), cx = x1 + w / 2;
      label(`Target ${fmtP(d.target)} · ${reward.toFixed(2)} (${Math.round(reward / tick)}t) · $${(reward * pv).toFixed(0)}`, cx, T2 + (long ? -12 : 12), "#26a69a", "#fff", "center");
      label(`Stop ${fmtP(d.pts[1].p)} · ${risk.toFixed(2)} (${Math.round(risk / tick)}t) · $${(risk * pv).toFixed(0)}`, cx, B.y + (long ? 12 : -12), "#ef5350", "#fff", "center");
      label(`${long ? "Long" : "Short"} ${fmtP(d.pts[0].p)} · R:R ${risk ? (reward / risk).toFixed(2) : "–"}`, cx, A.y, "#2a2e39", "#fff", "center");
    }

    function paintFib(d, P, base) {
      // retracement: level 1 at the first point, 0 at the second (TradingView convention)
      // extension: levels projected from the third point by the first→second move
      const opt = { ...FIB_OPTS, ...d };
      const levels = (d.levels || (d.type === "fibext" ? FIBEXT_LEVELS : FIB_LEVELS)).filter((l) => l.on).slice().sort((a, b) => a.v - b.v);
      const xsAll = P.map((q) => q.x), { w } = pane();
      let x1 = Math.min(...xsAll), x2 = Math.max(...xsAll) + (d.type === "fibext" ? 60 : 0);
      if (opt.fibExtLeft) x1 = 0;
      if (opt.fibExtRight) x2 = w;
      let prevY = null;
      for (const l of levels) {
        const p = base(opt.fibReverse ? 1 - l.v : l.v), y = priceToY(p);
        if (y === null) continue;
        if (opt.fibFill && prevY !== null) { ctx.fillStyle = alpha(l.c, +opt.fibFillOpacity); ctx.fillRect(x1, Math.min(y, prevY), x2 - x1, Math.abs(y - prevY)); }
        ctx.strokeStyle = l.c; ctx.lineWidth = d.width ? Math.max(1, d.width - 1) : 1; ctx.setLineDash(DASH[d.lineStyle || 0]);
        line({ x: x1, y }, { x: x2, y });
        ctx.setLineDash([]);
        const lvText = opt.fibLevelsFmt === "percents" ? `${+(l.v * 100).toFixed(1)}%` : opt.fibLevelsFmt === "values" ? String(l.v) : "";
        const txt = [lvText, opt.fibPrices ? `(${fmtP(p)})` : ""].filter(Boolean).join(" ");
        if (txt) {
          ctx.font = "11px ui-monospace, Menlo, monospace"; ctx.fillStyle = l.c; ctx.textBaseline = "bottom";
          ctx.textAlign = opt.fibLabels === "right" ? "right" : "left";
          ctx.fillText(txt, opt.fibLabels === "right" ? x2 - 4 : x1 + 4, y - 2);
          ctx.textAlign = "left";
        }
        prevY = y;
      }
      if (opt.fibTrend) {
        ctx.strokeStyle = alpha(d.color, 0.7); ctx.lineWidth = 1; ctx.setLineDash([4, 4]);
        for (let i = 1; i < P.length; i++) line(P[i - 1], P[i]);
        ctx.setLineDash([]);
      }
    }

    /** Text written along a line (or inside a box), like TradingView's Text tab. */
    function lineText(d, A, B) {
      if (!d.text) return;
      const size = +d.textSize || 13, pos = d.textPos || "top", align = d.textAlign || "center";
      let ang = Math.atan2(B.y - A.y, B.x - A.x), a = A, b = B;
      if (ang > Math.PI / 2 || ang < -Math.PI / 2) { a = B; b = A; ang = Math.atan2(b.y - a.y, b.x - a.x); }   // keep text upright
      const k = align === "left" ? 0 : align === "right" ? 1 : 0.5;
      const px = a.x + (b.x - a.x) * k, py = a.y + (b.y - a.y) * k;
      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(ang);
      ctx.font = `${d.textBold ? "700" : "500"} ${size}px -apple-system, Segoe UI, sans-serif`;
      ctx.fillStyle = d.textColor || d.color;
      ctx.textAlign = align === "left" ? "left" : align === "right" ? "right" : "center";
      ctx.textBaseline = pos === "top" ? "bottom" : pos === "bottom" ? "top" : "middle";
      const dx = align === "left" ? 6 : align === "right" ? -6 : 0;
      ctx.fillText(d.text, dx, pos === "top" ? -4 : pos === "bottom" ? 4 : 0);
      ctx.restore();
    }

    function boxText(d, x1, y1, x2, y2) {
      if (!d.text) return;
      const size = +d.textSize || 13, pos = d.textPos || "top", align = d.textAlign || "center";
      ctx.font = `${d.textBold ? "700" : "500"} ${size}px -apple-system, Segoe UI, sans-serif`;
      ctx.fillStyle = d.textColor || d.color;
      ctx.textAlign = align;
      ctx.textBaseline = pos === "top" ? "top" : pos === "bottom" ? "bottom" : "middle";
      const x = align === "left" ? x1 + 6 : align === "right" ? x2 - 6 : (x1 + x2) / 2;
      const y = pos === "top" ? y1 + 5 : pos === "bottom" ? y2 - 5 : (y1 + y2) / 2;
      ctx.fillText(d.text, x, y);
      ctx.textAlign = "left";
    }

    const tfClass = () => (o.tf() < 60 ? "sec" : o.tf() < 3600 ? "min" : "hour");

    function paintPattern(d, P) {
      const names = d.type === "xabcd" ? ["X", "A", "B", "C", "D"] : d.type === "abcd" ? ["A", "B", "C", "D"] : ["A", "B", "C"];
      ctx.fillStyle = alpha(d.color, 0.14);
      if (d.type === "triangle" && P.length === 3) { ctx.beginPath(); P.forEach((q, i) => (i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y))); ctx.closePath(); ctx.fill(); }
      if (d.type === "xabcd") {
        for (const tri of [P.slice(0, 3), P.slice(2, 5)]) {
          if (tri.length < 3) continue;
          ctx.beginPath(); tri.forEach((q, i) => (i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y))); ctx.closePath(); ctx.fill();
        }
      }
      ctx.strokeStyle = d.color; ctx.lineWidth = 2;
      for (let i = 1; i < P.length; i++) line(P[i - 1], P[i]);
      if (d.type === "triangle" && P.length === 3) line(P[2], P[0]);
      // Fibonacci ratios of each leg to the previous one, on dashed connectors
      ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
      const pts = d.pts;
      for (let i = 2; i < P.length && d.type !== "triangle"; i++) {
        line(P[i - 2], P[i]);
        const mx = (P[i - 2].x + P[i].x) / 2, my = (P[i - 2].y + P[i].y) / 2;
        label(ratio(pts[i - 2], pts[i - 1], pts[i]), mx, my, alpha(d.color, 0.85), "#fff", "center");
      }
      ctx.setLineDash([]);
      P.forEach((q, i) => {
        const up = i > 0 ? q.y < P[i - 1].y : P[1] && q.y < P[1].y;
        label(names[i], q.x, q.y + (up ? -14 : 14), d.color, "#fff", "center");
      });
    }

    function paint(d, sel) {
      if (d.vis && d.vis[tfClass()] === false) return;          // hidden on this timeframe (Visibility tab)
      const { w, h } = pane();
      ctx.strokeStyle = d.color;
      ctx.fillStyle = d.color;
      ctx.lineWidth = d.width || 2;
      ctx.setLineDash(DASH[d.lineStyle || 0]);
      if (d.type === "hline") {
        const y = priceToY(d.pts[0].p);
        if (y === null) return;
        line({ x: 0, y }, { x: w, y });
        ctx.setLineDash([]);
        if (d.priceLabel !== false) label(fmtP(d.pts[0].p), w - 4, y, d.color, "#fff", "right");
        lineText(d, { x: 0, y }, { x: w - 70, y });
        return drawHandles(d, sel);
      }
      const P = XYs(d), A = P[0];
      if (!A) return;
      switch (d.type) {
        case "vline": line({ x: A.x, y: 0 }, { x: A.x, y: h }); ctx.setLineDash([]); lineText(d, { x: A.x, y: h }, { x: A.x, y: 0 }); break;
        case "crossline":
          line({ x: A.x, y: 0 }, { x: A.x, y: h }); line({ x: 0, y: A.y }, { x: w, y: A.y });
          ctx.setLineDash([]);
          label(fmtP(d.pts[0].p), w - 4, A.y, d.color, "#fff", "right");
          break;
        case "hray":
          line(A, { x: w, y: A.y }); ctx.setLineDash([]);
          if (d.priceLabel !== false) label(fmtP(d.pts[0].p), w - 4, A.y, d.color, "#fff", "right");
          lineText(d, A, { x: w - 70, y: A.y });
          break;
        case "text":
          ctx.font = "600 13px -apple-system, Segoe UI, sans-serif"; ctx.textBaseline = "alphabetic";
          ctx.fillText(d.text || "", A.x, A.y);
          break;
        case "emoji":
          ctx.font = "26px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
          ctx.fillText(d.emoji, A.x, A.y); ctx.textAlign = "left";
          break;
        case "pricelabel": {
          const b = textBox(d, A);
          ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(A.x + 8, b.y1 + 16); ctx.lineTo(A.x + 8, b.y1);
          ctx.lineTo(b.x2, b.y1); ctx.lineTo(b.x2, b.y1 + 18); ctx.lineTo(A.x + 14, b.y1 + 18); ctx.closePath(); ctx.fill();
          ctx.fillStyle = "#fff"; ctx.font = "600 13px sans-serif"; ctx.textBaseline = "middle";
          ctx.fillText(fmtP(d.pts[0].p), A.x + 12, b.y1 + 9.5);
          break;
        }
        case "arrowup": case "arrowdown": {
          const up = d.type === "arrowup", s = up ? 1 : -1;
          ctx.fillStyle = up ? "#26a69a" : "#ef5350";
          ctx.beginPath();
          ctx.moveTo(A.x, A.y); ctx.lineTo(A.x + 9, A.y + 11 * s); ctx.lineTo(A.x + 4, A.y + 11 * s); ctx.lineTo(A.x + 4, A.y + 22 * s);
          ctx.lineTo(A.x - 4, A.y + 22 * s); ctx.lineTo(A.x - 4, A.y + 11 * s); ctx.lineTo(A.x - 9, A.y + 11 * s); ctx.closePath(); ctx.fill();
          break;
        }
        case "brush": case "highlighter": {
          ctx.lineWidth = d.type === "highlighter" ? 14 : 2;
          ctx.strokeStyle = d.type === "highlighter" ? alpha(d.color, 0.35) : d.color;
          ctx.beginPath();
          let started = false;
          for (const q of P) { if (!q) continue; if (started) ctx.lineTo(q.x, q.y); else { ctx.moveTo(q.x, q.y); started = true; } }
          ctx.stroke();
          break;
        }
      }
      if (["vline", "crossline", "hray", "text", "emoji", "pricelabel", "arrowup", "arrowdown", "brush", "highlighter"].includes(d.type)) return drawHandles(d, sel);
      if (P.some((q) => !q) || P.length < 2) return drawHandles(d, sel);
      const B = P[1];
      // lines can be extended past either point (Style tab), ray/extended do it by default
      const extL = d.extendLeft ?? d.type === "extended", extR = d.extendRight ?? (d.type === "ray" || d.type === "extended");
      const S0 = extL ? extend(B, A, w, false)[1] : A, E0 = extR ? extend(A, B, w, false)[1] : B;
      switch (d.type) {
        case "trend": case "ray": case "extended": line(S0, E0); ctx.setLineDash([]); lineText(d, A, B); break;
        case "arrowline": line(S0, B); ctx.setLineDash([]); arrowHead(A, B); lineText(d, A, B); break;
        case "info": {
          line(S0, E0); ctx.setLineDash([]); lineText(d, A, B);
          const sp = span(d), ang = (Math.atan2(A.y - B.y, B.x - A.x) * 180) / Math.PI;
          label(`${sp.price}`, B.x + 8, B.y - 10, alpha("#2a2e39", 0.95));
          label(`${sp.bars} bars · ${sp.dur} · ${ang.toFixed(1)}°`, B.x + 8, B.y + 10, alpha("#2a2e39", 0.95));
          break;
        }
        case "angle": {
          line(A, B);
          ctx.setLineDash([3, 3]); ctx.lineWidth = 1; line(A, { x: A.x + Math.max(40, Math.abs(B.x - A.x)), y: A.y }); ctx.setLineDash([]);
          const ang = Math.atan2(A.y - B.y, B.x - A.x);
          ctx.beginPath(); ctx.arc(A.x, A.y, 30, -ang, 0, ang < 0); ctx.stroke();
          label(`${((ang * 180) / Math.PI).toFixed(1)}°`, A.x + 36, A.y - 10, d.color);
          break;
        }
        case "callout": {
          ctx.lineWidth = 1.5; line(A, B);
          const bx = textBox({ ...d, type: "text" }, B);
          ctx.fillStyle = d.color;
          ctx.beginPath();
          if (ctx.roundRect) ctx.roundRect(bx.x1 - 4, bx.y1 - 4, bx.x2 - bx.x1 + 8, bx.y2 - bx.y1 + 8, 6); else ctx.rect(bx.x1 - 4, bx.y1 - 4, bx.x2 - bx.x1 + 8, bx.y2 - bx.y1 + 8);
          ctx.fill();
          ctx.fillStyle = "#fff"; ctx.font = "600 13px -apple-system, Segoe UI, sans-serif"; ctx.textBaseline = "alphabetic";
          ctx.fillText(d.text || "", B.x, B.y);
          break;
        }
        case "rect": {
          let x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x);
          if (d.extendLeft) x1 = 0;
          if (d.extendRight) x2 = w;
          const y1 = Math.min(A.y, B.y), y2 = Math.max(A.y, B.y);
          if (d.fill !== false) { ctx.fillStyle = alpha(d.fillColor || d.color, d.fillOpacity ?? 0.15); ctx.fillRect(x1, y1, x2 - x1, y2 - y1); }
          ctx.lineWidth = d.width ?? 1.5;
          if (ctx.lineWidth > 0) ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
          ctx.setLineDash([]);
          boxText(d, x1, y1, x2, y2);
          break;
        }
        case "channel": {
          const c = channelPts(d);
          if (!c) {
            line(A, B);
            break;
          }
          if (d.fill !== false) {
            ctx.fillStyle = alpha(d.fillColor || d.color, d.fillOpacity ?? 0.1);
            ctx.beginPath(); ctx.moveTo(c.a.x, c.a.y); ctx.lineTo(c.b.x, c.b.y); ctx.lineTo(c.b2.x, c.b2.y); ctx.lineTo(c.a2.x, c.a2.y); ctx.closePath(); ctx.fill();
          }
          line(c.a, c.b); line(c.a2, c.b2);
          ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
          line({ x: c.a.x, y: (c.a.y + c.a2.y) / 2 }, { x: c.b.x, y: (c.b.y + c.b2.y) / 2 });
          ctx.setLineDash([]);
          lineText(d, c.a, c.b);
          break;
        }
        case "fib": {
          const p0 = d.pts[1].p, p1 = d.pts[0].p;
          paintFib(d, P, (v) => p0 + (p1 - p0) * v);
          break;
        }
        case "fibext": {
          if (P.length < 3) { ctx.setLineDash([4, 4]); line(A, B); ctx.setLineDash([]); break; }
          const move = d.pts[1].p - d.pts[0].p, c = d.pts[2].p;
          paintFib(d, P, (v) => c + move * v);
          break;
        }
        case "xabcd": case "abcd": case "triangle": paintPattern(d, P); break;
        case "long": case "short": paintPosition(d, A, B); break;
        case "daterange": case "pricerange": case "measure": {
          const sp = span(d), col = d.type === "measure" ? (sp.dp >= 0 ? "#2962ff" : "#ef5350") : "#2962ff";
          const x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x), y1 = Math.min(A.y, B.y), y2 = Math.max(A.y, B.y);
          ctx.fillStyle = alpha(col, 0.15);
          ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
          ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1;
          const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
          if (d.type !== "daterange") { line({ x: mx, y: A.y }, { x: mx, y: B.y }); arrowHead({ x: mx, y: A.y }, { x: mx, y: B.y }, 7); }
          if (d.type !== "pricerange") { line({ x: A.x, y: my }, { x: B.x, y: my }); arrowHead({ x: A.x, y: my }, { x: B.x, y: my }, 7); }
          const lines = d.type === "daterange" ? [`${sp.bars} bars · ${sp.dur}`] : d.type === "pricerange" ? [sp.price] : [sp.price, `${sp.bars} bars · ${sp.dur}`];
          lines.forEach((s, i) => label(s, mx, y2 + 14 + i * 20, col, "#fff", "center"));
          break;
        }
      }
      drawHandles(d, sel);
    }

    function drawHandles(d, sel) {
      if (!(sel || d === hoverD) || pref.lock) return;
      for (const hp of handles(d)) {
        const q = xy(hp);
        if (!q) continue;
        ctx.fillStyle = "#0b0e14"; ctx.strokeStyle = sel ? "#4f7cff" : "#9598a1"; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(q.x, q.y, HANDLE, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
    }

    function redraw() {
      const dpr = window.devicePixelRatio || 1;
      const W = o.wrap.clientWidth, H = o.wrap.clientHeight;
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) {
        cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
        cv.style.width = W + "px"; cv.style.height = H + "px";
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      if (!o.times().length) return;
      const { w, h } = pane();
      ctx.save();
      ctx.beginPath(); ctx.rect(0, 0, w, h); ctx.clip();
      if (visible) for (const d of drawings) paint(d, d === selected);
      if (creating) paint(creating, true);
      if (zoomBox) {
        ctx.fillStyle = "rgba(79,124,255,.12)"; ctx.strokeStyle = "#4f7cff"; ctx.lineWidth = 1;
        const { a, b } = zoomBox;
        ctx.fillRect(Math.min(a.x, b.x), 0, Math.abs(b.x - a.x), h);
        ctx.strokeRect(Math.min(a.x, b.x), 0, Math.abs(b.x - a.x), h);
      }
      ctx.restore();
    }

    // ---- interaction ------------------------------------------------------------------------

    const local = (e) => { const r = o.wrap.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const inPane = ({ x, y }) => { const { w, h } = pane(); return x >= 0 && y >= 0 && x <= w && y <= h; };
    const isDrawTool = (t) => T[t] && !T[t].cursor && !T[t].action;
    const realType = (t) => T[t].alias || t;

    function newDrawing(t, pt) {
      const type = realType(t), n = T[type].n;
      const d = { id: ++uid, type, color: o.color(), width: type === "rect" ? 1 : 2, lineStyle: 0, pts: [pt] };
      if (type === "long" || type === "short") { d.color = "#9598a1"; d.target = pt.p; }
      if (type === "emoji") d.emoji = pref.emoji;
      if (type === "fib" || type === "fibext") Object.assign(d, clone(FIB_OPTS), { levels: clone(type === "fib" ? FIB_LEVELS : FIBEXT_LEVELS) });
      // the user's default template for this tool (Template → Save as default)
      const def = readJSON(DEF_KEY)[type];
      if (def) Object.assign(d, clone(def));
      if (n > 1) d.pts.push({ ...pt });   // live point following the mouse
      return d;
    }

    function finish(d) {
      if (d.type === "long" || d.type === "short") {
        if (!(d.pts[0].p - d.pts[1].p)) d.pts[1].p = d.pts[0].p + (d.type === "long" ? -1 : 1) * o.tickSize() * 20;
        d.target = roundTick(d.pts[0].p + (d.pts[0].p - d.pts[1].p) * o.rr());
        if (d.pts[1].t === d.pts[0].t) d.pts[1].t = d.pts[0].t + o.tf() * 20;
      }
      delete d.downAt;
      drawings.push(d);
      selected = d;
      creating = null;
      save();
      if (!pref.stay) setTool(pref.cursor);
    }

    function onDown(e) {
      if (e.button !== 0) return;
      const m = local(e);
      if (!inPane(m)) return;
      closeFlyout();
      if (tool === "zoomin") { e.preventDefault(); e.stopPropagation(); zoomBox = { a: m, b: m }; return; }
      if (isDrawTool(tool)) {
        e.preventDefault(); e.stopPropagation();
        const free = tool === "brush" || tool === "highlighter";
        const pt = snap(m.x, m.y, free);
        if (!pt) return;
        if (free) { creating = newDrawing(tool, pt); creating.freehand = true; return; }
        if (creating) {                                   // next click of a multi-point tool
          creating.pts[creating.pts.length - 1] = pt;
          if (creating.pts.length >= T[creating.type].n) return completeCreating(m);
          creating.pts.push({ ...pt });
          return;
        }
        const d = newDrawing(tool, pt);
        if (d.type === "text") { editText(d, m); return; }
        if (T[d.type].n === 1) { finish(d); return; }
        creating = d;
        creating.downAt = m;
        return;
      }
      const hit = pick(m.x, m.y);
      if (tool === "eraser") {
        if (hit) { e.preventDefault(); e.stopPropagation(); remove(hit.d); }
        return;
      }
      if (!hit) { selected = null; return; }
      e.preventDefault(); e.stopPropagation();          // a drawing under the mouse: don't pan the chart
      selected = hit.d;
      if (pref.lock) return;
      drag = { d: hit.d, handle: hit.handle, start: snap(m.x, m.y, true) || { t: 0, p: 0 }, orig: JSON.parse(JSON.stringify(hit.d)) };
    }

    function completeCreating(m) {
      const d = creating;
      if (d.type === "callout") { creating = null; editText(d, { x: timeToX(d.pts[1].t) ?? m.x, y: priceToY(d.pts[1].p) ?? m.y }); return; }
      finish(d);
    }

    function onMove(e) {
      const m = local(e);
      if (zoomBox) { zoomBox.b = m; return; }
      if (creating) {
        const free = creating.freehand;
        const pt = snap(m.x, m.y, free);
        if (!pt) return;
        if (free) { creating.pts.push(pt); return; }
        creating.pts[creating.pts.length - 1] = pt;
        if (creating.type === "long" || creating.type === "short") {
          creating.target = roundTick(creating.pts[0].p + (creating.pts[0].p - pt.p) * o.rr());
        }
        return;
      }
      if (drag) {
        const pt = snap(m.x, m.y, drag.handle < 0);
        if (!pt) return;
        const d = drag.d;
        if (drag.handle >= 0) setHandle(d, drag.handle, snap(m.x, m.y) || pt);
        else {
          const dt = pt.t - drag.start.t, dp = pt.p - drag.start.p;
          const free = d.type === "brush" || d.type === "highlighter";
          d.pts = drag.orig.pts.map((q) => ({ t: q.t + dt, p: free ? q.p + dp : roundTick(q.p + dp) }));
          if (d.target !== undefined) d.target = roundTick(drag.orig.target + dp);
        }
        return;
      }
      if (!isDrawTool(tool) && tool !== "zoomin" && inPane(m)) {
        const hit = pick(m.x, m.y);
        hoverD = hit ? hit.d : null;
        o.wrap.style.cursor = tool === "eraser" ? (hit ? "pointer" : "") : hit && !pref.lock ? (hit.handle >= 0 ? "grab" : "move") : "";
      }
    }

    function onUp(e) {
      if (zoomBox) {
        const { a, b } = zoomBox;
        zoomBox = null;
        if (Math.abs(b.x - a.x) > 8) {
          const l1 = ts().coordinateToLogical(Math.min(a.x, b.x)), l2 = ts().coordinateToLogical(Math.max(a.x, b.x));
          if (l1 !== null && l2 !== null) ts().setVisibleLogicalRange({ from: l1, to: l2 });
        }
        if (!pref.stay) setTool(pref.cursor);
        return;
      }
      if (creating && creating.freehand) {
        if (creating.pts.length > 1) finish(creating); else creating = null;
        return;
      }
      if (creating && creating.downAt) {
        const m = local(e);
        if (Math.hypot(m.x - creating.downAt.x, m.y - creating.downAt.y) > 6) {
          // drag-to-draw: the drag was the first segment
          if (creating.pts.length >= T[creating.type].n) completeCreating(m);
          else { delete creating.downAt; creating.pts.push({ ...creating.pts[creating.pts.length - 1] }); }
        } else delete creating.downAt;
        return;
      }
      if (drag) { drag = null; save(); }
    }

    function editText(d, m, existing = false) {
      const box = document.getElementById("textEdit"), input = document.getElementById("textInput");
      box.hidden = false;
      box.style.left = m.x + "px";
      box.style.top = m.y - 16 + "px";
      input.value = d.text || "";
      setTimeout(() => input.focus(), 0);
      let closed = false;
      const done = (ok) => {
        if (closed) return;
        closed = true;
        input.onkeydown = input.onblur = null;
        input.blur();          // give the keyboard back to the chart (shortcuts, Space)
        box.hidden = true;
        if (ok && input.value.trim()) {
          d.text = input.value.trim();
          if (!existing) finish(d); else save();
        } else if (!existing) setTool(pref.cursor);
      };
      input.onkeydown = (ev) => { if (ev.key === "Enter") done(true); if (ev.key === "Escape") done(false); ev.stopPropagation(); };
      input.onblur = () => done(true);
    }

    function onDbl(e) {
      const m = local(e), hit = pick(m.x, m.y);
      if (!hit) return;
      e.stopPropagation();
      if (hit.d.type === "text" || hit.d.type === "callout") {
        const at = hit.d.type === "callout" ? xy(hit.d.pts[1]) : m;
        editText(hit.d, at || m, true);
      } else openSettings(hit.d);
    }

    // ---- per-drawing settings dialog (TradingView style) + templates ----------------------

    let dlg = null;
    const TYPE_NAME = (t) => (T[t] ? T[t].name : t);
    const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    /** display seconds (New York wall clock) <-> datetime-local text */
    const tToInput = (t) => new Date(Math.round(t) * 1000).toISOString().slice(0, 19);
    const inputToT = (v) => Date.parse(v + "Z") / 1000;

    function styleRow(label, html) { return `<div class="set-row"><label>${label}</label><span>${html}</span></div>`; }
    const colorIn = (key, val) => `<input type="color" data-k="${key}" value="${esc(val)}">`;
    const selectIn = (key, val, opts) => `<select data-k="${key}">${opts.map(([v, l]) => `<option value="${v}" ${String(val) === String(v) ? "selected" : ""}>${l}</option>`).join("")}</select>`;
    const checkIn = (key, val) => `<input type="checkbox" data-k="${key}" ${val ? "checked" : ""}>`;
    const widthSel = (d) => selectIn("width", d.width ?? 2, [[1, "1 px"], [2, "2 px"], [3, "3 px"], [4, "4 px"]]);
    const styleSel = (d) => selectIn("lineStyle", d.lineStyle || 0, [[0, "━━ Solid"], [1, "┈┈ Dotted"], [2, "╌╌ Dashed"]]);

    function styleTab(d) {
      const t = d.type;
      if (t === "fib" || t === "fibext") {
        const levels = d.levels || [];
        return styleRow("Trend line", `${checkIn("fibTrend", d.fibTrend)} ${colorIn("color", d.color)}`) +
          styleRow("Levels line", `${widthSel(d)} ${styleSel(d)}`) +
          `<h4>Levels</h4><div class="lv-grid">${levels.map((l, i) => `<label class="lv"><input type="checkbox" data-lv="${i}" data-f="on" ${l.on ? "checked" : ""}>
            <input type="number" step="0.001" data-lv="${i}" data-f="v" value="${l.v}"><input type="color" data-lv="${i}" data-f="c" value="${l.c}"></label>`).join("")}</div>
          <div class="lv-actions"><button type="button" data-act="addLevel">+ Add level</button></div>
          <h4>Options</h4>` +
          styleRow("Extend lines", `<label class="inl">${checkIn("fibExtLeft", d.fibExtLeft)} Left</label><label class="inl">${checkIn("fibExtRight", d.fibExtRight)} Right</label>`) +
          styleRow("Reverse", checkIn("fibReverse", d.fibReverse)) +
          styleRow("Prices", checkIn("fibPrices", d.fibPrices)) +
          styleRow("Levels", selectIn("fibLevelsFmt", d.fibLevelsFmt, [["values", "Values"], ["percents", "Percents"], ["none", "Hidden"]])) +
          styleRow("Labels", selectIn("fibLabels", d.fibLabels, [["left", "Left"], ["right", "Right"]])) +
          styleRow("Background", `${checkIn("fibFill", d.fibFill)} <input type="range" min="0" max="0.5" step="0.01" data-k="fibFillOpacity" value="${d.fibFillOpacity ?? 0.08}">`);
      }
      let html = styleRow(t === "rect" || t === "channel" ? "Border" : "Line", `${colorIn("color", d.color)} ${widthSel(d)} ${styleSel(d)}`);
      if (t === "rect" || t === "channel") {
        html += styleRow("Background", `${checkIn("fill", d.fill !== false)} ${colorIn("fillColor", d.fillColor || d.color)}
          <input type="range" min="0" max="1" step="0.05" data-k="fillOpacity" value="${d.fillOpacity ?? (t === "rect" ? 0.15 : 0.1)}">`);
      }
      if (["trend", "ray", "info", "extended", "arrowline", "rect"].includes(t)) {
        html += styleRow("Extend", `<label class="inl">${checkIn("extendLeft", d.extendLeft ?? t === "extended")} Left</label><label class="inl">${checkIn("extendRight", d.extendRight ?? (t === "ray" || t === "extended"))} Right</label>`);
      }
      if (t === "hline" || t === "hray") html += styleRow("Price label", checkIn("priceLabel", d.priceLabel !== false));
      return html;
    }

    function textTab(d) {
      return `<textarea data-k="text" rows="3" placeholder="Text on the drawing…">${esc(d.text)}</textarea>` +
        styleRow("Colour and size", `${colorIn("textColor", d.textColor || d.color)} ${selectIn("textSize", d.textSize || 13, [[10, 10], [11, 11], [12, 12], [13, 13], [14, 14], [16, 16], [20, 20], [24, 24], [28, 28]])}
          <label class="inl">${checkIn("textBold", d.textBold)} Bold</label>`) +
        (d.type === "text" || d.type === "callout" ? "" :
          styleRow("Position", selectIn("textPos", d.textPos || "top", [["top", "Top"], ["middle", "Middle"], ["bottom", "Bottom"]])) +
          styleRow("Alignment", selectIn("textAlign", d.textAlign || "center", [["left", "Left"], ["center", "Center"], ["right", "Right"]])));
    }

    function coordsTab(d) {
      const names = d.type === "xabcd" ? ["X", "A", "B", "C", "D"] : d.type === "abcd" ? ["A", "B", "C", "D"] : ["#1", "#2", "#3", "#4", "#5"];
      return d.pts.map((q, i) => {
        const priceIn = d.type === "vline" ? "" : `<input type="number" step="${o.tickSize()}" data-pt="${i}" data-f="p" value="${q.p.toFixed(2)}">`;
        const timeIn = d.type === "hline" ? "" : `<input type="datetime-local" step="1" data-pt="${i}" data-f="t" value="${tToInput(q.t)}">`;
        return styleRow(`Point ${names[i] || i + 1}`, `${priceIn} ${timeIn}`);
      }).join("") + (d.type === "long" || d.type === "short" ? styleRow("Target price", `<input type="number" step="${o.tickSize()}" data-k="target" value="${(+d.target).toFixed(2)}">`) : "");
    }

    function visTab(d) {
      const v = d.vis || {};
      return `<p class="muted small">Show this drawing on these timeframes:</p>` +
        styleRow("Seconds (1s – 30s)", `<input type="checkbox" data-vis="sec" ${v.sec !== false ? "checked" : ""}>`) +
        styleRow("Minutes (1m – 30m)", `<input type="checkbox" data-vis="min" ${v.min !== false ? "checked" : ""}>`) +
        styleRow("Hours (1h – 4h)", `<input type="checkbox" data-vis="hour" ${v.hour !== false ? "checked" : ""}>`);
    }

    function ensureDialog() {
      if (dlg) return dlg;
      dlg = document.createElement("dialog");
      dlg.className = "dd";
      document.body.appendChild(dlg);
      return dlg;
    }

    function openSettings(d) {
      const box = ensureDialog();
      const before = clone(d);
      const hasText = TEXT_ON.has(d.type) || d.type === "text" || d.type === "callout";
      const tabs = [["style", "Style"], ...(hasText ? [["text", "Text"]] : []), ["coords", "Coordinates"], ["vis", "Visibility"]];
      const render = (tab) => {
        box.innerHTML = `<form method="dialog" class="set-form">
          <div class="set-head"><h2>${esc(TYPE_NAME(d.type))}</h2><button class="x" value="cancel" formnovalidate aria-label="Close">✕</button></div>
          <div class="set-body">
            <nav class="set-tabs">${tabs.map(([k, l]) => `<button type="button" data-dtab="${k}" class="${k === tab ? "on" : ""}">${l}</button>`).join("")}</nav>
            <div class="set-pane">${tab === "style" ? styleTab(d) : tab === "text" ? textTab(d) : tab === "coords" ? coordsTab(d) : visTab(d)}</div>
          </div>
          <div class="set-foot">
            <div class="tpl">
              <button type="button" class="btn ghost" data-act="tpl">Template ▾</button>
              <div class="tpl-menu" hidden></div>
            </div>
            <span class="spacer"></span>
            <button class="btn ghost" value="cancel" formnovalidate>Cancel</button>
            <button class="btn primary" value="ok">Ok</button>
          </div></form>`;
        box.dataset.tab = tab;
      };
      render("style");

      const apply = (el) => {
        if (el.dataset.k) {
          const k = el.dataset.k;
          let v = el.type === "checkbox" ? el.checked : el.type === "number" || el.type === "range" ? +el.value : el.value;
          if (["width", "lineStyle", "textSize"].includes(k)) v = +v;
          if (k === "target") v = Math.round(v / o.tickSize()) * o.tickSize();
          d[k] = v;
        } else if (el.dataset.lv !== undefined) {
          const l = d.levels[+el.dataset.lv], f = el.dataset.f;
          l[f] = f === "on" ? el.checked : f === "v" ? +el.value : el.value;
        } else if (el.dataset.pt !== undefined) {
          const q = d.pts[+el.dataset.pt];
          if (el.dataset.f === "p" && el.value !== "") q.p = Math.round(+el.value / o.tickSize()) * o.tickSize();
          if (el.dataset.f === "t" && el.value) { const t = inputToT(el.value); if (isFinite(t)) q.t = t; }
        } else if (el.dataset.vis) {
          d.vis = { ...(d.vis || {}), [el.dataset.vis]: el.checked };
        }
      };
      box.oninput = (e) => apply(e.target);
      box.onchange = (e) => apply(e.target);

      box.onclick = (e) => {
        const tabBtn = e.target.closest("[data-dtab]");
        if (tabBtn) return render(tabBtn.dataset.dtab);
        const act = e.target.closest("[data-act]");
        if (act && act.dataset.act === "addLevel") {
          d.levels.push({ v: 1.5, c: "#9598a1", on: true });
          return render("style");
        }
        if (act && act.dataset.act === "tpl") return toggleTemplateMenu(box, d, render);
        const tpl = e.target.closest("[data-tpl]");
        if (tpl) return templateAction(tpl.dataset.tpl, tpl.dataset.name, d, box, render);
      };
      box.onclose = () => {
        if (box.returnValue === "ok") save();
        else { for (const k of Object.keys(d)) delete d[k]; Object.assign(d, before); }
      };
      box.returnValue = "";
      box.showModal();
    }

    function toggleTemplateMenu(box, d) {
      const menu = box.querySelector(".tpl-menu");
      if (!menu.hidden) { menu.hidden = true; return; }
      const saved = readJSON(TPL_KEY)[d.type] || {};
      const names = Object.keys(saved).sort();
      menu.innerHTML = `<button type="button" data-tpl="saveas">💾 Save drawing template as…</button>
        <button type="button" data-tpl="default">★ Save as default for ${esc(TYPE_NAME(d.type))}</button>
        <button type="button" data-tpl="factory">↺ Reset to factory default</button>
        ${names.length ? '<div class="tpl-sep"></div>' + names.map((n) => `<div class="tpl-item"><button type="button" data-tpl="apply" data-name="${esc(n)}">${esc(n)}</button><button type="button" class="tpl-del" data-tpl="delete" data-name="${esc(n)}" title="Delete template">✕</button></div>`).join("") : '<div class="tpl-empty">No saved templates for this tool yet</div>'}`;
      menu.hidden = false;
    }

    function templateAction(action, name, d, box, render) {
      const all = readJSON(TPL_KEY);
      all[d.type] = all[d.type] || {};
      if (action === "saveas") {
        const n = prompt(`Template name for ${TYPE_NAME(d.type)}:`, d.text || "");
        if (!n) return;
        all[d.type][n.trim()] = styleOf(d);
        writeJSON(TPL_KEY, all);
        o.status(`Template "${n.trim()}" saved`);
      } else if (action === "default") {
        const defs = readJSON(DEF_KEY);
        defs[d.type] = styleOf(d);
        writeJSON(DEF_KEY, defs);
        o.status(`New ${TYPE_NAME(d.type)} drawings will use this style`);
      } else if (action === "factory") {
        const defs = readJSON(DEF_KEY);
        delete defs[d.type];
        writeJSON(DEF_KEY, defs);
        const fresh = newDrawing(d.type, d.pts[0]);
        for (const k of Object.keys(styleOf(d))) delete d[k];
        Object.assign(d, styleOf(fresh));
      } else if (action === "apply" && all[d.type][name]) {
        for (const k of Object.keys(styleOf(d))) delete d[k];
        Object.assign(d, clone(all[d.type][name]));
      } else if (action === "delete") {
        delete all[d.type][name];
        writeJSON(TPL_KEY, all);
      }
      render(box.dataset.tab || "style");
    }

    function onContext(e) {
      const m = local(e), hit = pick(m.x, m.y);
      const menu = document.getElementById("ctx");
      if (!hit) { menu.hidden = true; return; }
      e.preventDefault(); e.stopPropagation();
      selected = hit.d;
      const d = hit.d;
      menu.innerHTML = `<div class="colors">${SWATCHES.map((c) => `<span class="sw" data-c="${c}" style="background:${c}"></span>`).join("")}</div>
        <div class="widths">${[1, 2, 3, 4].map((wd) => `<button data-w="${wd}" class="${(d.width || 2) === wd ? "on" : ""}"><span style="height:${wd}px"></span></button>`).join("")}</div>
        ${d.type === "text" || d.type === "callout" ? '<button data-a="edit">✎ Edit text</button>' : ""}
        ${d.type === "long" || d.type === "short" ? '<button data-a="flip">⇅ Flip long / short</button>' : ""}
        <button data-a="settings">⚙ Settings…</button>
        <button data-a="clone">⧉ Clone</button>
        <button data-a="front">⤒ Bring to front</button>
        <button data-a="del">🗑 Remove</button>`;
      menu.hidden = false;
      menu.style.left = Math.min(e.clientX, innerWidth - 200) + "px";
      menu.style.top = Math.min(e.clientY, innerHeight - 260) + "px";
      menu.onclick = (ev) => {
        const t = ev.target.closest("[data-c],[data-a],[data-w]");
        if (!t) return;
        const { c, a, w: wd } = t.dataset;
        if (c) d.color = c;
        if (wd) d.width = +wd;
        if (a === "del") remove(d);
        if (a === "clone") { const k = JSON.parse(JSON.stringify(d)); k.id = ++uid; k.pts.forEach((q) => { q.t += o.tf() * 5; }); drawings.push(k); selected = k; }
        if (a === "front") { drawings = drawings.filter((x) => x !== d).concat(d); }
        if (a === "flip") { d.type = d.type === "long" ? "short" : "long"; const e0 = d.pts[0].p; d.pts[1].p = 2 * e0 - d.pts[1].p; d.target = 2 * e0 - d.target; }
        if (a === "edit") editText(d, d.type === "callout" ? xy(d.pts[1]) || m : m, true);
        menu.hidden = true;
        save();
        if (a === "settings") openSettings(d);
      };
    }

    function remove(d) {
      drawings = drawings.filter((x) => x !== d);
      if (selected === d) selected = null;
      save();
    }

    // capture phase on the wrapper: a hit on a drawing never reaches the chart (no panning)
    o.wrap.addEventListener("mousedown", onDown, true);
    o.wrap.addEventListener("dblclick", onDbl, true);
    o.wrap.addEventListener("contextmenu", onContext, true);
    addEventListener("mousemove", onMove);
    addEventListener("mouseup", onUp);
    document.addEventListener("mousedown", (e) => {
      const menu = document.getElementById("ctx");
      if (!menu.contains(e.target)) menu.hidden = true;
      if (flyout && !flyout.contains(e.target) && !e.target.closest(".tool-group")) closeFlyout();
    });

    const SHORTCUTS = { t: "trend", h: "hline", j: "hray", v: "vline", c: "crossline", f: "fib" };
    function onKey(e) {
      if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName) || (dlg && dlg.open)) return false;
      if (e.key === "Escape") { creating = null; zoomBox = null; selected = null; closeFlyout(); setTool(pref.cursor); return true; }
      if ((e.key === "Delete" || e.key === "Backspace") && selected) { remove(selected); return true; }
      if (e.altKey && !e.ctrlKey) {
        const k = e.key.toLowerCase();
        if (e.shiftKey && k === "r") { setTool("rect"); return true; }
        if (SHORTCUTS[k] && !e.shiftKey) { setTool(SHORTCUTS[k]); return true; }
      }
      return false;
    }

    // ---- toolbar ------------------------------------------------------------------------------

    const svg = (id) => `<svg viewBox="0 0 28 28">${I[id] || ""}</svg>`;
    const groupOf = (t) => GROUPS.find((g) => g !== "-" && g.items && g.items.some(([, list]) => list.includes(t)));

    function setTool(t) {
      if (T[t] && T[t].action) { if (t === "zoomout") ts().resetTimeScale(); return; }
      tool = t;
      creating = null;
      if (T[t] && T[t].cursor && t !== "eraser") { pref.cursor = t; o.setCursor(t); }
      const g = groupOf(t);
      if (g) pref.groups[g.id] = t;
      savePref();
      cv.classList.toggle("active", isDrawTool(t) || t === "zoomin");
      o.wrap.classList.toggle("eraser", t === "eraser");
      renderToolbar();
    }

    function closeFlyout() { if (flyout) { flyout.remove(); flyout = null; } }

    function openFlyout(g, btn) {
      closeFlyout();
      flyout = document.createElement("div");
      flyout.className = "flyout";
      if (g.emoji) {
        flyout.innerHTML = `<div class="fly-title">Icons</div><div class="emoji-grid">${EMOJIS.map((x) => `<button data-emoji="${x}">${x}</button>`).join("")}</div>`;
      } else if (g.menu === "hide") {
        flyout.innerHTML = `<button data-act="hideDraw">${svg(visible ? "eyeOff" : "eye")}<span>${visible ? "Hide" : "Show"} drawings</span></button>
          <button data-act="hideInd">${svg("eyeOff")}<span>Hide / show indicators</span></button>
          <button data-act="hidePos">${svg("eyeOff")}<span>Hide / show trade markers</span></button>`;
      } else if (g.menu === "trash") {
        flyout.innerHTML = `<button data-act="rmDraw">${svg("trash")}<span>Remove ${drawings.length} drawing${drawings.length === 1 ? "" : "s"}</span></button>
          <button data-act="rmInd">${svg("trash")}<span>Remove indicators</span></button>
          <button data-act="rmAll">${svg("trash")}<span>Remove drawings &amp; indicators</span></button>`;
      } else if (g.toggle === "magnet") {
        flyout.innerHTML = [["off", "magnet", "Magnet off"], ["weak", "magnet", "Weak magnet"], ["strong", "magnetStrong", "Strong magnet"]]
          .map(([k, ic, name]) => `<button data-magnet="${k}" class="${pref.magnet === k ? "on" : ""}">${svg(ic)}<span>${name}</span></button>`).join("");
      } else {
        flyout.innerHTML = g.items.map(([title, list]) => (title ? `<div class="fly-title">${title}</div>` : '<div class="fly-sep"></div>') +
          list.map((t) => `<button data-tool="${t}" class="${t === tool ? "on" : ""}">${svg(t)}<span>${T[t].name}</span>${T[t].key ? `<kbd>${T[t].key}</kbd>` : ""}</button>`).join("")).join("");
      }
      document.body.appendChild(flyout);
      const r = btn.getBoundingClientRect();
      flyout.style.left = r.right + 6 + "px";
      flyout.style.top = Math.max(8, Math.min(r.top, innerHeight - flyout.offsetHeight - 8)) + "px";
      flyout.addEventListener("click", (e) => {
        const b = e.target.closest("button");
        if (!b) return;
        if (b.dataset.tool) setTool(b.dataset.tool);
        if (b.dataset.emoji) { pref.emoji = b.dataset.emoji; pref.groups.icons = "emoji"; setTool("emoji"); }
        if (b.dataset.magnet) { pref.magnet = b.dataset.magnet; savePref(); renderToolbar(); o.status(b.textContent.trim()); }
        const act = b.dataset.act;
        if (act === "hideDraw") { visible = !visible; renderToolbar(); o.status(visible ? "Drawings shown" : "Drawings hidden"); }
        if (act === "hideInd") o.onIndicators("toggle");
        if (act === "hidePos") o.onMarkers();
        if (act === "rmDraw" || act === "rmAll") {
          if (drawings.length && confirm(`Remove all ${drawings.length} drawings on this chart?`)) { drawings = []; selected = null; save(); }
        }
        if (act === "rmInd" || act === "rmAll") o.onIndicators("remove");
        closeFlyout();
      });
    }

    function groupButton(g) {
      if (g.single) {
        return `<div class="tool-group"><button class="tool ${tool === g.single ? "on" : ""}" data-g="${g.id}" data-tip="${T[g.single].name}">${svg(g.single)}</button></div>`;
      }
      if (g.toggle) {
        const on = g.toggle === "magnet" ? pref.magnet !== "off" : pref[g.toggle];
        const icon = g.toggle === "magnet" ? (pref.magnet === "strong" ? "magnetStrong" : "magnet") : g.toggle === "lock" ? (pref.lock ? "lock" : "unlock") : g.toggle;
        const tip = g.toggle === "magnet" ? `Magnet: ${pref.magnet}` : g.title;
        return `<div class="tool-group"><button class="tool toggle ${on ? "on" : ""}" data-g="${g.id}" data-tip="${tip}">${svg(icon)}</button>${g.toggle === "magnet" ? '<span class="more" data-more="magnet">›</span>' : ""}</div>`;
      }
      if (g.menu) {
        const icon = g.menu === "hide" ? (visible ? "eye" : "eyeOff") : "trash";
        const tip = g.menu === "hide" ? "Hide / show" : "Remove";
        return `<div class="tool-group"><button class="tool ${g.menu === "hide" && !visible ? "on toggle" : ""}" data-g="${g.id}" data-tip="${tip}">${svg(icon)}</button><span class="more" data-more="${g.id}">›</span></div>`;
      }
      const cur = g.emoji ? "emoji" : pref.groups[g.id] && groupOf(pref.groups[g.id]) === g ? pref.groups[g.id] : g.items[0][1][0];
      const icon = g.emoji ? "icons" : cur;
      const on = g.emoji ? tool === "emoji" : tool === cur;
      return `<div class="tool-group"><button class="tool ${on ? "on" : ""}" data-g="${g.id}" data-tip="${g.emoji ? "Icons" : T[cur].name}">${g.emoji && pref.groups.icons ? `<span class="emoji">${pref.emoji}</span>` : svg(icon)}</button><span class="more" data-more="${g.id}">›</span></div>`;
    }

    function renderToolbar() {
      if (!bar) return;
      bar.innerHTML = GROUPS.map((g) => (g === "-" ? '<span class="sep"></span>' : groupButton(g))).join("");
    }

    function mountToolbar(el) {
      bar = el;
      el.addEventListener("click", (e) => {
        const more = e.target.closest("[data-more]");
        const g = GROUPS.find((x) => x !== "-" && x.id === (more ? more.dataset.more : (e.target.closest("[data-g]") || {}).dataset?.g));
        if (!g) return;
        const btn = e.target.closest(".tool-group").querySelector(".tool");
        if (more || g.emoji && !pref.groups.icons) return openFlyout(g, btn);
        if (g.single) return setTool(tool === g.single ? pref.cursor : g.single);
        if (g.toggle === "magnet") { pref.magnet = pref.magnet === "off" ? "weak" : "off"; savePref(); renderToolbar(); return o.status(`Magnet ${pref.magnet}`); }
        if (g.toggle) {
          pref[g.toggle] = !pref[g.toggle];
          savePref(); renderToolbar();
          if (g.toggle === "sync") { reload(); o.status(pref.sync ? "Drawings shared across all sessions" : "Drawings kept per session"); }
          if (g.toggle === "lock") o.status(pref.lock ? "Drawings locked" : "Drawings unlocked");
          if (g.toggle === "stay") o.status(pref.stay ? "Stays in drawing mode" : "Back to cursor after each drawing");
          return;
        }
        if (g.menu === "hide") { visible = !visible; renderToolbar(); return o.status(visible ? "Drawings shown" : "Drawings hidden"); }
        if (g.menu === "trash") return openFlyout(g, btn);
        const cur = g.emoji ? "emoji" : pref.groups[g.id] && groupOf(pref.groups[g.id]) === g ? pref.groups[g.id] : g.items[0][1][0];
        setTool(tool === cur && !T[cur].cursor ? pref.cursor : cur);
      });
      // long-press opens the group menu too, like TradingView
      let pressT = null;
      el.addEventListener("mousedown", (e) => {
        const b = e.target.closest(".tool");
        if (!b) return;
        const g = GROUPS.find((x) => x !== "-" && x.id === b.dataset.g);
        if (g && (g.items || g.emoji)) pressT = setTimeout(() => openFlyout(g, b), 450);
      });
      addEventListener("mouseup", () => clearTimeout(pressT));
      o.setCursor(pref.cursor);
      setTool(pref.cursor);
    }

    return { redraw, load, mountToolbar, onKey, setTool, get count() { return drawings.length; } };
  }

  window.Drawings = { create };
})();
