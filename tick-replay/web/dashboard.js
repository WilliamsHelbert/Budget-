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

  /** Evaluation status of a session with rules: where it stands against target and drawdown. */
  function ruleInfo(b) {
    const r = b.rules;
    if (!r) return null;
    const st = b.rule_state || {}, eq = equity(b), closed = eq - b.balance;
    const peak = Math.max(st.peak ?? b.balance, eq);
    const floor = r.max_dd ? Math.min(peak - r.max_dd, b.balance) : null;
    const status = st.status || (r.target && closed >= r.target ? "passed" : "active");
    return { r, status, reason: st.reason, toGo: r.target ? r.target - closed : null, ddLeft: floor !== null ? eq - floor : null };
  }
  function ruleBadge(b) {
    const i = ruleInfo(b);
    if (!i) return "";
    const txt = { passed: "Passed", failed: "Failed", active: "Evaluation" }[i.status];
    return `<span class="rbadge ${i.status}" title="${esc(i.status === "failed" ? "Failed: " + (i.reason || "rule broken") : "Evaluation rules on")}">${txt}</span>`;
  }
  function ruleLine(b) {
    const i = ruleInfo(b);
    if (!i || i.status === "failed") return i ? `<div class="rule-line neg">Failed – ${esc(i.reason || "a rule was broken")}. Duplicate the session to try again.</div>` : "";
    const parts = [];
    if (i.toGo !== null) parts.push(i.toGo > 0 ? `<b>${money(i.toGo, 0)}</b> to target` : "<b class=\"pos\">Target reached</b>");
    if (i.ddLeft !== null) parts.push(`<b class="${i.ddLeft < i.r.max_dd * 0.25 ? "neg" : ""}">${money(i.ddLeft, 0)}</b> drawdown room`);
    if (i.r.daily_loss) parts.push(`daily limit ${money(i.r.daily_loss, 0)}`);
    return `<div class="rule-line">${parts.join(" · ")}</div>`;
  }

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
  function fmtMin(m) {
    if (!m) return "0";
    return m >= 60 ? `${+(m / 60).toFixed(1)}h` : `${+m.toFixed(m < 10 ? 1 : 0)}m`;
  }

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
        const color = opts.polarity ? (it.value >= 0 ? "var(--up)" : "var(--down)") : opts.color || "var(--accent)";
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
        <div class="name">${esc(b.name)} ${ruleBadge(b)}</div>
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
      <div class="srow-end">
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
      <button class="btn btn-primary" data-act="new">+ New session</button>
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

  function greeting() {
    const h = new Date().getHours();
    return h < 5 ? "Late session" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }

  /** The most recently played session, shown big at the top. */
  function continueCard() {
    const b = backtests[0];
    if (!b) {
      const hasReal = symbols.some((s) => !/-DEMO$/i.test(s.symbol));
      return `<div class="hero-card empty-hero">
        <div class="eyebrow">Get started</div>
        <h2>Create your first backtest session</h2>
        <p class="muted">A session has its own date range, balance and trade log. Everything is saved as you replay.</p>
        <div class="hero-actions">
          <button class="btn btn-primary btn-lg" data-act="new">+ New session</button>
          ${hasReal ? "" : '<a class="btn btn-ghost btn-lg" href="#data">Import tick data</a>'}
        </div>
      </div>`;
    }
    const eq = equity(b), d = eq - b.balance;
    const done = Math.min(1, Math.max(0, (b.current_ts - b.start_ts) / (b.end_ts - b.start_ts)));
    const played = b.updated ? new Date(b.updated) : null;
    const ago = played ? Math.round((Date.now() - played) / 60000) : null;
    const agoTxt = ago === null ? "" : ago < 1 ? "just now" : ago < 60 ? `${ago} min ago` : ago < 1440 ? `${Math.round(ago / 60)} h ago` : `${Math.round(ago / 1440)} d ago`;
    return `<div class="hero-card">
      <div class="eyebrow">Continue where you left off <span class="muted">· played ${agoTxt}</span></div>
      <div class="hero-main">
        <div class="hero-info">
          <h2>${esc(b.name)} ${ruleBadge(b)}</h2>
          <div class="hero-meta">
            <span>${ICON.cal}${shortDate(nyDate(b.start_ts))} – ${shortDate(nyDate(b.end_ts))}</span>
            <span>${ICON.clock}at ${nyDate(b.current_ts)} ${nyClock(b.current_ts).slice(0, 5)} NY</span>
            <span class="chips">${b.symbols.map((s) => `<span class="chip">${esc(s)}</span>`).join("")}</span>
          </div>
          <div class="hero-prog">
            <div class="bar"><span style="width:${(done * 100).toFixed(1)}%"></span></div>
            <div class="lbl"><span>${(done * 100).toFixed(0)}% replayed</span><span>${remainingDays(b)} trading days left</span></div>
          </div>
          ${ruleLine(b)}
        </div>
        <div class="hero-eq">
          <div class="muted small">Balance</div>
          <div class="big">${money(eq)}</div>
          <div class="${cls(d)} mono">${signedMoney(d)} · ${b.trades.length} trade${b.trades.length === 1 ? "" : "s"}</div>
        </div>
      </div>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="chart.html?bt=${b.id}">${ICON.play} Continue replay</a>
        <a class="btn btn-ghost btn-lg" href="#analytics/${b.id}">Session stats</a>
        ${backtests.length > 1 ? `<a class="btn btn-ghost btn-lg" href="#sessions">All sessions (${backtests.length})</a>` : ""}
      </div>
    </div>`;
  }

  /** Shown until the user has data, a session and a trade. */
  function checklist(st) {
    const hasReal = symbols.some((s) => !/-DEMO$/i.test(s.symbol));
    const steps = [
      [hasReal, "Import your tick data", "Databento TBBO/trades, NinjaTrader or CSV", "#data", "Import"],
      [backtests.length > 0, "Create a backtest session", "Date range, balance and commission", "new", "New session"],
      [st.n > 0, "Take your first trade", "B / S on the chart, or orders from the DOM", backtests[0] ? `chart.html?bt=${backtests[0].id}` : "new", "Open chart"],
    ];
    if (steps.every((s) => s[0])) return "";
    return `<div class="panel checklist"><h3>Getting started <span class="muted">${steps.filter((s) => s[0]).length} of 3 done</span></h3>
      ${steps.map(([ok, t, sub, href, cta]) => `<div class="step-row ${ok ? "done" : ""}">
        <span class="tick">${ok ? "✓" : ""}</span><div><div class="t">${t}</div><div class="muted small">${sub}</div></div>
        ${ok ? "" : href === "new" ? `<button class="btn btn-ghost btn-sm" data-act="new">${cta}</button>` : `<a class="btn btn-ghost btn-sm" href="${href}">${cta}</a>`}
      </div>`).join("")}</div>`;
  }

  /** Win-rate ring + the numbers that matter next to it. */
  function winPanel(st) {
    const r = 46, c = 2 * Math.PI * r, wr = isFinite(st.winRate) ? st.winRate : 0;
    return `<div class="panel win-panel"><h3>Win / loss</h3>
      <div class="win-body">
        <svg class="ring" viewBox="0 0 120 120" aria-label="Win rate ${pct(st.winRate)}">
          <circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--down)" stroke-opacity="${st.n ? 0.85 : 0.15}" stroke-width="12"/>
          <circle cx="60" cy="60" r="${r}" fill="none" stroke="var(--up)" stroke-width="12" stroke-linecap="round"
            stroke-dasharray="${(c * wr).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 60 60)" ${st.n ? "" : 'stroke-opacity="0"'}/>
          <text x="60" y="58" text-anchor="middle" class="ring-v">${st.n ? (wr * 100).toFixed(0) + "%" : "–"}</text>
          <text x="60" y="76" text-anchor="middle" class="ring-l">win rate</text>
        </svg>
        <dl class="kv">
          <dt>Avg win</dt><dd class="pos">${signedMoney(st.avgWin)}</dd>
          <dt>Avg loss</dt><dd class="neg">${signedMoney(st.avgLoss)}</dd>
          <dt>Expectancy</dt><dd class="${cls(st.expectancy)}">${signedMoney(st.expectancy)}</dd>
          <dt>Best / worst</dt><dd><span class="pos">${signedMoney(st.best)}</span> / <span class="neg">${signedMoney(st.worst)}</span></dd>
          <dt>Max drawdown</dt><dd class="neg">${money(st.maxDD)}</dd>
        </dl>
      </div></div>`;
  }

  function renderDashboard(v) {
    const trades = allTrades(), st = stats(trades);
    const spent = backtests.reduce((a, b) => a + b.time_spent_ms, 0);
    const replayed = backtests.reduce((a, b) => a + b.replayed_ms, 0);
    const longPct = st.n ? (st.longs / st.n) * 100 : 50;
    $("title").textContent = greeting();

    v.innerHTML = `
      ${continueCard()}
      ${checklist(st)}

      <div class="grid tiles">
        ${tile("dollar", "Net P&amp;L", `<span class="${cls(st.net)}">${signedMoney(st.net)}</span>`, st.fees ? `after ${money(st.fees)} commission` : "all sessions")}
        ${tile("target", "Win rate", pct(st.winRate), st.n ? `${trades.filter((t) => t.pnl > 0).length} of ${st.n} trades` : "no trades yet")}
        ${tile("scale", "Profit factor", isFinite(st.pf) ? st.pf.toFixed(2) : st.pf === Infinity ? "∞" : "–", "gross win ÷ gross loss")}
        ${tile("trades", "Trades", st.n, st.n ? `<span class="pos">${longPct.toFixed(0)}% long</span> · <span class="neg">${(100 - longPct).toFixed(0)}% short</span>` : "long vs short",
          `<div class="split"><span style="flex:${st.longs || 1};background:var(--up)"></span><span style="flex:${st.shorts || 1};background:var(--down)"></span></div>`)}
        ${tile("clock", "Time invested", duration(spent, ["d", "h", "m"]), "real time in replay")}
        ${tile("hist", "Market time replayed", duration(replayed, ["y", "d", "h", "m"]), "historical time covered")}
      </div>

      <div class="grid row2">
        <div class="panel"><h3>Cumulative P&amp;L <span class="muted">all sessions, trade by trade</span></h3><div class="chart tall" id="cEq"></div></div>
        ${winPanel(st)}
      </div>

      <div class="grid row3">
        <div class="panel"><h3>Net P&amp;L <span class="muted">by month</span></h3><div class="chart" id="cPnl"></div></div>
        <div class="panel"><h3>Time invested <span class="muted">last 12 months</span></h3><div class="chart" id="cTime"></div></div>
        <div class="panel"><h3>Trades by symbol</h3><div class="chart" id="cSym"></div></div>
      </div>

      <div class="section-title"><h2>Recent sessions</h2><span class="spacer"></span><a class="btn btn-ghost btn-sm" href="#sessions">View all</a></div>
      <div class="sessions">${backtests.length ? backtests.slice(0, 4).map(sessionRow).join("") : noSessions()}</div>`;

    let eqv = 0;
    lineChart($("cEq"), [{ v: 0, tip: "Start: <b>$0.00</b>" }].concat(trades.map((t, k) => {
      eqv += t.pnl;
      return { v: eqv, tip: `#${k + 1} ${esc(t.symbol)} ${signedMoney(t.pnl)} · ${esc(t.session)}<br>Total: <b>${signedMoney(eqv)}</b>` };
    })), { base: 0, axis: (t) => (Math.abs(t) >= 10000 ? `${(t / 1000).toFixed(0)}k` : t), empty: "Your equity curve appears after the first closed trade" });

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
      label: monthLabel(k), value: ms / 60000, tip: `${monthLabel(k)}: <b>${fmtMin(ms / 60000)}</b>`,
    })), { axis: (t) => fmtMin(t), empty: "Replay a session to start tracking time" });

    // by market month of the trade
    const tm = new Map();
    for (const t of trades) {
      const key = nyDate(t.exit_ts).slice(0, 7);
      const e = tm.get(key) || { n: 0, w: 0, pnl: 0 };
      e.n++; e.w += t.pnl > 0; e.pnl += t.pnl;
      tm.set(key, e);
    }
    const months = [...tm].sort(([a], [b]) => a.localeCompare(b)).slice(-12);
    barChart($("cPnl"), months.map(([k, e]) => ({
      label: monthLabel(k), value: e.pnl, tip: `${monthLabel(k)}: <b>${signedMoney(e.pnl)}</b> · ${((e.w / e.n) * 100).toFixed(0)}% of ${e.n} won`,
    })), { polarity: true, axis: (t) => (Math.abs(t) >= 1000 ? `${t / 1000}k` : t), empty: "No trades yet" });

    const bySym = new Map();
    for (const t of trades) bySym.set(t.symbol, (bySym.get(t.symbol) || 0) + 1);
    hbarChart($("cSym"), [...bySym].sort((a, b) => b[1] - a[1]).map(([s, n]) => ({ label: s, value: n, tip: `${esc(s)}: <b>${n}</b> trades` })),
      { color: "var(--accent)", empty: "No trades yet" });
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
          <th>Exit (NY)</th><th class="num">Exit</th><th class="num">Points</th><th class="num" title="Heat: most points against you / best: most points in profit">Heat / best</th><th class="num">P&amp;L</th><th class="num">Held</th><th>Setup</th></tr></thead>
        <tbody>${rows.map((t) => {
          const pts = (t.exit_px - t.entry_px) * t.side, held = (t.exit_ts - t.entry_ts) / 1000;
          return `<tr><td>${esc(t.session)}</td><td><b>${esc(t.symbol)}</b></td>
            <td><span class="chip ${t.side > 0 ? "long" : "short"}">${t.side > 0 ? "LONG" : "SHORT"}</span></td>
            <td class="num">${t.qty}</td><td class="mono">${nyDate(t.entry_ts)} ${nyClock(t.entry_ts).slice(0, 8)}</td><td class="num">${t.entry_px.toFixed(2)}</td>
            <td class="mono">${nyClock(t.exit_ts).slice(0, 8)}</td><td class="num">${t.exit_px.toFixed(2)}</td>
            <td class="num ${cls(pts)}">${pts > 0 ? "+" : ""}${pts.toFixed(2)}</td>
            <td class="num">${t.mae != null ? `<span class="neg">${t.mae.toFixed(2)}</span> / <span class="pos">${t.mfe.toFixed(2)}</span>` : '<span class="muted">–</span>'}</td>
            <td class="num ${cls(t.pnl)}">${signedMoney(t.pnl)}</td>
            <td class="num">${held < 60 ? held.toFixed(0) + "s" : held < 3600 ? (held / 60).toFixed(1) + "m" : (held / 3600).toFixed(1) + "h"}</td>
            <td><button class="setup-cell ${t.setup ? "" : "empty"}" data-jr="${t.sid}/${t.id}" title="${esc(t.note || "Tag the setup and add a note")}">${t.setup ? esc(t.setup) : "+ tag"}${t.note ? " ✎" : ""}</button></td></tr>`;
        }).join("")}</tbody></table></div>`;
    };
    $("sf").addEventListener("change", draw);
    $("tbl").addEventListener("click", async (e) => {
      const btn = e.target.closest("[data-jr]");
      if (!btn) return;
      const [sid, tid] = btn.dataset.jr.split("/");
      const t = backtests.find((b) => b.id === sid)?.trades.find((x) => x.id === tid);
      if (!t) return;
      const setup = prompt("Setup for this trade (e.g. Opening range, VWAP, Pullback):", t.setup || "");
      if (setup === null) return;
      const note = prompt("Note (optional):", t.note || "");
      const body = { setup: setup.trim() || "" };
      if (note !== null) body.note = note.trim();
      Object.assign(t, await post(`/api/backtests/${sid}/trades/${tid}`, body, "PATCH"));
      draw();
    });
    $("csv").addEventListener("click", () => {
      const head = "session,symbol,side,qty,entry_time_ny,entry_px,exit_time_ny,exit_px,pnl,fees,mae_pts,mfe_pts,setup,note\n";
      const body = rows.map((t) => [t.session, t.symbol, t.side > 0 ? "long" : "short", t.qty,
        `${nyDate(t.entry_ts)} ${nyClock(t.entry_ts)}`, t.entry_px, `${nyDate(t.exit_ts)} ${nyClock(t.exit_ts)}`, t.exit_px, t.pnl, t.fees || 0, t.mae ?? "", t.mfe ?? "", t.setup || "", t.note || ""]
        .map((x) => `"${String(x).replace(/"/g, '""')}"`).join(",")).join("\n");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([head + body], { type: "text/csv" }));
      a.download = "tick-replay-trades.csv";
      a.click();
    });
    draw();
  }

  // ---- edge finder: plain-language findings from the trade log --------------

  const tradeDay = (ms) => nyDate(ms + 6 * 3600000);   // CME trading day (18:00 New York rollover)
  const net = (list) => list.reduce((a, t) => a + t.pnl, 0);
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

  /** Each finding: { tone: good|bad|info, title, text }. Only says something when there's enough data. */
  function insights(trades) {
    const out = [];
    if (trades.length < 5) return out;

    // 1. overtrading: the first trades of a day vs. the rest
    const byDay = new Map();
    for (const t of [...trades].sort((a, b) => a.entry_ts - b.entry_ts)) {
      const d = tradeDay(t.entry_ts);
      byDay.set(d, [...(byDay.get(d) || []), t]);
    }
    const early = [], late = [];
    for (const list of byDay.values()) list.forEach((t, k) => (k < 3 ? early : late).push(t));
    if (late.length >= 3) {
      const a = net(early), b = net(late);
      if (b < 0 && a > b) out.push({ tone: "bad", title: "You give it back after trade 3",
        text: `Your first 3 trades of a day made ${signedMoney(a)}; trades 4 and later made ${signedMoney(b)} over ${plural(late.length, "trade")}. A 3-trade daily cap would have saved ${money(-b)}.` });
      else if (b > 0) out.push({ tone: "good", title: "Later trades hold up",
        text: `Trades 4+ of the day made ${signedMoney(b)} over ${plural(late.length, "trade")}, so more trades are not hurting you.` });
    }

    // 2. revenge trading: entries within 2 minutes of closing a loser
    const sorted = [...trades].sort((a, b) => a.entry_ts - b.entry_ts);
    const revenge = sorted.filter((t) => sorted.some((p) => p.pnl < 0 && p.exit_ts <= t.entry_ts && t.entry_ts - p.exit_ts < 120000 && p !== t));
    if (revenge.length >= 2) {
      const r = net(revenge), wr = revenge.filter((t) => t.pnl > 0).length / revenge.length;
      out.push({ tone: r < 0 ? "bad" : "info", title: "Trades right after a loss",
        text: `${plural(revenge.length, "trade")} were entered less than 2 minutes after a losing trade: ${signedMoney(r)}, ${pct(wr)} win rate${r < 0 ? ". Take a breath before the next one." : "."}` });
    }

    // 3. best and worst hour (New York), entry time
    const hours = new Map();
    for (const t of trades) { const h = +nyParts(t.entry_ts).hour; hours.set(h, [...(hours.get(h) || []), t]); }
    const hs = [...hours].filter(([, l]) => l.length >= 2).map(([h, l]) => ({ h, n: l.length, pnl: net(l) })).sort((a, b) => a.pnl - b.pnl);
    if (hs.length >= 2) {
      const worst = hs[0], best = hs[hs.length - 1];
      const grossLoss = -net(trades.filter((t) => t.pnl < 0));
      if (worst.pnl < 0 && -worst.pnl >= Math.max(25, grossLoss * 0.15)) out.push({ tone: "bad", title: `${worst.h}:00–${worst.h}:59 is costing you`,
        text: `${plural(worst.n, "trade")} entered in that hour lost ${money(-worst.pnl)}. Your best hour is ${best.h}:00 (${signedMoney(best.pnl)}, ${plural(best.n, "trade")}).` });
      else if (best.pnl > 0) out.push({ tone: "good", title: `Your hour: ${best.h}:00 New York`,
        text: `${signedMoney(best.pnl)} from ${plural(best.n, "trade")} entered between ${best.h}:00 and ${best.h}:59.` });
    }

    // 4. exits: how much of the move winners keep, and losers that were green first
    const withExc = trades.filter((t) => t.mfe != null);
    const winners = withExc.filter((t) => t.pnl > 0 && t.mfe > 0);
    if (winners.length >= 3) {
      const kept = winners.reduce((a, t) => a + Math.min(1, ((t.exit_px - t.entry_px) * t.side) / t.mfe), 0) / winners.length;
      if (kept < 0.55) out.push({ tone: "bad", title: "You exit winners early",
        text: `Your winners kept ${Math.round(kept * 100)}% of their best move on average. Trailing the stop or leaving a runner could pay more.` });
      else out.push({ tone: "good", title: "Good exits on winners",
        text: `Your winners kept ${Math.round(kept * 100)}% of their best move on average.` });
    }
    const greenLosers = withExc.filter((t) => t.pnl < 0 && t.mfe > 0 && t.mfe >= Math.abs(t.exit_px - t.entry_px));
    if (greenLosers.length >= 2) {
      out.push({ tone: "bad", title: "Winners that turned into losers",
        text: `${plural(greenLosers.length, "losing trade")} had been in profit by at least as much as they finally lost (${money(-net(greenLosers))} in total). A move to breakeven at that point would have saved most of it.` });
    }

    // 5. stop sizing: how much heat winners take vs. losers
    const wHeat = winners.map((t) => t.mae).sort((a, b) => a - b);
    const losers = withExc.filter((t) => t.pnl < 0);
    if (wHeat.length >= 5 && losers.length >= 3) {
      const p90 = wHeat[Math.min(wHeat.length - 1, Math.ceil(wHeat.length * 0.9) - 1)];
      const lHeat = losers.reduce((a, t) => a + t.mae, 0) / losers.length;
      if (lHeat > p90 * 1.3) out.push({ tone: "info", title: "Where your stop could be",
        text: `9 of 10 of your winners never went more than ${p90.toFixed(2)} pts against you, but your losers averaged ${lHeat.toFixed(2)} pts of heat. A stop around ${p90.toFixed(2)} pts would have cut them earlier.` });
    }

    // 6. long vs. short
    const L = trades.filter((t) => t.side > 0), S = trades.filter((t) => t.side < 0);
    if (L.length >= 3 && S.length >= 3) {
      const a = net(L), b = net(S);
      if (Math.sign(a) !== Math.sign(b)) out.push({ tone: "info", title: a > b ? "Longs work, shorts don't" : "Shorts work, longs don't",
        text: `Longs: ${signedMoney(a)} over ${plural(L.length, "trade")}. Shorts: ${signedMoney(b)} over ${plural(S.length, "trade")}.` });
    }

    // 7. setups
    const tagged = trades.filter((t) => t.setup);
    const untagged = trades.length - tagged.length;
    const bySetup = setupStats(tagged).filter((x) => x.n >= 3);
    if (bySetup.length >= 2) {
      const best = bySetup[0], worst = bySetup[bySetup.length - 1];
      if (worst.net < 0) out.push({ tone: "bad", title: `Drop "${worst.name}"?`,
        text: `${worst.name} lost ${money(-worst.net)} over ${plural(worst.n, "trade")} (${pct(worst.wr)} win rate), while ${best.name} made ${signedMoney(best.net)}.` });
    }
    if (untagged > trades.length / 2) out.push({ tone: "info", title: "Tag your setups",
      text: `${untagged} of ${trades.length} trades have no setup. Tag them in the card that pops up after each trade (or on the Trades page) and this page will show which setups actually make money.` });
    return out;
  }

  function setupStats(trades) {
    const m = new Map();
    for (const t of trades) { const k = t.setup || "Untagged"; m.set(k, [...(m.get(k) || []), t]); }
    return [...m].map(([name, l]) => {
      const w = l.filter((t) => t.pnl > 0), lo = l.filter((t) => t.pnl < 0);
      const gw = net(w), gl = net(lo);
      return { name, n: l.length, net: gw + gl, wr: w.length / l.length, avg: (gw + gl) / l.length, pf: gl ? gw / -gl : gw > 0 ? Infinity : NaN };
    }).sort((a, b) => b.net - a.net);
  }

  function insightsPanel(trades) {
    const list = insights(trades);
    const icon = { good: "▲", bad: "▼", info: "●" };
    return `<div class="panel insights" style="margin-top:16px">
      <h3>Edge finder <span class="muted">what your trades say</span></h3>
      ${list.length ? `<div class="ins-grid">${list.map((i) => `<div class="ins ${i.tone}"><span class="ins-i">${icon[i.tone]}</span><div><b>${esc(i.title)}</b><p>${i.text}</p></div></div>`).join("")}</div>`
        : `<div class="empty-chart" style="height:auto;padding:18px 0">${trades.length < 5 ? `Take ${5 - trades.length} more trade${trades.length === 4 ? "" : "s"} and this will start pointing out what works and what doesn't.` : "Nothing stands out yet. Keep trading and tagging setups."}</div>`}
    </div>`;
  }

  function setupPanel(trades) {
    if (!trades.some((t) => t.setup)) return "";
    const rows = setupStats(trades);
    return `<div class="panel" style="margin-top:16px"><h3>By setup</h3><div class="table-wrap"><table class="t">
      <thead><tr><th>Setup</th><th class="num">Trades</th><th class="num">Win rate</th><th class="num">Profit factor</th><th class="num">Avg / trade</th><th class="num">Net P&amp;L</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td><b>${esc(r.name)}</b></td><td class="num">${r.n}</td><td class="num">${pct(r.wr)}</td>
        <td class="num">${isFinite(r.pf) ? r.pf.toFixed(2) : r.pf === Infinity ? "∞" : "–"}</td>
        <td class="num ${cls(r.avg)}">${signedMoney(r.avg)}</td><td class="num ${cls(r.net)}">${signedMoney(r.net)}</td></tr>`).join("")}</tbody>
    </table></div></div>`;
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
        ${insightsPanel(trades)}
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
        </div>
        ${setupPanel(trades)}`;
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
              <button type="submit" class="btn btn-primary" id="impBtn" disabled>Import</button>
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
        symbols = await api("/api/symbols");
        drawLibrary();
      };
      xhr.onerror = () => { done(); msg.className = "hint err"; msg.textContent = "Import failed: the program is not responding."; };
      xhr.send(fd);
    });
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
    setRules(b ? b.rules : null, b ? b.balance : 50000);
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

  /** Put a session's rules into the dialog, picking the matching preset when there is one. */
  function setRules(r, balance) {
    const sel = $("fRules");
    const key = r ? `${balance},${r.target},${r.max_dd},${r.daily_loss}` : "";
    sel.value = [...sel.options].some((o) => o.value === key) ? key : r ? "custom" : "";
    $("fTarget").value = r ? r.target : 3000; $("fDd").value = r ? r.max_dd : 2000; $("fDaily").value = r ? r.daily_loss : 1000;
    showRuleFields();
  }
  function showRuleFields() {
    const v = $("fRules").value;
    $("fRuleVals").hidden = v !== "custom";
    $("fRuleHint").hidden = !v;
  }
  $("fRules").addEventListener("change", () => {
    const v = $("fRules").value;
    if (v && v !== "custom") {
      const [bal, target, dd, daily] = v.split(",").map(Number);
      $("fBal").value = bal; $("fTarget").value = target; $("fDd").value = dd; $("fDaily").value = daily;
    }
    showRuleFields();
  });
  const dialogRules = () => ($("fRules").value
    ? { target: +$("fTarget").value || 0, max_dd: +$("fDd").value || 0, daily_loss: +$("fDaily").value || 0 } : null);

  $("dlgForm").addEventListener("submit", async (e) => {
    if (e.submitter && e.submitter.value === "cancel") return;
    e.preventDefault();
    const err = $("dlgErr");
    err.hidden = true;
    try {
      const end_ts = parseNY(`${$("fEnd").value}T17:00`);
      if (editing) {
        const body = {
          name: $("fName").value, end_ts: Math.max(end_ts, editing.start_ts + 60000),
          balance: +$("fBal").value, fee_per_side: +$("fFee").value,
        };
        const rules = dialogRules(), old = editing.rules || null;
        if (JSON.stringify(rules) !== JSON.stringify(old && { target: old.target, max_dd: old.max_dd, daily_loss: old.daily_loss })) {
          if (old && !confirm("Changing the rules restarts this session's evaluation status. Continue?")) return;
          body.rules = rules;
        }
        await post(`/api/backtests/${editing.id}`, body, "PATCH");
      } else {
        const rank = (s) => (/^NQ/.test(s) ? 0 : /^ES/.test(s) ? 1 : 2);
        const syms = [...$("fSyms").querySelectorAll("input:checked")].map((x) => x.value).sort((a, b) => rank(a) - rank(b));
        if (!syms.length) throw new Error("Pick at least one symbol");
        const start_ts = parseNY(`${$("fStart").value}T${$("fStartTime").value}`);
        if (end_ts <= start_ts) throw new Error("The end date must be after the start date");
        const b = await post("/api/backtests", {
          name: $("fName").value, symbols: syms, start_ts, end_ts, balance: +$("fBal").value, fee_per_side: +$("fFee").value,
          rules: dialogRules(),
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
    route();
    fetch("version.json").then((r) => r.json()).then((v) => { $("ver").textContent = v.version === "dev" ? "dev build" : "v" + v.version; }).catch(() => {});
    // Trading opens the most recently played session, or a free replay
    if (backtests.length) $("navTrading").href = `chart.html?bt=${backtests[0].id}`;
  })();
})();
