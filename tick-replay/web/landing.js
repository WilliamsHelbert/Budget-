(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const WEEKDAY = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "UTC" });
  const DATE_NY = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }); // YYYY-MM-DD
  const TIME_NY = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  let symbols = [];
  let retry = null;

  /** Weekdays with data (a UTC day file covers that date's 09:30 New York open). */
  function sessions(sym) {
    return sym.days.filter((d) => {
      const wd = new Date(d + "T12:00:00Z").getUTCDay();
      return wd >= 1 && wd <= 5;
    }).reverse();
  }

  function fillDays() {
    const sym = symbols.find((s) => s.symbol === $("sym").value);
    if (!sym) return;
    const days = sessions(sym);
    $("day").innerHTML = days.map((d) => `<option value="${d}">${WEEKDAY.format(new Date(d + "T12:00:00Z"))} ${d}</option>`).join("");
    $("free").href = `chart.html?symbol=${encodeURIComponent(sym.symbol)}`;
    $("openForm").querySelector("button").disabled = days.length === 0;
  }

  async function refresh() {
    clearTimeout(retry);
    const r = await fetch("/api/symbols");
    symbols = await r.json();

    if (!symbols.length) {
      $("dataRows").innerHTML = `<tr><td colspan="5" class="muted">No tick data yet. Demo data is being prepared (a few seconds), or import your own below.</td></tr>`;
      $("sym").innerHTML = "";
      $("day").innerHTML = "";
      $("openForm").querySelector("button").disabled = true;
      retry = setTimeout(refresh, 2000);
      return;
    }

    $("dataRows").innerHTML = symbols.map((s) => `
      <tr><td><strong>${esc(s.symbol)}</strong></td>
      <td>${DATE_NY.format(new Date(s.first_ts))}</td>
      <td>${DATE_NY.format(new Date(s.last_ts))}</td>
      <td>${s.days.length}</td>
      <td style="text-align:right"><button class="del" data-sym="${esc(s.symbol)}" title="Delete this data">Delete</button></td></tr>`).join("");

    const prev = $("sym").value;
    $("sym").innerHTML = symbols.map((s) => `<option>${esc(s.symbol)}</option>`).join("");
    const pick = [prev, "NQ", "ES"].find((x) => symbols.some((s) => s.symbol === x)) || symbols[0].symbol;
    $("sym").value = pick;
    fillDays();
  }

  function importFiles(e) {
    e.preventDefault();
    const files = $("impFiles").files;
    if (!files.length) return;
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    fd.append("symbol", $("impSym").value.trim().toUpperCase());
    fd.append("tz", $("impTz").value);

    const msg = $("impMsg"), btn = $("impBtn");
    btn.disabled = true;
    msg.className = "hint progress";
    msg.textContent = "Uploading…";

    // XHR instead of fetch for upload progress (tick files can be large)
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/import");
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) {
        const pct = Math.round((ev.loaded / ev.total) * 100);
        msg.textContent = pct < 100 ? `Uploading… ${pct}%` : "Reading ticks… (large files can take a minute)";
      }
    };
    xhr.onload = () => {
      btn.disabled = false;
      let r = {};
      try { r = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
      if (xhr.status !== 200) {
        msg.className = "hint err";
        msg.textContent = "Import failed: " + (r.detail || xhr.statusText);
        return;
      }
      msg.className = "hint ok";
      msg.textContent =
        `Imported ${r.ticks.toLocaleString("en-US")} ticks into ${r.symbol} (${r.days} day${r.days === 1 ? "" : "s"}). ` +
        `First tick ${TIME_NY.format(new Date(r.first_ts))}, last ${TIME_NY.format(new Date(r.last_ts))} New York time. ` +
        `If those times look hours off, import again with a different time zone.`;
      $("impFiles").value = "";
      refresh().then(() => { $("sym").value = r.symbol; fillDays(); });
    };
    xhr.onerror = () => {
      btn.disabled = false;
      msg.className = "hint err";
      msg.textContent = "Import failed: the program is not responding.";
    };
    xhr.send(fd);
  }

  async function del(e) {
    const sym = e.target.dataset.sym;
    if (!sym || !confirm(`Delete all ${sym} tick data from this computer?`)) return;
    const r = await fetch(`/api/symbols/${encodeURIComponent(sym)}`, { method: "DELETE" });
    if (!r.ok) alert("Delete failed: " + (await r.text()));
    refresh();
  }

  $("sym").addEventListener("change", fillDays);
  $("dataRows").addEventListener("click", del);
  $("importForm").addEventListener("submit", importFiles);
  $("openForm").addEventListener("submit", (e) => {
    e.preventDefault();
    if (!$("day").value) return;
    const q = new URLSearchParams({ symbol: $("sym").value, date: $("day").value, open: "1", tf: "60" });
    location.href = `chart.html?${q}`;
  });

  // tells the desktop program a window is still open
  const ping = () => fetch("/api/ping").catch(() => {});
  ping();
  setInterval(ping, 20000);

  refresh().catch((e) => {
    $("dataRows").innerHTML = `<tr><td colspan="5" class="muted">Could not reach the program (${esc(e.message)}). Is it running?</td></tr>`;
  });
})();
