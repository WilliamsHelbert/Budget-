(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const WEEKDAY = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: "UTC" });
  const DATE_NY = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }); // YYYY-MM-DD

  let symbols = [];

  /** Weekdays with data (a UTC day file covers that date's 09:30 New York open). */
  function sessions(sym) {
    return sym.days.filter((d) => {
      const wd = new Date(d + "T12:00:00Z").getUTCDay();
      return wd >= 1 && wd <= 5;
    }).reverse();
  }

  function fillDays() {
    const sym = symbols.find((s) => s.symbol === $("sym").value);
    const days = sessions(sym);
    $("day").innerHTML = days.map((d) => `<option value="${d}">${WEEKDAY.format(new Date(d + "T12:00:00Z"))} ${d}</option>`).join("");
    $("free").href = `chart.html?symbol=${encodeURIComponent(sym.symbol)}`;
    $("openForm").querySelector("button").disabled = days.length === 0;
  }

  async function init() {
    const r = await fetch("/api/symbols");
    symbols = await r.json();

    if (!symbols.length) {
      $("dataRows").innerHTML = `<tr><td colspan="4" class="muted">No tick data yet. Run <code>python tools/make_sample.py</code> or import your own.</td></tr>`;
      $("openForm").querySelector("button").disabled = true;
      return;
    }

    $("dataRows").innerHTML = symbols.map((s) => `
      <tr><td><strong>${s.symbol}</strong></td>
      <td>${DATE_NY.format(new Date(s.first_ts))}</td>
      <td>${DATE_NY.format(new Date(s.last_ts))}</td>
      <td>${s.days.length}</td></tr>`).join("");

    $("sym").innerHTML = symbols.map((s) => `<option>${s.symbol}</option>`).join("");
    if (symbols.some((s) => s.symbol === "NQ")) $("sym").value = "NQ";
    fillDays();
    $("sym").addEventListener("change", fillDays);

    $("openForm").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = new URLSearchParams({ symbol: $("sym").value, date: $("day").value, open: "1", tf: "60" });
      location.href = `chart.html?${q}`;
    });
  }

  init().catch((e) => {
    $("dataRows").innerHTML = `<tr><td colspan="4" class="muted">Could not reach the server (${e.message}). Is it running?</td></tr>`;
  });
})();
