"""HTML-rapport for TJR 4-step: noegletal, tabel og et 1m-chart pr. trade med step 1-4 markeret."""
import html, sys, os
import pandas as pd
import tjr

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--line:#e3e1db;--card:#fff;--up:#1f8a5b;--dn:#c8433a;
--tp:rgba(31,138,91,.13);--sl:rgba(200,67,58,.13);--lv:#3b6fd6;--s2:#9a5bd6;--s3:#d68a1f;--s4:#1d1d1b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;--mut:#9b9a94;--line:#33322f;
--card:#1e1e1c;--up:#3fbf86;--dn:#ef6a5f;--tp:rgba(63,191,134,.16);--sl:rgba(239,106,95,.16);--lv:#79a1f2;--s2:#c08cf0;--s3:#f0b25a;--s4:#ecebe6}}
:root[data-theme=dark]{--bg:#161615;--fg:#ecebe6;--mut:#9b9a94;--line:#33322f;--card:#1e1e1c;--up:#3fbf86;--dn:#ef6a5f;
--tp:rgba(63,191,134,.16);--sl:rgba(239,106,95,.16);--lv:#79a1f2;--s2:#c08cf0;--s3:#f0b25a;--s4:#ecebe6}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:24px 16px}
main{max-width:860px;margin:auto}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.mut{color:var(--mut)}.kpi{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.kpi div{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:110px}
.kpi b{display:block;font-size:18px}table{border-collapse:collapse;width:100%;font-size:12.5px}
.tw{overflow-x:auto}th,td{padding:4px 6px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.w{color:var(--up)}.l{color:var(--dn)}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:14px 0}
.card h3{margin:0 0 6px;font-size:15px}.card ul{margin:6px 0 0;padding-left:18px;font-size:12.5px}
svg{width:100%;height:auto;display:block}.c-up{fill:var(--up);stroke:var(--up)}.c-dn{fill:var(--dn);stroke:var(--dn)}
.zone-tp{fill:var(--tp)}.zone-sl{fill:var(--sl)}.ax{fill:var(--mut);font-size:10px}
"""


def n(v):
    return "" if v is None or pd.isna(v) else f"{v:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def chart(r, d):
    lv = r["_lv"]; ts = r["_ts"]; long = r["retning"] == "long"
    ex = r.get("_exit_ts_A")
    ex = ex if isinstance(ex, pd.Timestamp) else ts + pd.Timedelta(minutes=20)
    s0 = min(lv["sweep"][1], lv["s2"][0]) - pd.Timedelta(minutes=15)
    s0 = max(s0, ts - pd.Timedelta(hours=4))
    s1 = min(max(ex + pd.Timedelta(minutes=10), ts + pd.Timedelta(minutes=30)), ts + pd.Timedelta(hours=3))
    span = s1 - s0
    mins = 1 if span <= pd.Timedelta(minutes=150) else (2 if span <= pd.Timedelta(minutes=300) else 3)
    b = tjr.bars(d[(d.index >= s0) & (d.index < s1)], mins)
    W, H, L, R, T, B = 820, 380, 6, 70, 10, 22
    tp = r["tp_A"] if not pd.isna(r["tp_A"]) else None
    ps = [b.low.min(), b.high.max(), r["sl"], lv["sweep"][2]] + ([tp] if tp else [])
    lo, hi = min(ps), max(ps); pad = (hi - lo) * .04; lo -= pad; hi += pad
    y = lambda p: T + (hi - p) / (hi - lo) * (H - T - B)
    nb = len(b); cw = (W - L - R) / nb
    x0 = b.index[0]
    xt = lambda t: L + cw * ((t - x0) / pd.Timedelta(minutes=mins))
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="chart {r["dato"]} {r["entry_tid"]}">']
    xe0, xe1 = xt(ts), xt(ex)
    if tp:
        o.append(f'<rect class="zone-tp" x="{xe0:.1f}" y="{min(y(tp), y(r["entry"])):.1f}" width="{max(xe1 - xe0, 2):.1f}" height="{abs(y(tp) - y(r["entry"])):.1f}"/>')
    o.append(f'<rect class="zone-sl" x="{xe0:.1f}" y="{min(y(r["sl"]), y(r["entry"])):.1f}" width="{max(xe1 - xe0, 2):.1f}" height="{abs(y(r["sl"]) - y(r["entry"])):.1f}"/>')
    for i, (t, q) in enumerate(b.iterrows()):
        cx = L + cw * (i + .5); cls = "c-up" if q.close >= q.open else "c-dn"
        o.append(f'<line class="{cls}" x1="{cx:.1f}" x2="{cx:.1f}" y1="{y(q.high):.1f}" y2="{y(q.low):.1f}" stroke-width="1"/>')
        top, bot = y(max(q.open, q.close)), y(min(q.open, q.close))
        o.append(f'<rect class="{cls}" x="{cx - cw * .35:.1f}" y="{top:.1f}" width="{cw * .7:.1f}" height="{max(bot - top, .8):.1f}"/>')

    def hline(t0, t1, p, var, lab, dash=""):
        a, z = max(xt(t0), L), min(xt(t1), W - R)
        o.append(f'<line x1="{a:.1f}" x2="{z:.1f}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="var(--{var})" stroke-width="1.4" {dash}/>')
        o.append(f'<text x="{z + 3:.1f}" y="{y(p) + 3:.1f}" fill="var(--{var})" font-size="10">{html.escape(lab)}</text>')
    sw = lv["sweep"]
    hline(max(sw[0], s0), sw[1] + pd.Timedelta(minutes=1), sw[2], "lv", "1 liq", 'stroke-dasharray="4 3"')
    hline(lv["s2"][0], lv["s2"][1], lv["s2"][2], "s2", "2 5m BOS")
    s3 = lv["s3"]
    if s3[4] == "fvg":
        a = xt(s3[0]); z = xt(s3[1])
        o.append(f'<rect x="{a:.1f}" y="{y(s3[3]):.1f}" width="{max(z - a, 2):.1f}" height="{max(y(s3[2]) - y(s3[3]), 1):.1f}" fill="var(--s3)" opacity=".35"/>')
        o.append(f'<text x="{z + 3:.1f}" y="{y(s3[2]) + 3:.1f}" fill="var(--s3)" font-size="10">3 iFVG</text>')
    else:
        hline(s3[0], s3[1], s3[2], "s3", "3 1m BOS")
    hline(lv["s4"][0], lv["s4"][1], lv["s4"][2], "s4", "4 entry-BOS")
    hline(ts, ex, r["entry"], "mut", f"entry {n(r['entry'])}")
    hline(ts, ex, r["sl"], "dn", f"SL {n(r['sl'])}")
    if tp:
        hline(ts, ex, tp, "up", f"TP {r['tp_A_navn']}")
    for k in range(0, nb, max(1, nb // 8)):
        o.append(f'<text class="ax" x="{L + cw * (k + .5):.1f}" y="{H - 6}" text-anchor="middle">{b.index[k]:%H:%M}</text>')
    o.append("</svg>")
    return "".join(o)


def stats(z):
    z = z.dropna()
    if not len(z):
        return dict(n=0, win=0, sum=0, avg=0, dd=0)
    eq = z.cumsum(); dd = (eq - eq.cummax()).min()
    return dict(n=len(z), win=round((z > 0).mean() * 100, 1), sum=round(z.sum(), 2), avg=round(z.mean(), 2), dd=round(dd, 2))


def main(ud, titel):
    df = pd.read_pickle(os.path.join(ud, "trades.pkl"))
    d = tjr.load(df.dato.min(), df.dato.max())
    sa, sb = stats(df.R_A), stats(df.R_B)
    out = [f"<!doctype html><html lang=da><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>TJR 4-step backtest</title><style>{CSS}</style><main><h1>{html.escape(titel)}</h1>"
           f"<p class=mut>NQ, entry 09:30–12:00 NY, market på close af 1m-BOS. SL på nærmeste ubrudte 1m swing. "
           f"Hvis det er samme 15s-bar, rammer SL før TP. {len(df)} setups fandt step 4.</p>"]
    for tag, s, txt in (("A", sa, "TP = nærmeste liq. Er den under 0,9R, springes tradet over."),
                        ("B", sb, "TP = nærmeste liq, der er mindst 0,9R væk.")):
        out.append(f"<h2>Regel {tag}</h2><p class=mut>{txt}</p><div class=kpi>"
                   f"<div>Trades<b>{s['n']}</b></div><div>Win %<b>{s['win']}</b></div><div>Sum R<b>{n(s['sum'])}</b></div>"
                   f"<div>Snit R<b>{n(s['avg'])}</b></div><div>Max DD<b>{n(s['dd'])} R</b></div></div>")
    out.append("<h2>Alle setups</h2><div class=tw><table><tr><th>Dato</th><th>Retn.</th><th>Entry</th><th>Risk</th>"
               "<th>Sweep</th><th>Step 3</th><th>TP (A)</th><th>RR</th><th>Exit A</th><th>R A</th><th>R B</th></tr>")
    for _, r in df.iterrows():
        cls = "" if pd.isna(r.R_A) else ("w" if r.R_A > 0 else "l")
        out.append(f"<tr><td><a href='#t{_}'>{r.dato}</a></td><td>{r.retning}</td><td>{r.entry_tid}</td><td>{n(r.risk)}</td>"
                   f"<td>{html.escape(str(r.sweep).split(' ', 1)[1])}</td><td>{'iFVG' if 'FVG' in str(r.step3) else 'BOS'}</td>"
                   f"<td>{html.escape(str(r.tp_A_navn))}</td><td>{n(r.rr_A)}</td><td>{html.escape(str(r.exit_A) if not pd.isna(r.exit_A) else '')}</td>"
                   f"<td class={cls}>{n(r.R_A)}</td><td>{n(r.R_B)}</td></tr>")
    out.append("</table></div><h2>Trades</h2>")
    for i, r in df.iterrows():
        res = "" if pd.isna(r.R_A) else f" · {n(r.R_A)} R"
        out.append(f"<div class=card id=t{i}><h3>{r.dato} {r.retning} {r.entry_tid}{res}</h3>{chart(r, d)}<ul>"
                   f"<li>Step 1: {html.escape(str(r.sweep))}</li><li>Step 2: {html.escape(str(r.step2))}</li>"
                   f"<li>Step 3: {html.escape(str(r.step3))}</li><li>Step 4: {html.escape(str(r.step4))}</li>"
                   f"<li>Entry {n(r.entry)}, SL {n(r.sl)} (swing {r.sl_swing}), risk {n(r.risk)}</li>"
                   f"<li>TP A: {html.escape(str(r.tp_A_navn))} {n(r.tp_A)} ({n(r.rr_A)}R) → {html.escape(str(r.exit_A))}</li>"
                   f"<li>TP B: {html.escape(str(r.tp_B_navn))} {n(r.tp_B)} ({n(r.rr_B)}R) → {html.escape(str(r.exit_B))}</li></ul></div>")
    out.append("</main>")
    open(os.path.join(ud, "rapport.html"), "w").write("".join(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "TJR 4-step")
