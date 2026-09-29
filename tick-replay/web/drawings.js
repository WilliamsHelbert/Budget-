/* Drawing tools for Lightweight Charts (which has none built in).
 *
 * Drawings live in chart space: time (display seconds, same axis as the candles) and
 * price. They are painted on a canvas over the chart every frame, so they follow
 * panning, zooming and live candles. Time <-> x goes through the candles' logical
 * index, which also works to the right of the last candle and across timeframes.
 */
(() => {
  "use strict";

  const FIB_LEVELS = [
    [0, "#787b86"], [0.236, "#f23645"], [0.382, "#ff9800"], [0.5, "#4caf50"],
    [0.618, "#089981"], [0.786, "#00bcd4"], [1, "#787b86"],
  ];
  const HIT = 6;          // px tolerance for picking lines
  const HANDLE = 5;       // handle radius
  const SWATCHES = ["#2962ff", "#f5a623", "#26a69a", "#ef5350", "#e040fb", "#ffffff", "#9598a1"];

  const ICONS = {
    cursor: '<path d="M5 3l14 8-6 1.5L10 19z"/>',
    trend: '<path d="M4 19 20 5"/><circle cx="4" cy="19" r="1.8"/><circle cx="20" cy="5" r="1.8"/>',
    ray: '<path d="M4 18 21 6"/><circle cx="4" cy="18" r="1.8"/><circle cx="12" cy="12.4" r="1.8"/>',
    hline: '<path d="M2 12h20"/><circle cx="12" cy="12" r="1.8"/>',
    hray: '<path d="M6 12h16"/><circle cx="6" cy="12" r="1.8"/>',
    vline: '<path d="M12 2v20"/><circle cx="12" cy="12" r="1.8"/>',
    rect: '<rect x="4" y="6" width="16" height="12" rx="1"/>',
    fib: '<path d="M3 5h18M3 9.5h18M3 14h18M3 19h18"/><path d="M5 19 19 5" stroke-dasharray="2 2"/>',
    long: '<rect x="4" y="4" width="16" height="8" fill="rgba(38,166,154,.35)" stroke="#26a69a"/><rect x="4" y="12" width="16" height="7" fill="rgba(239,83,80,.3)" stroke="#ef5350"/>',
    short: '<rect x="4" y="5" width="16" height="7" fill="rgba(239,83,80,.3)" stroke="#ef5350"/><rect x="4" y="12" width="16" height="8" fill="rgba(38,166,154,.35)" stroke="#26a69a"/>',
    text: '<path d="M5 6V4h14v2M12 4v16M9 20h6"/>',
    measure: '<path d="M4 20 20 4M7 20l-3-3M11 16l-2-2M15 12l-2-2M19 8l-2-2"/>',
    magnet: '<path d="M6 4v8a6 6 0 0 0 12 0V4h-4v8a2 2 0 0 1-4 0V4z"/><path d="M6 8h4M14 8h4"/>',
    eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  };
  const TOOLS = [
    ["cursor", "Cursor (Esc)"],
    "-",
    ["trend", "Trend line"], ["ray", "Ray"], ["hline", "Horizontal line"], ["hray", "Horizontal ray"], ["vline", "Vertical line"],
    "-",
    ["rect", "Rectangle"], ["fib", "Fib retracement"],
    "-",
    ["long", "Long position"], ["short", "Short position"],
    "-",
    ["text", "Text"], ["measure", "Measure (price & time range)"],
    "-",
    ["magnet", "Magnet: snap to candle OHLC", "toggle"], ["eye", "Hide / show drawings", "toggle"], ["trash", "Remove all drawings", "action"],
  ];
  const TWO_POINT = new Set(["trend", "ray", "rect", "fib", "long", "short", "measure"]);

  function create(o) {
    // o: { chart, series(), canvas, wrap, times(), barAt(i), tf(), tickSize(), pointValue(), color(), rr(), status(msg) }
    const cv = o.canvas, ctx = cv.getContext("2d");
    let drawings = [], key = null, tool = "cursor", selected = null, creating = null, drag = null;
    let magnet = false, visible = true, mouse = null, toolbarEl = null;
    let uid = Date.now();

    // ---- coordinate conversion ------------------------------------------------

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
      const x = ts().logicalToCoordinate(l);
      return x === null ? null : x;
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

    function snap(x, y) {
      let t = xToTime(x), p = yToPrice(y);
      if (t === null || p === null) return null;
      if (magnet) {
        const l = Math.round(ts().coordinateToLogical(x)), bar = o.barAt(l);
        if (bar) {
          t = bar.time;
          p = [bar.open, bar.high, bar.low, bar.close].reduce((a, v) => (Math.abs(priceToY(v) - y) < Math.abs(priceToY(a) - y) ? v : a));
        }
      }
      return { t, p: roundTick(p) };
    }

    const pane = () => ({ w: ts().width(), h: o.wrap.clientHeight - ts().height() });

    // ---- persistence ------------------------------------------------------------

    function save() {
      if (!key) return;
      try { localStorage.setItem(key, JSON.stringify(drawings)); } catch { /* storage full or blocked */ }
    }
    function load(k) {
      key = k;
      selected = creating = drag = null;
      try { drawings = JSON.parse(localStorage.getItem(k) || "[]"); } catch { drawings = []; }
    }

    // ---- geometry helpers ---------------------------------------------------------

    function xy(pt) {
      const x = timeToX(pt.t), y = priceToY(pt.p);
      return x === null || y === null ? null : { x, y };
    }
    function distSeg(px, py, ax, ay, bx, by) {
      const dx = bx - ax, dy = by - ay, len = dx * dx + dy * dy;
      let k = len ? ((px - ax) * dx + (py - ay) * dy) / len : 0;
      k = Math.max(0, Math.min(1, k));
      return Math.hypot(px - (ax + k * dx), py - (ay + k * dy));
    }
    function rayEnd(a, b, w) {
      if (b.x === a.x) return { x: b.x, y: b.y > a.y ? 1e5 : -1e5 };
      const k = (b.y - a.y) / (b.x - a.x), x = b.x > a.x ? w : 0;
      return { x, y: a.y + k * (x - a.x) };
    }

    /** Draggable points of a drawing, in chart space. */
    function handles(d) {
      const [a, b] = d.pts;
      switch (d.type) {
        case "hline": return [{ t: xToTime(pane().w / 2), p: a.p }];
        case "vline": return [{ t: a.t, p: yToPrice(pane().h / 2) }];
        case "hray": case "text": return [a];
        case "long": case "short": return [a, { t: a.t, p: b.p }, { t: a.t, p: d.target }, { t: b.t, p: a.p }];
        case "rect": return [a, b, { t: a.t, p: b.p }, { t: b.t, p: a.p }];
        default: return [a, b];
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
        const q = hs[i].t === null || hs[i].p === null ? null : xy(hs[i]);
        if (q && Math.hypot(q.x - x, q.y - y) <= HANDLE + 4) return i;
      }
      return -1;
    }

    function hitBody(d, x, y) {
      const { w } = pane();
      const A = xy(d.pts[0]);
      if (d.type === "hline") { const yy = priceToY(d.pts[0].p); return yy !== null && Math.abs(yy - y) < HIT; }
      if (!A) return false;
      if (d.type === "vline") return Math.abs(A.x - x) < HIT;
      if (d.type === "hray") return Math.abs(A.y - y) < HIT && x >= A.x - HIT;
      if (d.type === "text") {
        ctx.font = "600 13px sans-serif";
        const tw = ctx.measureText(d.text || "").width;
        return x >= A.x - 4 && x <= A.x + tw + 4 && y >= A.y - 16 && y <= A.y + 4;
      }
      const B = xy(d.pts[1]);
      if (!B) return false;
      if (d.type === "trend") return distSeg(x, y, A.x, A.y, B.x, B.y) < HIT;
      if (d.type === "ray") { const E = rayEnd(A, B, w); return distSeg(x, y, A.x, A.y, E.x, E.y) < HIT; }
      let y1 = Math.min(A.y, B.y), y2 = Math.max(A.y, B.y);
      if (d.type === "long" || d.type === "short") {
        const T = priceToY(d.target);
        y1 = Math.min(y1, T); y2 = Math.max(y2, T);
      }
      const x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x);
      return x >= x1 - HIT && x <= x2 + HIT && y >= y1 - HIT && y <= y2 + HIT;
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

    // ---- painting -------------------------------------------------------------------

    function alpha(hex, a) {
      const n = parseInt(hex.slice(1), 16);
      return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
    }
    function label(text, x, y, bg, fg = "#fff", align = "left") {
      ctx.font = "600 11px ui-monospace, Menlo, Consolas, monospace";
      const w = ctx.measureText(text).width + 10, h = 18;
      const lx = align === "center" ? x - w / 2 : align === "right" ? x - w : x;
      ctx.fillStyle = bg;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(lx, y - h / 2, w, h, 4) : ctx.rect(lx, y - h / 2, w, h);
      ctx.fill();
      ctx.fillStyle = fg;
      ctx.textBaseline = "middle";
      ctx.fillText(text, lx + 5, y + 0.5);
    }
    const fmtP = (p) => p.toFixed(2);

    function paintPosition(d, A, B) {
      const T = priceToY(d.target), long = d.type === "long";
      const x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x), w = Math.max(x2 - x1, 1);
      ctx.fillStyle = "rgba(38,166,154,.18)";
      ctx.fillRect(x1, Math.min(A.y, T), w, Math.abs(T - A.y));
      ctx.fillStyle = "rgba(239,83,80,.18)";
      ctx.fillRect(x1, Math.min(A.y, B.y), w, Math.abs(B.y - A.y));
      ctx.strokeStyle = "#9598a1"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x1, A.y); ctx.lineTo(x2, A.y); ctx.stroke();
      const risk = Math.abs(d.pts[0].p - d.pts[1].p), reward = Math.abs(d.target - d.pts[0].p);
      const tick = o.tickSize(), pv = o.pointValue();
      const cx = x1 + w / 2;
      label(`Target ${fmtP(d.target)} · ${reward.toFixed(2)} (${Math.round(reward / tick)}t) · $${(reward * pv).toFixed(0)}`, cx, T + (long ? -12 : 12), "#26a69a", "#fff", "center");
      label(`Stop ${fmtP(d.pts[1].p)} · ${risk.toFixed(2)} (${Math.round(risk / tick)}t) · $${(risk * pv).toFixed(0)}`, cx, B.y + (long ? 12 : -12), "#ef5350", "#fff", "center");
      label(`${long ? "Long" : "Short"} ${fmtP(d.pts[0].p)} · R:R ${risk ? (reward / risk).toFixed(2) : "–"}`, cx, A.y, "#2a2e39", "#fff", "center");
    }

    function paint(d, sel) {
      const { w, h } = pane();
      ctx.strokeStyle = d.color;
      ctx.lineWidth = d.width || 2;
      ctx.setLineDash([]);
      const A = d.type === "hline" ? null : xy(d.pts[0]);
      if (d.type === "hline") {
        const y = priceToY(d.pts[0].p);
        if (y === null) return;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
        label(fmtP(d.pts[0].p), w - 4, y, d.color, "#fff", "right");
        return;
      }
      if (!A) return;
      if (d.type === "vline") { ctx.beginPath(); ctx.moveTo(A.x, 0); ctx.lineTo(A.x, h); ctx.stroke(); return; }
      if (d.type === "hray") {
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(w, A.y); ctx.stroke();
        label(fmtP(d.pts[0].p), w - 4, A.y, d.color, "#fff", "right");
        return;
      }
      if (d.type === "text") {
        ctx.font = "600 13px -apple-system, Segoe UI, sans-serif";
        ctx.fillStyle = d.color; ctx.textBaseline = "alphabetic";
        ctx.fillText(d.text || "", A.x, A.y);
        return;
      }
      const B = xy(d.pts[1]);
      if (!B) return;
      switch (d.type) {
        case "trend":
          ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
          break;
        case "ray": {
          const E = rayEnd(A, B, w);
          ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(E.x, E.y); ctx.stroke();
          break;
        }
        case "rect":
          ctx.fillStyle = alpha(d.color, 0.15);
          ctx.fillRect(Math.min(A.x, B.x), Math.min(A.y, B.y), Math.abs(B.x - A.x), Math.abs(B.y - A.y));
          ctx.lineWidth = 1.5;
          ctx.strokeRect(Math.min(A.x, B.x), Math.min(A.y, B.y), Math.abs(B.x - A.x), Math.abs(B.y - A.y));
          break;
        case "fib": {
          // level 1 at the first click, 0 at the second (TradingView convention)
          const x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x), p0 = d.pts[1].p, p1 = d.pts[0].p;
          let prevY = null;
          for (const [lv, col] of FIB_LEVELS) {
            const p = p0 + (p1 - p0) * lv, y = priceToY(p);
            if (y === null) continue;
            if (prevY !== null) { ctx.fillStyle = alpha(col, 0.08); ctx.fillRect(x1, Math.min(y, prevY), x2 - x1, Math.abs(y - prevY)); }
            ctx.strokeStyle = col; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(x1, y); ctx.lineTo(x2, y); ctx.stroke();
            ctx.font = "11px ui-monospace, Menlo, monospace"; ctx.fillStyle = col; ctx.textBaseline = "bottom";
            ctx.fillText(`${lv} (${fmtP(p)})`, x1 + 4, y - 2);
            prevY = y;
          }
          ctx.strokeStyle = alpha(d.color, 0.6); ctx.setLineDash([4, 4]);
          ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
          ctx.setLineDash([]);
          break;
        }
        case "long": case "short":
          paintPosition(d, A, B);
          break;
        case "measure": {
          const dp = d.pts[1].p - d.pts[0].p, up = dp >= 0, col = up ? "#2962ff" : "#ef5350";
          ctx.fillStyle = alpha(col, 0.15);
          ctx.fillRect(Math.min(A.x, B.x), Math.min(A.y, B.y), Math.abs(B.x - A.x), Math.abs(B.y - A.y));
          ctx.strokeStyle = col; ctx.lineWidth = 1;
          const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
          ctx.beginPath(); ctx.moveTo(mx, A.y); ctx.lineTo(mx, B.y); ctx.moveTo(A.x, my); ctx.lineTo(B.x, my); ctx.stroke();
          const secs = Math.abs(d.pts[1].t - d.pts[0].t), bars = Math.round(secs / o.tf());
          const dur = secs < 60 ? `${Math.round(secs)}s` : secs < 3600 ? `${Math.floor(secs / 60)}m ${Math.round(secs % 60)}s` : `${Math.floor(secs / 3600)}h ${Math.round((secs % 3600) / 60)}m`;
          const pct = (dp / d.pts[0].p) * 100;
          label(`${up ? "+" : ""}${dp.toFixed(2)} (${pct.toFixed(2)}%) ${Math.round(dp / o.tickSize())}t · $${(Math.abs(dp) * o.pointValue()).toFixed(0)}`,
            mx, Math.max(A.y, B.y) + 14, col, "#fff", "center");
          label(`${bars} bars · ${dur}`, mx, Math.max(A.y, B.y) + 34, col, "#fff", "center");
          break;
        }
      }
      if (sel || d === hoverD) {
        for (const hp of handles(d)) {
          const q = hp.t === null || hp.p === null ? null : xy(hp);
          if (!q) continue;
          ctx.fillStyle = "#0b0e14"; ctx.strokeStyle = sel ? "#4f7cff" : "#9598a1"; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(q.x, q.y, HANDLE, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        }
      }
    }

    let hoverD = null;
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
      ctx.restore();
    }

    // ---- interaction --------------------------------------------------------------------

    const local = (e) => { const r = o.wrap.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
    const inPane = ({ x, y }) => { const { w, h } = pane(); return x >= 0 && y >= 0 && x <= w && y <= h; };

    function newDrawing(type, pt) {
      const d = { id: ++uid, type, color: type === "long" || type === "short" ? "#9598a1" : o.color(), width: 2, pts: [pt, { ...pt }] };
      if (type === "hline" || type === "vline" || type === "hray" || type === "text") d.pts = [pt];
      if (type === "long" || type === "short") d.target = pt.p;  // set properly on the next mouse move
      return d;
    }

    function finish(d) {
      if (d.type === "long" || d.type === "short") {
        const risk = d.pts[0].p - d.pts[1].p;
        if (!risk) d.pts[1].p = d.pts[0].p + (d.type === "long" ? -1 : 1) * o.tickSize() * 20;
        const r = d.pts[0].p - d.pts[1].p;
        d.target = roundTick(d.pts[0].p + r * o.rr());
        if (d.pts[1].t === d.pts[0].t) d.pts[1].t = d.pts[0].t + o.tf() * 20;
      }
      drawings.push(d);
      selected = d;
      creating = null;
      save();
      setTool("cursor");
    }

    function onDown(e) {
      if (e.button !== 0) return;
      const m = local(e);
      if (!inPane(m)) return;
      if (tool !== "cursor") {
        e.preventDefault(); e.stopPropagation();
        const pt = snap(m.x, m.y);
        if (!pt) return;
        if (creating) { finish(creating); return; }           // second click
        const d = newDrawing(tool, pt);
        if (d.type === "text") { editText(d, m); return; }
        if (!TWO_POINT.has(d.type)) { finish(d); return; }
        creating = d;
        creating.downAt = m;
        return;
      }
      const hit = pick(m.x, m.y);
      if (!hit) { if (selected) { selected = null; } return; }
      e.preventDefault(); e.stopPropagation();                 // keep the chart from panning
      selected = hit.d;
      drag = { d: hit.d, handle: hit.handle, start: snap(m.x, m.y) || { t: 0, p: 0 }, orig: JSON.parse(JSON.stringify(hit.d)) };
    }

    function onMove(e) {
      const m = local(e);
      mouse = m;
      if (creating) {
        const pt = snap(m.x, m.y);
        if (pt) {
          creating.pts[1] = pt;
          if (creating.type === "long" || creating.type === "short") {
            creating.target = roundTick(creating.pts[0].p + (creating.pts[0].p - pt.p) * o.rr());
          }
        }
        return;
      }
      if (drag) {
        const pt = snap(m.x, m.y);
        if (!pt) return;
        const d = drag.d;
        if (drag.handle >= 0) setHandle(d, drag.handle, pt);
        else {
          const dt = pt.t - drag.start.t, dp = pt.p - drag.start.p;
          d.pts = drag.orig.pts.map((q) => ({ t: q.t + dt, p: roundTick(q.p + dp) }));
          if (d.target !== undefined) d.target = roundTick(drag.orig.target + dp);
        }
        return;
      }
      if (tool === "cursor" && inPane(m)) {
        const hit = pick(m.x, m.y);
        hoverD = hit ? hit.d : null;
        o.wrap.style.cursor = hit ? (hit.handle >= 0 ? "grab" : "move") : "";
      }
    }

    function onUp(e) {
      if (creating && creating.downAt) {
        const m = local(e);
        if (Math.hypot(m.x - creating.downAt.x, m.y - creating.downAt.y) > 6) finish(creating);  // drag-to-draw
        else delete creating.downAt;                                                           // click, click
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
      input.focus();
      const done = (ok) => {
        box.hidden = true;
        input.onkeydown = input.onblur = null;
        if (ok && input.value.trim()) {
          d.text = input.value.trim();
          if (!existing) finish(d); else save();
        } else if (!existing) setTool("cursor");
      };
      input.onkeydown = (ev) => { if (ev.key === "Enter") done(true); if (ev.key === "Escape") done(false); ev.stopPropagation(); };
      input.onblur = () => done(true);
    }

    function onDbl(e) {
      const m = local(e), hit = pick(m.x, m.y);
      if (hit && hit.d.type === "text") { e.stopPropagation(); editText(hit.d, m, true); }
    }

    function onContext(e) {
      const m = local(e), hit = pick(m.x, m.y);
      const menu = document.getElementById("ctx");
      if (!hit) { menu.hidden = true; return; }
      e.preventDefault(); e.stopPropagation();
      selected = hit.d;
      const d = hit.d;
      menu.innerHTML = `<div class="colors">${SWATCHES.map((c) => `<span class="sw" data-c="${c}" style="background:${c}"></span>`).join("")}</div>
        ${d.type === "text" ? '<button data-a="edit">✎ Edit text</button>' : ""}
        ${d.type === "long" || d.type === "short" ? '<button data-a="flip">⇅ Flip long / short</button>' : ""}
        <button data-a="clone">⧉ Clone</button>
        <button data-a="del">🗑 Delete</button>`;
      menu.hidden = false;
      menu.style.left = Math.min(e.clientX, innerWidth - 190) + "px";
      menu.style.top = Math.min(e.clientY, innerHeight - 200) + "px";
      menu.onclick = (ev) => {
        const c = ev.target.dataset.c, a = ev.target.dataset.a;
        if (c) d.color = c;
        if (a === "del") remove(d);
        if (a === "clone") { const k = JSON.parse(JSON.stringify(d)); k.id = ++uid; k.pts.forEach((q) => { q.t += o.tf() * 5; }); drawings.push(k); selected = k; }
        if (a === "flip") {
          d.type = d.type === "long" ? "short" : "long";
          const e0 = d.pts[0].p; d.pts[1].p = 2 * e0 - d.pts[1].p; d.target = 2 * e0 - d.target;
        }
        if (a === "edit") editText(d, m, true);
        menu.hidden = true;
        save();
      };
    }
    document.addEventListener("mousedown", (e) => { const menu = document.getElementById("ctx"); if (!menu.contains(e.target)) menu.hidden = true; });

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

    function onKey(e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return false;
      if (e.key === "Escape") { creating = null; selected = null; setTool("cursor"); return true; }
      if ((e.key === "Delete" || e.key === "Backspace") && selected) { remove(selected); return true; }
      return false;
    }

    // ---- toolbar ---------------------------------------------------------------------

    function setTool(t) {
      tool = t;
      creating = null;
      cv.classList.toggle("active", t !== "cursor");
      if (toolbarEl) for (const b of toolbarEl.querySelectorAll("[data-tool]")) b.classList.toggle("on", b.dataset.tool === t);
    }

    function mountToolbar(el) {
      toolbarEl = el;
      el.innerHTML = TOOLS.map((x) => x === "-" ? '<span class="sep"></span>'
        : `<button class="tool ${x[2] || ""}" ${x[2] ? `data-${x[2]}="${x[0]}"` : `data-tool="${x[0]}"`} data-tip="${x[1]}" aria-label="${x[1]}"><svg viewBox="0 0 24 24">${ICONS[x[0]]}</svg></button>`).join("");
      el.addEventListener("click", (e) => {
        const b = e.target.closest("button");
        if (!b) return;
        if (b.dataset.tool) setTool(b.dataset.tool === tool && tool !== "cursor" ? "cursor" : b.dataset.tool);
        if (b.dataset.toggle === "magnet") { magnet = !magnet; b.classList.toggle("on", magnet); o.status(`Magnet ${magnet ? "on" : "off"}`); }
        if (b.dataset.toggle === "eye") { visible = !visible; b.classList.toggle("on", !visible); o.status(visible ? "Drawings shown" : "Drawings hidden"); }
        if (b.dataset.action === "trash") {
          if (drawings.length && confirm(`Remove all ${drawings.length} drawings on this chart?`)) { drawings = []; selected = null; save(); }
        }
      });
      setTool("cursor");
    }

    return { redraw, load, mountToolbar, onKey, setTool, get count() { return drawings.length; } };
  }

  window.Drawings = { create };
})();
