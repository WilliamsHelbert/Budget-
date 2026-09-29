/* Start page: live mini replay of the latest open, session cards, data library and import. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const api = async (path) => {
    const r = await fetch(path);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  };

  const TZ = "America/New_York";
  const tzParts = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const DAY_LONG = new Intl.DateTimeFormat("en-US", { weekday: "long", timeZone: "UTC" });
  const DAY_SHORT = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "UTC" });
  const MONTH_DAY = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const MONTH_DAY_Y = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  const DATE_NY = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });

  function nyOffsetSec(ms) {
    const p = Object.fromEntries(tzParts.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
    const wall = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
    return Math.round((wall - Math.floor(ms / 1000) * 1000) / 1000);
  }
  const clockNY = (ms) => new Date(ms + nyOffsetSec(ms) * 1000).toISOString().slice(11, 23);
  const dayDate = (iso) => new Date(iso + "T12:00:00Z");
  const fmtPx = (v) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtVol = (v) => (v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e3 ? (v / 1e3).toFixed(0) + "k" : String(v));
  const signed = (v, d = 2) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d);
  const chartUrl = (params) => `chart.html?${new URLSearchParams(params)}`;

  let symbols = [];
  let sym = null;
  const sessionsCache = new Map();

  // ---- symbol switch -------------------------------------------------------

  function renderSwitches() {
    const html = symbols.map((s) =>
      `<button type="button" data-sym="${esc(s.symbol)}" class="${s.symbol === sym ? "on" : ""}">${esc(s.symbol)}</button>`).join("");
    $("symSwitch").innerHTML = html;
    $("symSwitch2").innerHTML = html;
  }

  function onSwitch(e) {
    const s = e.target.dataset && e.target.dataset.sym;
    if (s && s !== sym) selectSymbol(s);
  }

  async function selectSymbol(s) {
    sym = s;
    renderSwitches();
    $("heroFree").href = chartUrl({ symbol: sym });
    $("navChart").href = chartUrl({ symbol: sym });
    let sessions = sessionsCache.get(sym);
    if (!sessions) {
      sessions = await api(`/api/sessions?symbol=${encodeURIComponent(sym)}`);
      sessionsCache.set(sym, sessions);
    }
    if (s !== sym) return;
    renderHero(sessions);
    renderCards(sessions);
    startLive(sessions[0]);
  }

  // ---- hero ----------------------------------------------------------------

  function renderHero(sessions) {
    const latest = sessions[0];
    const info = symbols.find((x) => x.symbol === sym);
    $("statSessions").textContent = sessions.length;
    $("statQuotes").textContent = info && info.quotes ? "Bid/Ask" : "Trades";
    const btn = $("heroOpen");
    btn.disabled = !latest;
    $("heroOpenLabel").textContent = latest
      ? `Market Open · ${DAY_SHORT.format(dayDate(latest.date))} ${MONTH_DAY.format(dayDate(latest.date))}`
      : "Market Open";
    btn.onclick = () => { if (latest) location.href = chartUrl({ symbol: sym, date: latest.date, open: 1, tf: 60 }); };
  }

  // ---- live mini replay ----------------------------------------------------

  const LIVE_PRE_MS = 20000;   // start 20 s before the bell
  const LIVE_LEN_MS = 150000;  // then loop after 2.5 minutes
  const LIVE_TF = 5;           // 5-second candles
  let liveChart = null, liveSeries = null;
  const live = { gen: 0 };

  function ensureLiveChart() {
    if (liveChart) return;
    liveChart = LightweightCharts.createChart($("liveChart"), {
      autoSize: true,
      localization: { locale: "en-US" },
      layout: { background: { color: "transparent" }, textColor: "#8a91a3", fontSize: 11, attributionLogo: false },
      grid: { vertLines: { visible: false }, horzLines: { color: "rgba(255,255,255,.04)" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: true, rightOffset: 4 },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      handleScroll: false,
      handleScale: false,
    });
    liveSeries = liveChart.addCandlestickSeries({
      upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
      wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    });
  }

  async function startLive(session) {
    const gen = ++live.gen;
    if (!session) {
      $("liveDate").textContent = "No sessions yet";
      return;
    }
    ensureLiveChart();
    const start = session.open_ts - LIVE_PRE_MS, end = start + LIVE_LEN_MS;
    const q = encodeURIComponent(sym);
    const [hist, tk] = await Promise.all([
      api(`/api/candles?symbol=${q}&tf=${LIVE_TF}&end=${start}&count=80`),
      api(`/api/ticks?symbol=${q}&after=${start}&until=${end}&limit=200000`),
    ]);
    if (gen !== live.gen) return;

    const off = nyOffsetSec(start);
    liveSeries.setData(hist.map((c) => ({ time: c.time + off, open: c.open, high: c.high, low: c.low, close: c.close })));
    liveChart.timeScale().scrollToRealTime();
    $("liveSym").textContent = sym;
    $("liveDate").textContent = `${DAY_LONG.format(dayDate(session.date))}, ${MONTH_DAY_Y.format(dayDate(session.date))} · the open`;

    const lastC = hist[hist.length - 1];
    let bar = lastC ? { ...lastC } : null;
    let last = lastC ? lastC.close : session.open, prevShown = last;
    const tape = [];
    let t = start, i = 0, prevFrame = performance.now(), tapeDirty = true, lastTapeRender = 0;

    function apply(k) {
      const ts = tk.ts[k], px = tk.price[k], sz = tk.size[k];
      const b = Math.floor(ts / 1000 / LIVE_TF) * LIVE_TF;
      if (!bar || b > bar.time) {
        if (bar) liveSeries.update({ ...bar, time: bar.time + off });
        bar = { time: b, open: px, high: px, low: px, close: px };
      } else {
        bar.high = Math.max(bar.high, px);
        bar.low = Math.min(bar.low, px);
        bar.close = px;
      }
      const side = tk.side[k] || (px > last ? 1 : px < last ? -1 : 0);
      last = px;
      tape.push([ts, px, sz, side]);
      if (tape.length > 12) tape.shift();
      tapeDirty = true;
    }

    function frame(now) {
      if (gen !== live.gen) return;
      t += Math.min(now - prevFrame, 250);
      prevFrame = now;
      const before = i;
      while (i < tk.ts.length && tk.ts[i] <= t) apply(i++);
      if (i > before && bar) liveSeries.update({ ...bar, time: bar.time + off });

      const priceEl = $("livePrice");
      if (last !== prevShown) {
        priceEl.className = "live-price " + (last > prevShown ? "up" : "down");
        prevShown = last;
      }
      priceEl.textContent = fmtPx(last);
      const chg = last - session.pre_open;
      $("liveChg").innerHTML = `<span class="${chg >= 0 ? "b" : "s"}" style="color:var(--${chg >= 0 ? "up" : "down"})">${signed(chg)} (${signed((chg / session.pre_open) * 100)}%)</span>`;
      $("liveClock").textContent = clockNY(t);

      const badge = $("liveBadge");
      const toOpen = session.open_ts - t;
      if (toOpen > 0) {
        badge.className = "live-badge";
        badge.innerHTML = `<span class="dot"></span> OPENS IN 0:${String(Math.ceil(toOpen / 1000)).padStart(2, "0")}`;
      } else if (!badge.classList.contains("open")) {
        badge.className = "live-badge open";
        badge.innerHTML = `<span class="dot"></span> MARKET OPEN`;
      }

      if (tapeDirty && now - lastTapeRender > 120) {
        $("liveTape").innerHTML = tape.slice(-6).reverse().map(([ts, px, sz, side]) =>
          `<span class="${side > 0 ? "b" : side < 0 ? "s" : ""}"><b>${fmtPx(px)}</b> ${sz}</span>`).join("");
        tapeDirty = false;
        lastTapeRender = now;
      }

      if (t >= end) {
        setTimeout(() => { if (gen === live.gen) startLive(session); }, 1500);
        return;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ---- session cards -------------------------------------------------------

  function spark(values, up, id) {
    if (!values || values.length < 2) return "";
    const w = 240, h = 64, pad = 4;
    const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
    const pts = values.map((v, k) => [
      (k / (values.length - 1)) * w,
      pad + (1 - (v - lo) / span) * (h - pad * 2),
    ]);
    const line = pts.map(([x, y], k) => `${k ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join("");
    const color = up ? "#26a69a" : "#ef5350";
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
      <defs><linearGradient id="g${id}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${line}L${w},${h}L0,${h}Z" fill="url(#g${id})"/>
      <path d="${line}" fill="none" stroke="${color}" stroke-width="1.8" vector-effect="non-scaling-stroke"/>
    </svg>`;
  }

  function renderCards(sessions) {
    if (!sessions.length) {
      $("cards").innerHTML = `<div class="empty">No regular sessions in this data yet.</div>`;
      return;
    }
    $("cards").innerHTML = sessions.map((s, k) => {
      const chg = s.close - s.open, pct = (chg / s.open) * 100, up = chg >= 0;
      const d = dayDate(s.date);
      return `<article class="card">
        <div class="card-top">
          <div><div class="card-day">${DAY_LONG.format(d)}</div><div class="card-date">${MONTH_DAY_Y.format(d)}</div></div>
          <div class="chg ${up ? "up" : "down"}">${signed(chg)}<br><span class="small">${signed(pct)}%</span></div>
        </div>
        ${spark(s.spark, up, k)}
        <dl class="card-stats">
          <div><dt>Range</dt><dd>${(s.high - s.low).toFixed(2)}</dd></div>
          <div><dt>First 5m</dt><dd>${s.range_5m.toFixed(2)}</dd></div>
          <div><dt>Volume</dt><dd>${fmtVol(s.volume)}</dd></div>
        </dl>
        <div class="card-actions">
          <a class="btn btn-gold" href="${chartUrl({ symbol: sym, date: s.date, open: 1, tf: 60 })}">🔔 Market Open</a>
          <a class="btn btn-ghost" href="${chartUrl({ symbol: sym, date: s.date })}">Chart</a>
        </div>
      </article>`;
    }).join("");
  }

  // ---- library -------------------------------------------------------------

  function renderLibrary() {
    if (!symbols.length) {
      $("lib").innerHTML = `<p class="muted">No data yet. Demo data is being prepared (a few seconds), or import your own.</p>`;
      return;
    }
    $("lib").innerHTML = symbols.map((s) => {
      const demo = /-DEMO$/i.test(s.symbol);
      return `<div class="lib-item">
        <div class="lib-sym">${esc(s.symbol)}</div>
        <div class="lib-meta">
          ${DATE_NY.format(new Date(s.first_ts))} → ${DATE_NY.format(new Date(s.last_ts))} · ${s.days.length} day${s.days.length === 1 ? "" : "s"}
          <span class="badge ${s.quotes ? "q" : "t"}">${s.quotes ? "BID/ASK" : "TRADES"}</span>${demo ? `<span class="badge demo">DEMO</span>` : ""}
        </div>
        <button class="btn btn-danger btn-sm" data-del="${esc(s.symbol)}">Delete</button>
      </div>`;
    }).join("");
  }

  async function onLibraryClick(e) {
    const s = e.target.dataset && e.target.dataset.del;
    if (!s || !confirm(`Delete all ${s} tick data from this computer?`)) return;
    const r = await fetch(`/api/symbols/${encodeURIComponent(s)}`, { method: "DELETE" });
    if (!r.ok) alert("Delete failed: " + (await r.text()));
    sessionsCache.delete(s);
    refresh();
  }

  // ---- import --------------------------------------------------------------

  function showPicked() {
    const files = $("impFiles").files;
    const drop = $("drop");
    if (!files.length) {
      drop.classList.remove("has");
      $("dropTitle").textContent = "Drop tick files here";
      $("dropSub").textContent = "or click to choose · .csv · .csv.zst · .txt";
      $("impBtn").disabled = true;
      return;
    }
    const total = [...files].reduce((a, f) => a + f.size, 0);
    drop.classList.add("has");
    $("dropTitle").textContent = `${files.length} file${files.length === 1 ? "" : "s"} ready`;
    $("dropSub").textContent = `${(total / 1024 / 1024).toFixed(1)} MB · click to change`;
    $("impBtn").disabled = false;
  }

  function setupDrop() {
    const drop = $("drop");
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      if (e.dataTransfer.files.length) {
        $("impFiles").files = e.dataTransfer.files;
        showPicked();
      }
    });
    $("impFiles").addEventListener("change", showPicked);
  }

  function importFiles(e) {
    e.preventDefault();
    const files = $("impFiles").files;
    if (!files.length) return;
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    fd.append("symbol", $("impSym").value.trim().toUpperCase());
    fd.append("tz", $("impTz").value);

    const msg = $("impMsg"), btn = $("impBtn"), bar = $("impBar"), fill = bar.firstElementChild;
    btn.disabled = true;
    bar.hidden = false;
    bar.classList.remove("busy");
    fill.style.width = "0";
    msg.className = "hint";
    msg.textContent = "Uploading…";

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/import");
    xhr.upload.onprogress = (ev) => {
      if (!ev.lengthComputable) return;
      const pct = Math.round((ev.loaded / ev.total) * 100);
      fill.style.width = pct + "%";
      if (pct >= 100) {
        bar.classList.add("busy");
        msg.textContent = "Reading ticks… large files can take a minute.";
      } else {
        msg.textContent = `Uploading… ${pct}%`;
      }
    };
    const done = () => { btn.disabled = false; bar.hidden = true; };
    xhr.onload = () => {
      done();
      let r = {};
      try { r = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status !== 200) {
        msg.className = "hint err";
        msg.textContent = "Import failed: " + (r.detail || xhr.statusText);
        return;
      }
      const fmt = (ms) => `${DATE_NY.format(new Date(ms))} ${clockNY(ms).slice(0, 5)}`;
      msg.className = "hint ok";
      msg.textContent =
        `✓ ${r.ticks.toLocaleString("en-US")} tick${r.ticks === 1 ? "" : "s"} into ${r.symbol} (${r.days} day${r.days === 1 ? "" : "s"}` +
        `${r.has_quotes ? ", with bid/ask" : ""}). First ${fmt(r.first_ts)}, last ${fmt(r.last_ts)} New York. ` +
        `If those times are hours off, import again with another time zone.`;
      $("impFiles").value = "";
      showPicked();
      sessionsCache.delete(r.symbol);
      refresh(r.symbol);
    };
    xhr.onerror = () => {
      done();
      msg.className = "hint err";
      msg.textContent = "Import failed: the program is not responding.";
    };
    xhr.send(fd);
  }

  // ---- boot ----------------------------------------------------------------

  let retry = null;

  async function refresh(prefer) {
    clearTimeout(retry);
    symbols = await api("/api/symbols");
    renderLibrary();
    if (!symbols.length) {
      $("cards").innerHTML = `<div class="empty">No data yet. Import tick files below. Demo data appears here in a few seconds on first start.</div>`;
      retry = setTimeout(() => refresh(), 2000);
      return;
    }
    const has = (s) => s && symbols.some((x) => x.symbol === s);
    const real = symbols.filter((x) => !/-DEMO$/i.test(x.symbol)).map((x) => x.symbol);
    const pick = [prefer, sym, "NQ", "ES", real[0], "NQ-DEMO"].find(has) || symbols[0].symbol;
    sym = null;
    await selectSymbol(pick);
  }

  $("symSwitch").addEventListener("click", onSwitch);
  $("symSwitch2").addEventListener("click", onSwitch);
  $("lib").addEventListener("click", onLibraryClick);
  $("importForm").addEventListener("submit", importFiles);
  setupDrop();

  // tells the desktop program a window is still open
  const ping = () => fetch("/api/ping").catch(() => {});
  ping();
  setInterval(ping, 20000);

  refresh().catch((e) => {
    $("cards").innerHTML = `<div class="empty">Could not reach the program (${esc(e.message)}). Is it running?</div>`;
  });
})();
