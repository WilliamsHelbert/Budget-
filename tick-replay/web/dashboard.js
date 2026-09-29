/* Tick Replay workspace: dashboard, backtest sessions, trades, analytics and data. */
(() => {
  "use strict";

  // ---- helpers -------------------------------------------------------------

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) {
      let msg = r.statusText;
      try { msg = (await r.json()).detail || msg; } catch { /* not JSON */ }
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return r.json();
  }
  const post = (path, body, method = "POST") =>
    api(path, { method, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

  const TZ = "America/New_York";
  const tzParts = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", weekday: "short",
  });
  function nyParts(ms) {
    return Object.fromEntries(tzParts.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  }
  function nyOffsetSec(ms) {
    const p = nyParts(ms);
    const wall = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
    return Math.round((wall - Math.floor(ms / 1000) * 1000) / 1000);
  }
  /** "YYYY-MM-DDTHH:MM" New York wall time -> UTC ms. */
  function parseNY(value) {
    const [d, t = "00:00"] = value.split("T");
    const [Y, M, D] = d.split("-").map(Number);
    const [h, m] = t.split(":").map(Number);
    const wall = Date.UTC(Y, M - 1, D, h, m);
    let ms = wall - nyOffsetSec(wall) * 1000;
    return wall - nyOffsetSec(ms) * 1000;
  }
  const nyDate = (ms) => { const p = nyParts(ms); return `${p.year}-${p.month}-${p.day}`; };
  const nyClock = (ms) => new Date(ms + nyOffsetSec(ms) * 1000).toISOString().slice(11, 23);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const shortDate = (iso) => { const [y, m, d] = iso.split("-"); return `${MONTHS[+m - 1]} ${+d}, ${y}`; };
  const monthLabel = (key) => { const [y, m] = key.split("-"); return `${MONTHS[+m - 1]} ${y.slice(2)}`; };

  const money = (v, dec = 2) => (v < 0 ? "−$" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const signedMoney = (v) => (v > 0 ? "+" : "") + money(v);
  const pct = (v) => (isFinite(v) ? (v * 100).toFixed(1) + "%" : "–");
  const cls = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "");

  /** Up to three units, starting at the largest non-zero one: "9d 23h 41m", "18y 16d 2h". */
  function duration(ms, units) {
    const table = { y: 365 * 86400, d: 86400, h: 3600, m: 60 };
    const parts = [];
    let left = Math.floor(ms / 1000);
    for (const u of units) {
      const n = Math.floor(left / table[u]);
      left -= n * table[u];
      if ((n || parts.length) && parts.length < 3) parts.push(`${n}<small>${u}</small>`);
    }
    return parts.join("") || `0<small>${units[units.length - 1]}</small>`;
  }

  const ICON = {
    cal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
    wallet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="6" width="18" height="14" rx="2"/><path d="M16 13h2M3 10h18"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5v15l13-7.5z"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 20h4L19 9l-4-4L4 16z"/></svg>',
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>',
    stats: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 20V10M12 20V4M19 20v-7"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
    hist: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 8v4l3 2"/></svg>',
    trades: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17 17 7M9 7h8v8"/></svg>',
    target: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/></svg>',
    dollar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v18M17 7H9.5a3 3 0 0 0 0 6h5a3 3 0 0 1 0 6H6"/></svg>',
    scale: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v18M5 7h14M5 7l-3 7a4 4 0 0 0 6 0zM19 7l-3 7a4 4 0 0 0 6 0z"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>',
  };

  // ---- data ----------------------------------------------------------------

  let symbols = [];
  let backtests = [];
  const daysCache = new Map();

  async function loadAll() {
    [symbols, backtests] = await Promise.all([api("/api/symbols"), api("/api/backtests")]);
  }

  const allTrades = (list = backtests) =>
    list.flatMap((b) => b.trades.map((t) => ({ ...t, session: b.name, sid: b.id })))
      .sort((a, b) => a.exit_ts - b.exit_ts);

  function stats(trades) {
    const n = trades.length;
    const wins = trades.filter((t) => t.pnl > 0), losses = trades.filter((t) => t.pnl < 0);
    const gw = wins.reduce((a, t) => a + t.pnl, 0), gl = losses.reduce((a, t) => a + t.pnl, 0);
    let eq = 0, peak = 0, dd = 0;
    for (const t of trades) { eq += t.pnl; peak = Math.max(peak, eq); dd = Math.min(dd, eq - peak); }
    const longs = trades.filter((t) => t.side > 0), shorts = trades.filter((t) => t.side < 0);
    const wr = (list) => (list.length ? list.filter((t) => t.pnl > 0).length / list.length : NaN);
    return {
      n, net: gw + gl, winRate: n ? wins.length / n : NaN,
      pf: gl ? gw / -gl : gw > 0 ? Infinity : NaN,
      avgWin: wins.length ? gw / wins.length : 0, avgLoss: losses.length ? gl / losses.length : 0,
      expectancy: n ? (gw + gl) / n : 0, maxDD: dd,
      best: n ? Math.max(...trades.map((t) => t.pnl)) : 0, worst: n ? Math.min(...trades.map((t) => t.pnl)) : 0,
      longs: longs.length, shorts: shorts.length, longWR: wr(longs), shortWR: wr(shorts),
      fees: trades.reduce((a, t) => a + (t.fees || 0), 0),
    };
  }

  function equity(b) { return b.balance + b.trades.reduce((a, t) => a + t.pnl, 0); }

  /** Trading days (weekdays with data) still ahead in a session. */
  function remainingDays(b) {
    const set = new Set();
    for (const s of symbols) if (b.symbols.includes(s.symbol)) s.days.forEach((d) => set.add(d));
    const cur = nyDate(b.current_ts), end = nyDate(b.end_ts);
    return [...set].filter((d) => d > cur && d <= end && ![0, 6].includes(new Date(d + "T12:00:00Z").getUTCDay())).length;
  }

  // ---- charts (hand-rolled SVG, one series each, hover tooltips) ------------

  const charts = [];   // re-drawn on resize
  const NS = "http://www.w3.org/2000/svg";

  function niceTicks(lo, hi, n = 4) {
    if (lo === hi) { hi = lo + 1; }
    const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const out = [];
    const top = Math.ceil(hi / step - 1e-9) * step;
    for (let v = Math.floor(lo / step + 1e-9) * step; v <= top + step * 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  function roundedBar(x, y0, y1, w, r = 4) {
    // rounded at the data end only; anchored square to the baseline
    const up = y1 < y0, h = Math.abs(y1 - y0);
    r = Math.min(r, w / 2, h);
    if (up) return `M${x},${y0}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 + r}V${y0}Z`;
    return `M${x},${y0}V${y1 - r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 - r}V${y0}Z`;
  }

  /** Vertical bars. items: [{label, value, tip}] ; opts.color or opts.polarity. */
  function barChart(el, items, opts = {}) {
    const draw = () => {
      const W = el.clientWidth, H = el.clientHeight;
      if (!items.length || items.every((i) => !i.value)) {
        el.innerHTML = `<div class="empty-chart">${opts.empty || "No data yet"}</div>`;
        return;
      }
      const L = 44, R = 6, T = 8, B = 24;
      const vals = items.map((i) => i.value);
      const ticks = niceTicks(Math.min(0, ...vals), Math.max(0, ...vals));
      const lo = ticks[0], hi = ticks[ticks.length - 1];
      const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
      const slot = (W - L - R) / items.length, bw = Math.min(46, slot * 0.62);
      let s = `<svg viewBox="0 0 ${W} ${H}">`;
      for (const t of ticks) {
        s += `<line class="${t === 0 ? "zero-line" : "grid-line"}" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/>`;
        s += `<text class="axis" x="${L - 8}" y="${y(t) + 3}" text-anchor="end">${esc(opts.axis ? opts.axis(t) : t)}</text>`;
      }
      const every = Math.ceil(items.length / Math.max(1, Math.floor((W - L) / 56)));
      items.forEach((it, k) => {
        const x = L + k * slot + (slot - bw) / 2;
        const color = opts.polarity ? (it.value >= 0 ? "var(--up)" : "var(--down)") : opts.color || "var(--gold)";
        if (it.value) s += `<path class="bar" d="${roundedBar(x, y(0), y(it.value), bw)}" fill="${color}"/>`;
        s += `<rect class="hit" x="${L + k * slot}" y="${T}" width="${slot}" height="${H - T - B}" data-tip="${esc(it.tip)}"/>`;
        if (k % every === 0) s += `<text class="axis" x="${x + bw / 2}" y="${H - 6}" text-anchor="middle">${esc(it.label)}</text>`;
      });
      el.innerHTML = s + "</svg>";
    };
    charts.push(draw);
    draw();
  }

  /** Horizontal bars for categories. */
  function hbarChart(el, items, opts = {}) {
    const draw = () => {
      if (!items.length) { el.innerHTML = `<div class="empty-chart">${opts.empty || "No data yet"}</div>`; return; }
      const W = el.clientWidth, H = el.clientHeight, L = 70, R = 44;
      const max = Math.max(...items.map((i) => i.value)) || 1;
      const rowH = Math.min(38, (H - 8) / items.length), bh = Math.min(18, rowH * 0.6);
      let s = `<svg viewBox="0 0 ${W} ${H}">`;
      items.forEach((it, k) => {
        const cy = 4 + k * rowH + rowH / 2, w = ((W - L - R) * it.value) / max;
        s += `<text class="axis" x="${L - 10}" y="${cy + 3}" text-anchor="end" style="font-weight:700">${esc(it.label)}</text>`;
        const r = Math.min(4, bh / 2, w);
        s += `<path class="bar" fill="${opts.color || "var(--accent)"}" d="M${L},${cy - bh / 2}H${L + w - r}Q${L + w},${cy - bh / 2} ${L + w},${cy - bh / 2 + r}V${cy + bh / 2 - r}Q${L + w},${cy + bh / 2} ${L + w - r},${cy + bh / 2}H${L}Z"/>`;
        s += `<text class="axis" x="${L + w + 6}" y="${cy + 3}" style="fill:var(--text)">${esc(it.value)}</text>`;
        s += `<rect class="hit" x="0" y="${cy - rowH / 2}" width="${W}" height="${rowH}" data-tip="${esc(it.tip)}"/>`;
      });
      el.innerHTML = s + "</svg>";
    };
    charts.push(draw);
    draw();
  }

  /** Equity-style line with area and a crosshair tooltip. points: [{v, tip}] */
  function lineChart(el, points, opts = {}) {
    const draw = () => {
      if (points.length < 2) { el.innerHTML = `<div class="empty-chart">${opts.empty || "No data yet"}</div>`; return; }
      const W = el.clientWidth, H = el.clientHeight, L = 58, R = 10, T = 10, B = 20;
      const vals = points.map((p) => p.v);
      const ticks = niceTicks(Math.min(...vals), Math.max(...vals));
      const lo = ticks[0], hi = ticks[ticks.length - 1];
      const x = (k) => L + (k / (points.length - 1)) * (W - L - R);
      const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
      const up = vals[vals.length - 1] >= vals[0];
      const color = up ? "var(--up)" : "var(--down)";
      const line = points.map((p, k) => `${k ? "L" : "M"}${x(k).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
      let s = `<svg viewBox="0 0 ${W} ${H}"><defs><linearGradient id="eqg" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0" stop-color="${up ? "#26a69a" : "#ef5350"}" stop-opacity=".25"/><stop offset="1" stop-color="${up ? "#26a69a" : "#ef5350"}" stop-opacity="0"/></linearGradient></defs>`;
      for (const t of ticks) {
        s += `<line class="grid-line" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/>`;
        s += `<text class="axis" x="${L - 8}" y="${y(t) + 3}" text-anchor="end">${esc(opts.axis ? opts.axis(t) : t)}</text>`;
      }
      if (opts.base !== undefined && opts.base >= lo && opts.base <= hi) {
        s += `<line class="zero-line" x1="${L}" x2="${W - R}" y1="${y(opts.base)}" y2="${y(opts.base)}"/>`;
      }
      s += `<path d="${line}L${x(points.length - 1)},${H - B}L${L},${H - B}Z" fill="url(#eqg)"/>`;
      s += `<path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>`;
      s += `<line id="xh" stroke="rgba(255,255,255,.25)" y1="${T}" y2="${H - B}" visibility="hidden"/>`;
      s += `<circle id="xd" r="4.5" fill="${color}" stroke="var(--panel)" stroke-width="2" visibility="hidden"/>`;
      s += `<rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}"/>`;
      el.innerHTML = s + "</svg>";
      const svg = el.firstElementChild, xh = svg.querySelector("#xh"), xd = svg.querySelector("#xd");
      svg.querySelector(".hit").addEventListener("mousemove", (e) => {
        const r = svg.getBoundingClientRect();
        const k = Math.round(((e.clientX - r.left - L) / (W - L - R)) * (points.length - 1));
        const p = points[Math.max(0, Math.min(points.length - 1, k))], px = x(points.indexOf(p));
        xh.setAttribute("x1", px); xh.setAttribute("x2", px); xh.setAttribute("visibility", "visible");
        xd.setAttribute("cx", px); xd.setAttribute("cy", y(p.v)); xd.setAttribute("visibility", "visible");
        showTip(p.tip, r.left + px, r.top + y(p.v));
      });
      svg.querySelector(".hit").addEventListener("mouseleave", () => {
        xh.setAttribute("visibility", "hidden"); xd.setAttribute("visibility", "hidden"); hideTip();
      });
    };
    charts.push(draw);
    draw();
  }

  function showTip(html, x, y) {
    const tip = $("tip");
    tip.innerHTML = html;
    tip.hidden = false;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  function hideTip() { $("tip").hidden = true; }
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (!t) return;
    const r = t.getBoundingClientRect();
    showTip(t.dataset.tip, r.left + r.width / 2, r.top + 4);
  });
  document.addEventListener("mouseout", (e) => { if (e.target.closest && e.target.closest("[data-tip]")) hideTip(); });
  let resizeT = null;
  addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => charts.forEach((d) => d()), 120); });

  // ---- shared bits ---------------------------------------------------------

  function tile(icon, label, value, foot = "", extra = "") {
    return `<div class="panel tile"><div class="label">${ICON[icon]}${label}</div><div class="value">${value}</div>${extra}${foot ? `<div class="foot">${foot}</div>` : ""}</div>`;
  }

  function sessionRow(b) {
    const eq = equity(b), d = eq - b.balance;
    const span = b.end_ts - b.start_ts, done = Math.min(1, Math.max(0, (b.current_ts - b.start_ts) / span));
    return `<div class="srow">
      <a class="play" href="chart.html?bt=${b.id}" title="Continue replay">${ICON.play}</a>
      <div>
        <div class="name">${esc(b.name)}</div>
        <div class="meta">
          <span>${ICON.cal}${shortDate(nyDate(b.start_ts))} – ${shortDate(nyDate(b.end_ts))}</span>
          <span>${ICON.wallet}${money(b.balance, 0)}</span>
          <span>${b.trades.length} trade${b.trades.length === 1 ? "" : "s"}</span>
        </div>
        <div class="chips">${b.symbols.map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</div>
      </div>
      <div class="prog" title="Replayed up to ${esc(nyDate(b.current_ts))}">
        <div class="bar"><span style="width:${(done * 100).toFixed(1)}%"></span></div>
        <div class="lbl"><span>${(done * 100).toFixed(0)}%</span><span>Remaining days: ${remainingDays(b)}</span></div>
      </div>
      <div style="display:flex;align-items:center;gap:14px">
        <div class="eq"><div class="v">${money(eq)}</div><div class="d ${cls(d)}">${signedMoney(d)}</div></div>
        <div class="acts">
          <button class="icon-btn" data-act="edit" data-id="${b.id}" title="Edit">${ICON.edit}</button>
          <button class="icon-btn" data-act="dup" data-id="${b.id}" title="Duplicate (fresh start)">${ICON.copy}</button>
          <a class="icon-btn" href="#analytics/${b.id}" title="Summary">${ICON.stats}</a>
          <button class="icon-btn danger" data-act="del" data-id="${b.id}" title="Delete">${ICON.trash}</button>
        </div>
      </div>
    </div>`;
  }

  function noSessions() {
    return `<div class="empty">
      <h3>No backtest sessions yet</h3>
      <div>Create a session with a date range and a starting balance. Your trades and progress are saved as you go.</div>
      <button class="btn btn-gold" data-act="new">+ New session</button>
    </div>`;
  }

  // ---- views ---------------------------------------------------------------

  const views = {
    dashboard: { title: "Dashboard", render: renderDashboard },
    sessions: { title: "Sessions", render: renderSessions },
    trades: { title: "Trades", render: renderTrades },
    analytics: { title: "Analytics", render: renderAnalytics },
    data: { title: "Data", render: renderData },
  };

  function renderDashboard(v) {
    const trades = allTrades(), st = stats(trades);
    const spent = backtests.reduce((a, b) => a + b.time_spent_ms, 0);
    const replayed = backtests.reduce((a, b) => a + b.replayed_ms, 0);
    const longPct = st.n ? (st.longs / st.n) * 100 : 50;

    v.innerHTML = `
      <div class="grid tiles">
        ${tile("clock", "Time invested", duration(spent, ["d", "h", "m"]))}
        ${tile("hist", "Historical time replayed", duration(replayed, ["y", "d", "h", "m"]))}
        ${tile("trades", "Trades taken", st.n, st.n ? `<span class="pos">${longPct.toFixed(0)}% long</span> · <span class="neg">${(100 - longPct).toFixed(0)}% short</span>` : "",
          `<div class="split"><span style="flex:${st.longs || 1};background:var(--up)"></span><span style="flex:${st.shorts || 1};background:var(--down)"></span></div>`)}
        ${tile("target", "Win rate", pct(st.winRate))}
        ${tile("dollar", "Net P&amp;L", `<span class="${cls(st.net)}">${signedMoney(st.net)}</span>`)}
        ${tile("scale", "Profit factor", isFinite(st.pf) ? st.pf.toFixed(2) : st.pf === Infinity ? "∞" : "–")}
      </div>

      <div class="grid row2" style="margin-top:16px">
        <div class="panel"><h3>Time invested <span class="muted">last 12 months</span></h3><div class="chart" id="cTime"></div></div>
        <div class="panel" id="liveCard">
          <div class="live-head">
            <div><div class="live-sym" id="liveSym">Next open</div><div class="live-date" id="liveDate">Loading…</div></div>
            <div class="live-badge" id="liveBadge"><span class="dot"></span> REPLAY 1x</div>
          </div>
          <div class="live-price-row">
            <div class="live-price" id="livePrice">–</div><div class="live-chg" id="liveChg"></div><div class="live-clock" id="liveClock"></div>
          </div>
          <div class="live-chart" id="liveChart"></div>
        </div>
      </div>

      <div class="grid row3" style="margin-top:16px">
        <div class="panel"><h3>Win rate <span class="muted">by month</span></h3><div class="chart" id="cWin"></div></div>
        <div class="panel"><h3>Net P&amp;L <span class="muted">by month</span></h3><div class="chart" id="cPnl"></div></div>
        <div class="panel"><h3>Trades by symbol</h3><div class="chart" id="cSym"></div></div>
      </div>

      <div class="section-title"><h2>Recent sessions</h2><span class="spacer"></span><a class="btn btn-ghost btn-sm" href="#sessions">View all</a></div>
      <div class="sessions">${backtests.length ? backtests.slice(0, 5).map(sessionRow).join("") : noSessions()}</div>`;

    // time invested per month (last 12)
    const byMonth = new Map();
    const now = new Date();
    for (let k = 11; k >= 0; k--) {
      const d = new Date(now.getFullYear(), now.getMonth() - k, 1);
      byMonth.set(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, 0);
    }
    for (const b of backtests) for (const [day, ms] of Object.entries(b.time_by_day || {})) {
      const key = day.slice(0, 7);
      if (byMonth.has(key)) byMonth.set(key, byMonth.get(key) + ms);
    }
    barChart($("cTime"), [...byMonth].map(([k, ms]) => ({
      label: monthLabel(k), value: ms / 3600000, tip: `${monthLabel(k)}: <b>${(ms / 3600000).toFixed(1)} h</b>`,
    })), { axis: (t) => `${+t.toFixed(2)}h`, empty: "Replay a session to start tracking time" });

    // by market month of the trade
    const tm = new Map();
    for (const t of trades) {
      const key = nyDate(t.exit_ts).slice(0, 7);
      const e = tm.get(key) || { n: 0, w: 0, pnl: 0 };
      e.n++; e.w += t.pnl > 0; e.pnl += t.pnl;
      tm.set(key, e);
    }
    const months = [...tm].sort(([a], [b]) => a.localeCompare(b)).slice(-12);
    barChart($("cWin"), months.map(([k, e]) => ({
      label: monthLabel(k), value: (e.w / e.n) * 100, tip: `${monthLabel(k)}: <b>${((e.w / e.n) * 100).toFixed(1)}%</b> of ${e.n}`,
    })), { color: "var(--accent)", axis: (t) => `${t}%`, empty: "No trades yet" });
    barChart($("cPnl"), months.map(([k, e]) => ({
      label: monthLabel(k), value: e.pnl, tip: `${monthLabel(k)}: <b>${signedMoney(e.pnl)}</b>`,
    })), { polarity: true, axis: (t) => (Math.abs(t) >= 1000 ? `${t / 1000}k` : t), empty: "No trades yet" });

    const bySym = new Map();
    for (const t of trades) bySym.set(t.symbol, (bySym.get(t.symbol) || 0) + 1);
    hbarChart($("cSym"), [...bySym].sort((a, b) => b[1] - a[1]).map(([s, n]) => ({ label: s, value: n, tip: `${esc(s)}: <b>${n}</b> trades` })),
      { color: "var(--accent)", empty: "No trades yet" });

    startLive();
  }

  let page = 0;
  function renderSessions(v) {
    v.innerHTML = `
      <div class="toolbar-row">
        <label class="search">${ICON.search}<input id="q" placeholder="Search sessions"></label>
        <span style="flex:1"></span>
        <select class="input" id="sort">
          <option value="updated">Last played</option>
          <option value="created">Newest first</option>
          <option value="pnl">Best P&amp;L</option>
          <option value="name">Name</option>
        </select>
      </div>
      <div class="sessions" id="list"></div>
      <div class="pager" id="pager"></div>`;
    const PER = 8;
    const draw = () => {
      const q = $("q").value.trim().toLowerCase(), sort = $("sort").value;
      let list = backtests.filter((b) => !q || b.name.toLowerCase().includes(q) || b.symbols.join(" ").toLowerCase().includes(q));
      const key = { updated: (b) => -b.updated, created: (b) => -b.created, pnl: (b) => -equity(b) + b.balance, name: (b) => b.name.toLowerCase() }[sort];
      list = list.slice().sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0));
      const pages = Math.max(1, Math.ceil(list.length / PER));
      page = Math.min(page, pages - 1);
      $("list").innerHTML = backtests.length
        ? list.slice(page * PER, page * PER + PER).map(sessionRow).join("") || `<div class="empty">No sessions match "${esc(q)}".</div>`
        : noSessions();
      $("pager").innerHTML = pages > 1
        ? `<button class="icon-btn" data-pg="-1" ${page ? "" : "disabled"}>‹</button> Page ${page + 1} of ${pages} <button class="icon-btn" data-pg="1" ${page < pages - 1 ? "" : "disabled"}>›</button>`
        : "";
    };
    $("q").addEventListener("input", () => { page = 0; draw(); });
    $("sort").addEventListener("change", draw);
    $("pager").addEventListener("click", (e) => { const d = e.target.dataset.pg; if (d) { page += +d; draw(); } });
    draw();
  }

  function sessionFilter(selected) {
    return `<select class="input" id="sf">
      <option value="">All sessions</option>
      ${backtests.map((b) => `<option value="${b.id}" ${b.id === selected ? "selected" : ""}>${esc(b.name)}</option>`).join("")}
    </select>`;
  }

  function renderTrades(v, arg) {
    v.innerHTML = `
      <div class="toolbar-row">${sessionFilter(arg)}<span style="flex:1"></span>
        <button class="btn btn-ghost btn-sm" id="csv">Export CSV</button></div>
      <div id="tbl"></div>`;
    let rows = [];
    const draw = () => {
      const sid = $("sf").value;
      rows = allTrades(sid ? backtests.filter((b) => b.id === sid) : backtests).reverse();
      if (!rows.length) {
        $("tbl").innerHTML = `<div class="empty"><h3>No trades yet</h3><div>Open a session, press <kbd>B</kbd> or <kbd>S</kbd> to trade. Every closed trade lands here.</div></div>`;
        return;
      }
      $("tbl").innerHTML = `<div class="table-wrap"><table class="t">
        <thead><tr><th>Session</th><th>Symbol</th><th>Side</th><th class="num">Qty</th><th>Entry (NY)</th><th class="num">Entry</th>
          <th>Exit (NY)</th><th class="num">Exit</th><th class="num">Points</th><th class="num">P&amp;L</th><th class="num">Held</th></tr></thead>
        <tbody>${rows.map((t) => {
          const pts = (t.exit_px - t.entry_px) * t.side, held = (t.exit_ts - t.entry_ts) / 1000;
          return `<tr><td>${esc(t.session)}</td><td><b>${esc(t.symbol)}</b></td>
            <td><span class="chip ${t.side > 0 ? "long" : "short"}">${t.side > 0 ? "LONG" : "SHORT"}</span></td>
            <td class="num">${t.qty}</td><td class="mono">${nyDate(t.entry_ts)} ${nyClock(t.entry_ts).slice(0, 8)}</td><td class="num">${t.entry_px.toFixed(2)}</td>
            <td class="mono">${nyClock(t.exit_ts).slice(0, 8)}</td><td class="num">${t.exit_px.toFixed(2)}</td>
            <td class="num ${cls(pts)}">${pts > 0 ? "+" : ""}${pts.toFixed(2)}</td>
            <td class="num ${cls(t.pnl)}">${signedMoney(t.pnl)}</td>
            <td class="num">${held < 60 ? held.toFixed(0) + "s" : held < 3600 ? (held / 60).toFixed(1) + "m" : (held / 3600).toFixed(1) + "h"}</td></tr>`;
        }).join("")}</tbody></table></div>`;
    };
    $("sf").addEventListener("change", draw);
    $("csv").addEventListener("click", () => {
      const head = "session,symbol,side,qty,entry_time_ny,entry_px,exit_time_ny,exit_px,pnl,fees\n";
      const body = rows.map((t) => [t.session, t.symbol, t.side > 0 ? "long" : "short", t.qty,
        `${nyDate(t.entry_ts)} ${nyClock(t.entry_ts)}`, t.entry_px, `${nyDate(t.exit_ts)} ${nyClock(t.exit_ts)}`, t.exit_px, t.pnl, t.fees || 0]
        .map((x) => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([head + body], { type: "text/csv" }));
      a.download = "tick-replay-trades.csv";
      a.click();
    });
    draw();
  }

  function renderAnalytics(v, arg) {
    v.innerHTML = `<div class="toolbar-row">${sessionFilter(arg)}</div><div id="an"></div>`;
    const draw = () => {
      charts.length = 0;
      const sid = $("sf").value;
      const list = sid ? backtests.filter((b) => b.id === sid) : backtests;
      const trades = allTrades(list), st = stats(trades);
      const base = sid ? list[0].balance : 0;
      $("an").innerHTML = `
        <div class="grid tiles">
          ${tile("dollar", "Net P&amp;L", `<span class="${cls(st.net)}">${signedMoney(st.net)}</span>`, st.fees ? `incl. ${money(st.fees)} commission` : "")}
          ${tile("target", "Win rate", pct(st.winRate), `${st.n} trades`)}
          ${tile("scale", "Profit factor", isFinite(st.pf) ? st.pf.toFixed(2) : st.pf === Infinity ? "∞" : "–")}
          ${tile("trades", "Expectancy", `<span class="${cls(st.expectancy)}">${signedMoney(st.expectancy)}</span>`, "per trade")}
          ${tile("hist", "Max drawdown", `<span class="neg">${money(st.maxDD)}</span>`)}
        </div>
        <div class="panel" style="margin-top:16px"><h3>${sid ? "Equity" : "Cumulative P&amp;L"} <span class="muted">trade by trade</span></h3><div class="chart" id="cEq" style="height:240px"></div></div>
        <div class="grid row3" style="margin-top:16px">
          <div class="panel"><h3>P&amp;L by weekday</h3><div class="chart" id="cWd"></div></div>
          <div class="panel"><h3>P&amp;L by entry hour <span class="muted">New York</span></h3><div class="chart" id="cHr"></div></div>
          <div class="panel"><h3>Details</h3><dl class="kv">
            <dt>Average win</dt><dd class="pos">${signedMoney(st.avgWin)}</dd>
            <dt>Average loss</dt><dd class="neg">${signedMoney(st.avgLoss)}</dd>
            <dt>Best trade</dt><dd class="${cls(st.best)}">${signedMoney(st.best)}</dd>
            <dt>Worst trade</dt><dd class="${cls(st.worst)}">${signedMoney(st.worst)}</dd>
            <dt>Long trades · win rate</dt><dd>${st.longs} · ${pct(st.longWR)}</dd>
            <dt>Short trades · win rate</dt><dd>${st.shorts} · ${pct(st.shortWR)}</dd>
            <dt>Commission paid</dt><dd>${money(st.fees)}</dd>
          </dl></div>
        </div>`;
      let eq = base;
      const pts = [{ v: base, tip: `Start: <b>${money(base)}</b>` }].concat(trades.map((t, k) => {
        eq += t.pnl;
        return { v: eq, tip: `#${k + 1} ${esc(t.symbol)} ${signedMoney(t.pnl)}<br>${sid ? "Equity" : "Total"}: <b>${money(eq)}</b>` };
      }));
      lineChart($("cEq"), pts, { base, axis: (t) => (Math.abs(t) >= 10000 ? `${(t / 1000).toFixed(0)}k` : t), empty: "Take some trades to see the curve" });

      // Globex opens Sunday evening, so Sunday shows up when there are trades on it
      const wd = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"].map((d) => ({ d, pnl: 0, n: 0 }));
      const hr = new Map();
      for (const t of trades) {
        const p = nyParts(t.entry_ts), w = wd.find((x) => x.d === p.weekday);
        if (w) { w.pnl += t.pnl; w.n++; }
        const h = +p.hour, e = hr.get(h) || { pnl: 0, n: 0 };
        e.pnl += t.pnl; e.n++; hr.set(h, e);
      }
      if (!wd[0].n) wd.shift();
      barChart($("cWd"), wd.map((w) => ({ label: w.d, value: w.pnl, tip: `${w.d}: <b>${signedMoney(w.pnl)}</b> · ${w.n} trades` })),
        { polarity: true, axis: (t) => (Math.abs(t) >= 1000 ? `${t / 1000}k` : t), empty: "No trades yet" });
      const hours = [...hr.keys()].sort((a, b) => a - b);
      const hrs = hours.length ? Array.from({ length: hours[hours.length - 1] - hours[0] + 1 }, (_, k) => hours[0] + k) : [];
      barChart($("cHr"), hrs.map((h) => { const e = hr.get(h) || { pnl: 0, n: 0 }; return { label: `${h}`, value: e.pnl, tip: `${h}:00–${h}:59: <b>${signedMoney(e.pnl)}</b> · ${e.n} trades` }; }),
        { polarity: true, axis: (t) => (Math.abs(t) >= 1000 ? `${t / 1000}k` : t), empty: "No trades yet" });
    };
    $("sf").addEventListener("change", () => { history.replaceState(null, "", `#analytics${$("sf").value ? "/" + $("sf").value : ""}`); draw(); });
    draw();
  }

  function renderData(v) {
    v.innerHTML = `
      <div class="grid row2">
        <div class="panel"><h3>Your tick data</h3><div class="lib" id="lib"></div></div>
        <div class="panel">
          <h3>Import ticks</h3>
          <form id="importForm">
            <label class="drop" id="drop">
              <input id="impFiles" type="file" multiple accept=".csv,.txt,.zst" hidden>
              <span class="drop-icon">⇪</span>
              <span class="drop-title" id="dropTitle">Drop tick files here</span>
              <span class="muted small" id="dropSub">or click to choose · .csv · .csv.zst · .txt</span>
            </label>
            <div class="form-row">
              <label class="field">Symbol
                <input class="input" id="impSym" list="symList" value="NQ" required maxlength="32" pattern="[A-Za-z0-9][A-Za-z0-9_\\-]*">
                <datalist id="symList"><option>NQ</option><option>ES</option><option>MNQ</option><option>MES</option></datalist>
              </label>
              <label class="field">Time zone in file
                <select class="input" id="impTz">
                  <option value="Europe/Copenhagen">Denmark (my PC)</option>
                  <option value="America/New_York">New York</option>
                  <option value="America/Chicago">Chicago (CME)</option>
                  <option value="UTC">UTC</option>
                </select>
              </label>
              <button type="submit" class="btn btn-gold" id="impBtn" disabled>Import</button>
            </div>
            <div class="progress" id="impBar" hidden><span></span></div>
            <p class="hint" id="impMsg">Databento CSV (TBBO or trades) carries its own time zone. With several contracts in one file, the most-traded one is kept for each day.</p>
          </form>
        </div>
      </div>`;
    drawLibrary();
    setupImport();
  }

  function drawLibrary() {
    $("lib").innerHTML = symbols.length ? symbols.map((s) => {
      const demo = /-DEMO$/i.test(s.symbol);
      return `<div class="lib-item">
        <div class="lib-sym">${esc(s.symbol)}</div>
        <div class="lib-meta">${nyDate(s.first_ts)} → ${nyDate(s.last_ts)} · ${s.days.length} day${s.days.length === 1 ? "" : "s"}
          <span class="badge ${s.quotes ? "q" : "t"}">${s.quotes ? "BID/ASK" : "TRADES"}</span>${demo ? `<span class="badge demo">DEMO</span>` : ""}</div>
        <button class="icon-btn danger" data-del-sym="${esc(s.symbol)}" title="Delete">${ICON.trash}</button>
      </div>`;
    }).join("") : `<p class="muted">No data yet. Demo data appears here a few seconds after the first start.</p>`;
  }

  function setupImport() {
    const drop = $("drop"), files = $("impFiles");
    const picked = () => {
      const f = files.files;
      drop.classList.toggle("has", f.length > 0);
      $("impBtn").disabled = !f.length;
      if (!f.length) { $("dropTitle").textContent = "Drop tick files here"; $("dropSub").textContent = "or click to choose · .csv · .csv.zst · .txt"; return; }
      const mb = [...f].reduce((a, x) => a + x.size, 0) / 1048576;
      $("dropTitle").textContent = `${f.length} file${f.length === 1 ? "" : "s"} ready`;
      $("dropSub").textContent = `${mb.toFixed(1)} MB · click to change`;
    };
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
    drop.addEventListener("drop", (e) => { e.preventDefault(); if (e.dataTransfer.files.length) { files.files = e.dataTransfer.files; picked(); } });
    files.addEventListener("change", picked);

    $("importForm").addEventListener("submit", (e) => {
      e.preventDefault();
      if (!files.files.length) return;
      const fd = new FormData();
      for (const f of files.files) fd.append("files", f);
      fd.append("symbol", $("impSym").value.trim().toUpperCase());
      fd.append("tz", $("impTz").value);
      const msg = $("impMsg"), btn = $("impBtn"), bar = $("impBar"), fill = bar.firstElementChild;
      btn.disabled = true; bar.hidden = false; bar.classList.remove("busy"); fill.style.width = "0";
      msg.className = "hint"; msg.textContent = "Uploading…";
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/import");
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        const p = Math.round((ev.loaded / ev.total) * 100);
        fill.style.width = p + "%";
        if (p >= 100) { bar.classList.add("busy"); msg.textContent = "Reading ticks… large files can take a minute."; }
        else msg.textContent = `Uploading… ${p}%`;
      };
      const done = () => { btn.disabled = false; bar.hidden = true; };
      xhr.onload = async () => {
        done();
        let r = {};
        try { r = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
        if (xhr.status !== 200) { msg.className = "hint err"; msg.textContent = "Import failed: " + (r.detail || xhr.statusText); return; }
        const fmt = (ms) => `${nyDate(ms)} ${nyClock(ms).slice(0, 5)}`;
        msg.className = "hint ok";
        msg.textContent = `✓ ${r.ticks.toLocaleString("en-US")} tick${r.ticks === 1 ? "" : "s"} into ${r.symbol} (${r.days} day${r.days === 1 ? "" : "s"}${r.has_quotes ? ", with bid/ask" : ""}). ` +
          `First ${fmt(r.first_ts)}, last ${fmt(r.last_ts)} New York. If those times are hours off, import again with another time zone.`;
        files.value = ""; picked();
        daysCache.delete(r.symbol);
        symbols = await api("/api/symbols");
        drawLibrary();
        updateQuick();
      };
      xhr.onerror = () => { done(); msg.className = "hint err"; msg.textContent = "Import failed: the program is not responding."; };
      xhr.send(fd);
    });
  }

  // ---- live preview of the latest open --------------------------------------

  const live = { gen: 0, chart: null, series: null };
  function previewSymbol() {
    const real = symbols.filter((s) => !/-DEMO$/i.test(s.symbol));
    return (real.find((s) => s.symbol === "NQ") || real[0] || symbols.find((s) => s.symbol === "NQ-DEMO") || symbols[0] || {}).symbol;
  }
  async function days(sym) {
    if (!daysCache.has(sym)) daysCache.set(sym, await api(`/api/days?symbol=${encodeURIComponent(sym)}`));
    return daysCache.get(sym);
  }

  async function startLive() {
    const gen = ++live.gen;
    const el = $("liveChart");
    live.chart = null;
    const sym = previewSymbol();
    if (!sym) { $("liveDate").textContent = "Import data to see a preview"; return; }
    const session = (await days(sym))[0];
    if (gen !== live.gen || !session) { if (session === undefined && $("liveDate")) $("liveDate").textContent = "No regular sessions yet"; return; }
    const chart = LightweightCharts.createChart(el, {
      autoSize: true, localization: { locale: "en-US" },
      layout: { background: { color: "transparent" }, textColor: "#8a91a3", fontSize: 11, attributionLogo: false },
      grid: { vertLines: { visible: false }, horzLines: { color: "rgba(255,255,255,.04)" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: true, rightOffset: 4 },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      handleScroll: false, handleScale: false,
    });
    const series = chart.addCandlestickSeries({ upColor: "#26a69a", downColor: "#ef5350", borderVisible: false, wickUpColor: "#26a69a", wickDownColor: "#ef5350" });
    const TF = 5, start = session.open_ts - 20000, end = start + 150000, q = encodeURIComponent(sym);
    const [hist, tk] = await Promise.all([
      api(`/api/candles?symbol=${q}&tf=${TF}&end=${start}&count=70`),
      api(`/api/ticks?symbol=${q}&after=${start}&until=${end}&limit=200000`),
    ]);
    if (gen !== live.gen) { chart.remove(); return; }
    const off = nyOffsetSec(start);
    series.setData(hist.map((c) => ({ time: c.time + off, open: c.open, high: c.high, low: c.low, close: c.close })));
    $("liveSym").textContent = sym;
    $("liveDate").textContent = `${shortDate(session.date)} · the open, 1x`;
    let bar = hist.length ? { ...hist[hist.length - 1] } : null, last = bar ? bar.close : session.open, shown = last;
    let t = start, i = 0, prev = performance.now();
    const frame = (now) => {
      if (gen !== live.gen || !document.body.contains(el)) { chart.remove(); return; }
      t += Math.min(now - prev, 250); prev = now;
      let moved = false;
      while (i < tk.ts.length && tk.ts[i] <= t) {
        const px = tk.price[i], b = Math.floor(tk.ts[i] / 1000 / TF) * TF;
        if (!bar || b > bar.time) { if (bar) series.update({ ...bar, time: bar.time + off }); bar = { time: b, open: px, high: px, low: px, close: px }; }
        else { bar.high = Math.max(bar.high, px); bar.low = Math.min(bar.low, px); bar.close = px; }
        last = px; i++; moved = true;
      }
      if (moved) series.update({ ...bar, time: bar.time + off });
      const pe = $("livePrice");
      if (last !== shown) { pe.className = "live-price " + (last > shown ? "up" : "down"); shown = last; }
      pe.textContent = last.toLocaleString("en-US", { minimumFractionDigits: 2 });
      const chg = last - session.pre_open;
      $("liveChg").innerHTML = `<span class="${cls(chg)}">${chg > 0 ? "+" : ""}${chg.toFixed(2)}</span>`;
      $("liveClock").textContent = nyClock(t);
      const badge = $("liveBadge"), left = session.open_ts - t;
      if (left > 0) { badge.className = "live-badge"; badge.innerHTML = `<span class="dot"></span> OPENS IN 0:${String(Math.ceil(left / 1000)).padStart(2, "0")}`; }
      else if (!badge.classList.contains("open")) { badge.className = "live-badge open"; badge.innerHTML = `<span class="dot"></span> MARKET OPEN`; }
      if (t >= end) { setTimeout(() => { if (gen === live.gen && document.body.contains(el)) { chart.remove(); startLive(); } }, 1500); return; }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }

  async function updateQuick() {
    const sym = previewSymbol();
    if (!sym) return;
    try {
      const s = (await days(sym))[0];
      if (!s) return;
      $("quickBtn").href = `chart.html?${new URLSearchParams({ symbol: sym, date: s.date, open: 1, tf: 60 })}`;
      $("quickSub").textContent = `${sym} · ${shortDate(s.date)} open, live at 1x.`;
    } catch { /* keep default */ }
  }

  // ---- new / edit session dialog --------------------------------------------

  let editing = null;
  function openDialog(b = null) {
    editing = b;
    const dlg = $("dlg");
    $("dlgErr").hidden = true;
    $("dlgTitle").textContent = b ? "Edit session" : "New backtest session";
    $("dlgOk").textContent = b ? "Save" : "Create session";
    $("fSymsField").hidden = !!b;
    $("fStart").closest("label").hidden = !!b;
    $("fStartTime").closest("label").hidden = !!b;
    if (!symbols.length) { location.hash = "#data"; return; }
    const lo = nyDate(Math.min(...symbols.map((s) => s.first_ts))), hi = nyDate(Math.max(...symbols.map((s) => s.last_ts)));
    for (const id of ["fStart", "fEnd"]) { $(id).min = lo; $(id).max = hi; }
    if (b) {
      $("fName").value = b.name; $("fEnd").value = nyDate(b.end_ts); $("fBal").value = b.balance; $("fFee").value = b.fee_per_side || 0;
      $("fStart").required = false;
    } else {
      const real = symbols.filter((s) => !/-DEMO$/i.test(s.symbol));
      const pre = new Set((real.length ? real : symbols).filter((s) => /^(NQ|ES)/.test(s.symbol)).map((s) => s.symbol));
      $("fSyms").innerHTML = symbols.map((s) => `<label><input type="checkbox" value="${esc(s.symbol)}" ${pre.has(s.symbol) ? "checked" : ""}> ${esc(s.symbol)}</label>`).join("");
      let first = lo;
      while ([0, 6].includes(new Date(first + "T12:00:00Z").getUTCDay()) && first < hi) {
        first = new Date(Date.parse(first + "T12:00:00Z") + 86400000).toISOString().slice(0, 10);
      }
      $("fName").value = ""; $("fStart").value = first; $("fEnd").value = hi; $("fBal").value = 50000; $("fFee").value = 0;
      $("fStart").required = true;
    }
    dlg.showModal();
  }

  $("dlgForm").addEventListener("submit", async (e) => {
    if (e.submitter && e.submitter.value === "cancel") return;
    e.preventDefault();
    const err = $("dlgErr");
    err.hidden = true;
    try {
      const end_ts = parseNY(`${$("fEnd").value}T17:00`);
      if (editing) {
        await post(`/api/backtests/${editing.id}`, {
          name: $("fName").value, end_ts: Math.max(end_ts, editing.start_ts + 60000),
          balance: +$("fBal").value, fee_per_side: +$("fFee").value,
        }, "PATCH");
      } else {
        const rank = (s) => (/^NQ/.test(s) ? 0 : /^ES/.test(s) ? 1 : 2);
        const syms = [...$("fSyms").querySelectorAll("input:checked")].map((x) => x.value).sort((a, b) => rank(a) - rank(b));
        if (!syms.length) throw new Error("Pick at least one symbol");
        const start_ts = parseNY(`${$("fStart").value}T${$("fStartTime").value}`);
        if (end_ts <= start_ts) throw new Error("The end date must be after the start date");
        const b = await post("/api/backtests", {
          name: $("fName").value, symbols: syms, start_ts, end_ts, balance: +$("fBal").value, fee_per_side: +$("fFee").value,
        });
        $("dlg").close();
        location.href = `chart.html?bt=${b.id}`;
        return;
      }
      $("dlg").close();
      backtests = await api("/api/backtests");
      route();
    } catch (ex) {
      err.textContent = ex.message;
      err.hidden = false;
    }
  });

  // ---- actions & routing ----------------------------------------------------

  document.addEventListener("click", async (e) => {
    const el = e.target.closest("[data-act], [data-del-sym]");
    if (!el) return;
    if (el.dataset.delSym) {
      const s = el.dataset.delSym;
      if (!confirm(`Delete all ${s} tick data from this computer?`)) return;
      await api(`/api/symbols/${encodeURIComponent(s)}`, { method: "DELETE" }).catch((ex) => alert(ex.message));
      daysCache.delete(s);
      symbols = await api("/api/symbols");
      drawLibrary();
      return;
    }
    const b = backtests.find((x) => x.id === el.dataset.id);
    const act = el.dataset.act;
    if (act === "new") return openDialog();
    if (act === "edit" && b) return openDialog(b);
    if (act === "dup" && b) { await post(`/api/backtests/${b.id}/duplicate`, {}); }
    if (act === "del" && b) {
      if (!confirm(`Delete the session "${b.name}" and its ${b.trades.length} trades?`)) return;
      await api(`/api/backtests/${b.id}`, { method: "DELETE" });
    }
    backtests = await api("/api/backtests");
    route();
  });
  $("newBtn").addEventListener("click", () => openDialog());

  function route() {
    const [name, arg] = location.hash.replace(/^#/, "").split("/");
    const key = views[name] ? name : "dashboard";
    const view = views[key];
    document.querySelectorAll(".nav-item").forEach((a) => a.classList.toggle("on", a.dataset.view === key));
    $("title").textContent = view.title;
    const n = backtests.length;
    $("subtitle").textContent = key === "data"
      ? `${symbols.length} symbol${symbols.length === 1 ? "" : "s"} on this PC`
      : `${n} session${n === 1 ? "" : "s"} · ${allTrades().length} trades`;
    charts.length = 0;
    live.gen++;
    hideTip();
    view.render($("view"), arg);
    scrollTo(0, 0);
  }

  addEventListener("hashchange", route);
  addEventListener("pageshow", async (e) => {
    // coming back from the chart: refresh saved progress and trades
    if (e.persisted) { await loadAll(); route(); }
  });

  // tells the desktop program a window is still open
  const ping = () => fetch("/api/ping").catch(() => {});
  ping();
  setInterval(ping, 20000);

  (async function boot() {
    try {
      await loadAll();
    } catch (ex) {
      $("view").innerHTML = `<div class="empty"><h3>Could not reach the program</h3>${esc(ex.message)}</div>`;
      return;
    }
    if (!symbols.length) {
      // first start: demo data is generated in the background
      $("view").innerHTML = `<div class="empty"><h3>Preparing demo data…</h3>This takes a few seconds on first start.</div>`;
      for (let k = 0; k < 30 && !symbols.length; k++) {
        await new Promise((r) => setTimeout(r, 1500));
        symbols = await api("/api/symbols");
      }
    }
    updateQuick();
    route();
    fetch("version.json").then((r) => r.json()).then((v) => { $("ver").textContent = v.version === "dev" ? "dev build" : "v" + v.version; }).catch(() => {});
    // Trading opens the most recently played session, or a free replay
    if (backtests.length) $("navTrading").href = `chart.html?bt=${backtests[0].id}`;
  })();
})();
