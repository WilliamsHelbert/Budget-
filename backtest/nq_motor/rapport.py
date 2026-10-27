"""HTML-rapport for NQ FVG-motoren: noegletal, equity-kurve, tabel og et chart pr. trade."""
import html, os
import pandas as pd
import fvg_model as f

DK = pd.Timedelta(hours=6)
DAYN = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
MDR = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
MAX_CHARTS = 150          # flere trades end det: kun tabel og maanedsoversigt (siden bliver ellers for stor)
d = None                  # 15s-data, saettes af motor.py


def n(v):
    return f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def chart(r):
    tp = r["tp"]; ex = r["exit_ts"]
    s0 = min(r["sweep_ts"], min(g[2] for g in r["gaps5"]) - pd.Timedelta(minutes=10)) - pd.Timedelta(minutes=40)
    s1 = min(max(r["ts"] + pd.Timedelta(minutes=40), ex + pd.Timedelta(minutes=15)), r["ts"] + pd.Timedelta(hours=5))
    s0 = max(s0, r["ts"] - pd.Timedelta(hours=5))
    b = f.bars(d[s0:s1], 5)
    W, H, L, R, T0, BT = 760, 360, 8, 86, 14, 26
    ps = [b.low.min(), b.high.max(), r["sl"], r["lvl"], tp]
    lo, hi = min(ps), max(ps); pad = (hi - lo) * 0.04; lo -= pad; hi += pad
    y = lambda p: T0 + (hi - p) / (hi - lo) * (H - T0 - BT)
    nb = len(b); cw = (W - L - R) / nb
    x = lambda i: L + cw * (i + 0.5)
    idx = {ts: i for i, ts in enumerate(b.index)}

    def xt(ts):
        k = ts.floor("5min")
        return L if k < b.index[0] else x(idx.get(k, nb - 1))
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="5m chart for trade {r["entry_dk"]}">']
    ei = xt(r["ts"] - pd.Timedelta(minutes=1)); xe = max(xt(ex) - ei, cw)
    o.append(f'<rect class="zone-tp" x="{ei:.1f}" y="{min(y(tp), y(r["entry"])):.1f}" width="{xe:.1f}" height="{abs(y(tp) - y(r["entry"])):.1f}"/>')
    o.append(f'<rect class="zone-sl" x="{ei:.1f}" y="{min(y(r["sl"]), y(r["entry"])):.1f}" width="{xe:.1f}" height="{abs(y(r["sl"]) - y(r["entry"])):.1f}"/>')
    for k, (a, c, t3) in enumerate(sorted(r["gaps5"], key=lambda g: g[2])):
        x0 = xt(t3 - pd.Timedelta(minutes=10)) - cw / 2
        o.append(f'<rect class="gap5" x="{x0:.1f}" y="{y(max(a, c)):.1f}" width="{ei - x0:.1f}" height="{max(abs(y(a) - y(c)), 1.5):.1f}"/>')
        o.append(f'<text class="gapt" x="{x0 + 3:.1f}" y="{y(max(a, c)) - 3:.1f}">5m gap {k + 1}</text>')
    a, c, t3 = r["efvg"]; m = int(r["fvg_tf"][:-1])
    x0 = xt(t3 - pd.Timedelta(minutes=2 * m)) - cw / 2
    o.append(f'<rect class="egap" x="{x0:.1f}" y="{y(max(a, c)):.1f}" width="{max(ei - x0, cw):.1f}" height="{max(abs(y(a) - y(c)), 1.5):.1f}"/>')
    o.append(f'<text class="egapt" x="{x0 + 3:.1f}" y="{y(min(a, c)) + 11:.1f}">entry-gap {r["fvg_tf"]}</text>')
    sx = xt(r["sweep_ts"])
    o.append(f'<line class="liq" x1="{L}" x2="{min(sx + cw * 3, W - R):.1f}" y1="{y(r["lvl"]):.1f}" y2="{y(r["lvl"]):.1f}"/>')
    o.append(f'<text class="lbl liqt" x="{L + 4}" y="{y(r["lvl"]) - 5:.1f}">{html.escape(r["sweep"].replace("i gaar", "i går"))}</text>')
    for i, (ts, q) in enumerate(b.iterrows()):
        c_ = "up" if q.close >= q.open else "dn"
        o.append(f'<line class="wick {c_}" x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(q.high):.1f}" y2="{y(q.low):.1f}"/>')
        t_, b_ = y(max(q.open, q.close)), y(min(q.open, q.close))
        o.append(f'<rect class="body {c_}" x="{x(i) - cw * .32:.1f}" y="{t_:.1f}" width="{cw * .64:.1f}" height="{max(b_ - t_, 1):.1f}"/>')
    for cls, v in (("len", r["entry"]), ("lsl", r["sl"]), ("ltp", tp)):
        yy = y(v)
        o.append(f'<line class="{cls}" x1="{ei:.1f}" x2="{W - R:.1f}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        o.append(f'<rect class="tag {cls}" x="{W - R + 4}" y="{yy - 9:.1f}" width="{R - 6}" height="18" rx="3"/><text class="tagt" x="{W - R + 8}" y="{yy + 4:.1f}">{v:,.2f}</text>')
    o.append(f'<line class="mark" x1="{sx:.1f}" x2="{sx:.1f}" y1="{T0}" y2="{H - BT}"/><text class="lbl" x="{sx + 3:.1f}" y="{H - BT - 4}">sweep</text>')
    o.append(f'<line class="mark" x1="{ei:.1f}" x2="{ei:.1f}" y1="{T0}" y2="{H - BT}"/><text class="lbl" x="{ei + 3:.1f}" y="{H - BT - 4}">entry</text>')
    step = 1 if nb < 50 else 2
    for i, ts in enumerate(b.index):
        tk = ts + DK
        if tk.minute == 0 and tk.hour % step == 0:
            o.append(f'<text class="ax" x="{x(i):.1f}" y="{H - 8}" text-anchor="middle">{tk:%H:%M}</text>')
    o.append("</svg>")
    return "".join(o)


def card(r, i, med_chart):
    ts = r["ts"] + DK; side = r["retning"].lower()
    g = sorted(r["gaps5"], key=lambda g: g[2])
    gtxt = " og ".join(f'{n(min(a, c))}–{n(max(a, c))} <span class="muted">{(t - pd.Timedelta(minutes=5) + DK):%H:%M}</span>' for a, c, t in g)
    part = (f'{n(r["partial"][0])} <span class="muted">4h, kl. {r["partial"][1]}, {r["partial"][2]:.2f}R. Uden: {r["R_uden"]:+.2f}R</span>'
            if r["partial"] else '<span class="muted">intet 4h ramt</span>')
    return f'''
<article class="trade" id="t{i}" data-side="{side}">
  <header class="th">
    <div class="tn">#{i}</div>
    <div class="tmeta"><span class="side {side}">{r["retning"].title()}</span><span>{DAYN[ts.weekday()]} {ts.day}. {MDR[ts.month - 1]} {ts.year}</span><span class="mono">{ts:%H:%M} DK</span><span class="pill">{r["fvg_tf"]} inversion</span><span class="pill">RR {abs(r.get("tp_start", r["tp"]) - r["entry"]) / r["risk"]:.2f}</span></div>
    <div class="res {"win" if r["R"] > 0 else "loss"}">{html.escape(r["udfald"])} <b class="mono">{r["R"]:+.2f}R</b> <small class="mono">{r["exit_dk"]}</small></div>
  </header>
  {f'<div class="chartwrap">{chart(r)}</div>' if med_chart else ''}
  <dl class="facts">
    <div><dt>Sweep</dt><dd>{html.escape(r["sweep"].replace("i gaar", "i går"))} <span class="mono muted">{(r["sweep_ts"] + DK):%H:%M}</span></dd></div>
    <div><dt>5m gaps</dt><dd class="mono">{gtxt}</dd></div>
    <div><dt>Entry / SL</dt><dd class="mono">{n(r["entry"])} / {n(r["sl"])} <span class="muted">({r["risk"]:.2f} p)</span></dd></div>
    <div><dt>TP</dt><dd class="mono">{n(r["tp"])} <span class="muted">{html.escape(r["tp_navn"])}</span></dd></div>
    <div><dt>25% ud</dt><dd class="mono">{part}</dd></div>
  </dl>
</article>'''


def equity(rows):
    W, H, L, R, T, B = 760, 220, 44, 14, 14, 26
    cum = [0.0]
    for r in rows:
        cum.append(cum[-1] + r["R"])
    lo, hi = min(cum + [0]), max(cum + [0]); pad = max((hi - lo) * 0.08, 1); lo -= pad; hi += pad
    nn = len(cum) - 1
    x = lambda i: L + (W - L - R) * i / max(nn, 1)
    y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Samlet R efter hvert trade">']
    step = max(1, round((hi - lo) / 5))
    v = (int(lo) // step) * step
    while v <= hi:
        if v >= lo:
            o.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/><text class="ax" x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v:+d}R</text>')
        v += step
    o.append(f'<line class="zero" x1="{L}" x2="{W - R}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    pts = " ".join(f"{x(i):.1f},{y(c):.1f}" for i, c in enumerate(cum))
    o.append(f'<polygon class="eqarea" points="{x(0):.1f},{y(0):.1f} {pts} {x(nn):.1f},{y(0):.1f}"/>')
    o.append(f'<polyline class="eqline" points="{pts}"/>')
    hw = (W - L - R) / max(nn, 1)
    for i, r in enumerate(rows, 1):
        tip = f'#{i} {(r["ts"] + DK):%d/%m %H:%M} {r["retning"].lower()} {r["R"]:+.2f}R · i alt {cum[i]:+.2f}R'
        o.append(f'<g><title>{tip}</title><rect class="eqhit" x="{x(i) - hw / 2:.1f}" y="{T}" width="{hw:.1f}" height="{H - T - B}"/>'
                 f'<circle class="eqdot" cx="{x(i):.1f}" cy="{y(cum[i]):.1f}" r="{4 if nn <= 80 else 2}"/></g>')
    o.append(f'<text class="ax" x="{L}" y="{H - 6}">trade 1</text><text class="ax" x="{W - R}" y="{H - 6}" text-anchor="end">trade {nn}</text></svg>')
    return "".join(o)


def variant_html(rows, partial):
    if not rows or "R_4h3" not in rows[0]:
        return ""
    def st(v):
        cum = peak = dd = 0
        for x in v:
            cum += x; peak = max(peak, cum); dd = min(dd, cum - peak)
        return f'<td class="mono num">{len(v)}</td><td class="mono num">{sum(1 for x in v if x > 0) / len(v):.0%}</td><td class="mono num {"pos" if sum(v) > 0 else "neg"}">{sum(v):+.2f}</td><td class="mono num neg">{dd:.2f}</td>'
    a, b = ("R_alt_partial", "R") if partial else ("R", "R_alt_partial")
    rk = [("Session-liq, ingen partial", [r[a] for r in rows]), ("Session-liq + 25% på 4h", [r[b] for r in rows]),
          ("Nærmeste af session-liq og 3. 4h, ingen partial", [r["R_4h3"] for r in rows]), ("Nærmeste af session-liq og 3. 4h + 25% på 4h", [r["R_4h3_partial"] for r in rows])]
    trs = "".join(f'<tr><td>{n}</td>{st(v)}</tr>' for n, v in rk)
    return f'<section><h2>TP-varianter</h2><div class="tablewrap"><table style="min-width:0"><thead><tr><th>TP</th><th class="num">Trades</th><th class="num">Vundne</th><th class="num">R</th><th class="num">Drawdown</th></tr></thead><tbody>{trs}</tbody></table></div></section>'


def html_rapport(rows, titel, fra, til, gp=None, partial=False, h4=False):
    totf = sum(r.get("R_fuld", 0) for r in rows)
    stil = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stil.html")).read().replace("{TITEL}", html.escape(titel))
    Rs = [r["R"] for r in rows]; tot = sum(Rs)
    cum, peak, dd = 0, 0, 0
    for v in Rs:
        cum += v; peak = max(peak, cum); dd = min(dd, cum - peak)
    win = sum(1 for v in Rs if v > 0) / len(Rs) if Rs else 0
    med_chart = len(rows) <= MAX_CHARTS
    trs = "".join(
        f'<tr data-side="{r["retning"].lower()}"><td class="mono"><a href="#t{i}">#{i}</a></td><td class="mono">{(r["ts"] + DK):%d/%m/%y %H:%M}</td>'
        f'<td><span class="side {r["retning"].lower()}">{r["retning"].title()}</span></td><td class="cs">{html.escape(r["sweep"].replace("i gaar", "i går"))}</td>'
        f'<td class="mono">{r["fvg_tf"]}</td><td class="mono num">{n(r["entry"])}</td><td class="mono num">{n(r["sl"])}</td>'
        f'<td class="cs">{html.escape(r["tp_navn"])}</td><td class="mono num">{abs(r.get("tp_start", r["tp"]) - r["entry"]) / r["risk"]:.2f}</td><td class="cs">{html.escape(r["udfald"])}</td><td class="mono num {"pos" if r["R"] > 0 else "neg"}">{r["R"]:+.2f}</td><td class="mono num {"pos" if r.get("R_fuld", 0) > 0 else "neg"}">{r.get("R_fuld", float("nan")):+.2f}</td><td class="mono num {"pos" if r.get("R_4h3", 0) > 0 else "neg"}">{r.get("R_4h3", float("nan")):+.2f}</td></tr>'
        for i, r in enumerate(rows, 1))
    mdr = {}
    for r in rows:
        k = f"{(r['ts'] + DK):%Y-%m}"; mdr.setdefault(k, []).append(r["R"])
    mrows = "".join(f'<tr><td class="mono">{MDR[int(k[5:]) - 1]} {k[:4]}</td><td class="mono num">{len(v)}</td><td class="mono num">{sum(1 for z in v if z > 0) / len(v):.0%}</td><td class="mono num {"pos" if sum(v) > 0 else "neg"}">{sum(v):+.2f}</td></tr>' for k, v in sorted(mdr.items()))
    cards = "".join(card(r, i, med_chart) for i, r in enumerate(rows, 1)) if med_chart else ""
    body = f'''<div class="wrap">
  <header class="hero">
    <div class="eyebrow">NQ · FVG-motoren · {fra} – {til}</div>
    <h1>{html.escape(titel)}</h1>
    <p class="lede">Alle trades motoren tager i perioden. Sweep af liq, reaktion ind i de to nyeste 5m gaps, {"entry med limit i " + f"{gp:.3f}".replace(".", ",") + " af vejen tilbage mod SL efter inversionen" if gp else "entry på inversion af det ældste gap i reaktionen"}. Alle tider er dansk tid.</p>
    <div class="stats">
      <div class="stat"><b>{len(rows)}</b><span>trades</span></div>
      <div class="stat"><b class="{"pos" if tot > 0 else "neg"}">{tot:+.2f}R</b><span>i alt</span></div>
      <div class="stat"><b class="{"pos" if totf > 0 else "neg"}">{totf:+.2f}R</b><span>med fuld TP</span></div>
      <div class="stat"><b>{win:.0%}</b><span>vundne</span></div>
      <div class="stat"><b>{(tot / len(rows) if rows else 0):+.2f}R</b><span>pr. trade</span></div>
      <div class="stat"><b>{dd:.2f}R</b><span>største drawdown</span></div>
    </div>
  </header>
  <section><h2>Samlet R</h2><div class="eq">{equity(rows) if rows else ''}</div></section>
  {variant_html(rows, partial)}
  {f'<section><h2>Pr. måned</h2><div class="tablewrap"><table style="min-width:0"><thead><tr><th>Måned</th><th class="num">Trades</th><th class="num">Vundne</th><th class="num">R</th></tr></thead><tbody>{mrows}</tbody></table></div></section>' if len(mdr) > 1 else ''}
  <section><h2>Alle trades</h2>
    <div class="filters" role="group" aria-label="Filter"><button aria-pressed="true" data-f="alle">Alle</button><button aria-pressed="false" data-f="long">Long</button><button aria-pressed="false" data-f="short">Short</button></div>
    <div class="tablewrap"><table><thead><tr><th>#</th><th>Entry DK</th><th>Retning</th><th>Sweep</th><th>TF</th><th class="num">Entry</th><th class="num">SL</th><th>TP</th><th class="num">RR</th><th>Udfald</th><th class="num">R</th><th class="num" title="Hold til start-TP eller SL, ingen ny TP og ingen lukning 22:55">R fuld TP</th><th class="num" title="TP = naermeste af session-liq og 3. uberoerte 4h-liq, uden partial">R 3·4h</th></tr></thead><tbody>{trs}</tbody></table></div>
  </section>
  <section><h2>Reglerne</h2><div class="rules">
    <div class="rule"><b>Liq</b>Asia (02:00–08:00 DK), London (08:00–14:00 DK), PDH/PDL, gårsdagens sessions og 4h-candles en uge tilbage. Et niveau kan kun sweepes én gang.</div>
    <div class="rule"><b>Benet og gaps</b>De to nyeste 5m gaps i benet, lavet til og med sweep-candlen. Et gap, der blev inverseret før sweepet, tæller ikke.</div>
    <div class="rule"><b>Sweep</b>Sweep af liq og en 5m close tilbage over niveauet. Tager prisen et session-niveau på den anden side før entry, er setuppet dødt. Ingen entry inden for 2 timer: setuppet dør, men benet lever.</div>
    <div class="rule"><b>Entry</b>Reaktionen skal ind i begge 5m gaps. Signal på close mindst 1 point forbi det ældste gap i reaktionen (1–5m, højeste timeframe vinder). {("Entry med limit " + f"{gp:.3f}".replace(".", ",") + " af vejen fra signalet mod SL. Fyldes den ikke, eller når prisen TP først, er der intet trade.") if gp else "Entry på signalet."} SL på toppen af reaktionen.</div>
    <div class="rule"><b>TP</b>Nærmeste uberørte session/PDH/PDL mindst 1R væk. Ellers den nærmeste gamle session, der ikke er taget, uanset hvor langt tilbage. {"Ellers 4h, og" if h4 else "Ellers,"} på ATH 4R. En session, der bliver færdig under tradet og ligger tættere, bliver ny TP.</div>
    <div class="rule"><b>Styring</b>{"25% ud på high/low af en 4h-candle, der lukker under tradet." if partial else "Hele positionen går til TP, ingen partial."} Alt lukkes 22:55 DK.</div>
  </div></section>
  {f'<section><h2>Hvert trade</h2>{cards}</section>' if med_chart else f'<p class="muted">Over {MAX_CHARTS} trades, så der er ingen charts pr. trade. Kør en kortere periode for at se dem.</p>'}
</div>
<script>
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.filters button').forEach(x => x.setAttribute('aria-pressed', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('tr[data-side], article[data-side]').forEach(el => el.hidden = f !== 'alle' && el.dataset.side !== f);
}}));
</script>'''
    return stil + body
