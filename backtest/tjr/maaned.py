"""Simpel maanedstabel: motor (med dagsregel) vs Williams journal, med forklaring af forskellen. Brug: maaned.py 2026-01 ud.html"""
import sys, pandas as pd, match
mdr, ud = sys.argv[1], sys.argv[2]
GRUND = {("2026-01-08", "16:55"): "Motoren stopper efter win 15:55 (dagsregel)",
         ("2026-01-20", "16:55"): "Ugyldig nu: du var i shorten (reverse-idé)",
         ("2026-01-21", "16:05"): "NY PRE 5m-swing uden 15m (idé til senere)"}
m = pd.read_pickle('/mnt/project-files/backtest/tjr/jan-mar2026/trades.pkl')
m = m[(m.dato.str[:7] == mdr) & (m.status != 'skip')].reset_index(drop=True)
w = match.load_j(); w = w[w.dato.str[:7] == mdr].reset_index(drop=True)
if "tilfoejet" not in w: w["tilfoejet"] = False
w["tilfoejet"] = w.tilfoejet.fillna(False).astype(bool)
par, used = match.match(m, w); pw = {i: j for i, j, _ in par}; pm = {j: i for i, j, _ in par}
dk = lambda ts: ts.tz_convert('Europe/Copenhagen').strftime('%H:%M')
rows = []
for dato in sorted(set(m.dato) | set(w.dato)):
    for j, r in m[m.dato == dato].iterrows():
        q = w.loc[pm[j]] if j in pm else None
        why = "Tilføjet: gyldig ifølge dig, ikke handlet" if q is not None and q.tilfoejet else ("" if q is not None else "Ikke gennemgået")
        rows.append(dict(dato=dato, t=dk(r['_ts']), ret=r.retning, mod=r.model, mR=r.R, wt=q.entry if q is not None else '',
                         wR=float(q.r) if q is not None else None, s='enig' if q is not None else 'motor', why=why))
    for i, q in w[w.dato == dato].iterrows():
        if i in pw: continue
        rows.append(dict(dato=dato, t=q.entry, ret=q.retning, mod='', mR=None, wt=q.entry, wR=float(q.r), s='william',
                         why=GRUND.get((dato, q.entry), "Ikke gennemgået")))
rows.sort(key=lambda x: (x['dato'], x['t']))
f = lambda v: '' if v is None else (('+' if v > 0 else '') + f'{v:.2f}'.replace('.', ','))
cls = lambda v: '' if v is None else ('w' if v > 0 else 'l' if v < 0 else '')
dage = ['man', 'tir', 'ons', 'tor', 'fre', 'lør', 'søn']
tr = []; prev = None
for x in rows:
    d = pd.Timestamp(x['dato']); lab = f"{dage[d.dayofweek]} {d.day}/{d.month}" if x['dato'] != prev else ''
    prev = x['dato']
    st = {'enig': 'Enig', 'motor': 'Kun motor', 'william': 'Kun dig'}[x['s']]
    tr.append(f"<tr class='{x['s']}{' ny' if lab else ''}'><td>{lab}</td><td>{x['t'] if x['s'] != 'william' else ''}</td><td>{x['wt']}</td><td>{x['ret']}</td><td>{x['mod']}</td><td class='{cls(x['mR'])} n'>{f(x['mR'])}</td><td class='{cls(x['wR'])} n'>{f(x['wR'])}</td><td><span class='tag {x['s']}'>{st}</span></td><td class='why'>{x['why']}</td></tr>")
mR = m.R.sum(); wR = w.r.sum(); ne = len(par)
eM = sum(m.loc[j, 'R'] for _, j, _ in par); eW = sum(w.loc[i, 'r'] for i, _, _ in par)
kM = m[~m.index.isin(used)].R.sum(); kW = w[~w.index.isin(pw)].r.sum()
ntil = int(w.tilfoejet.sum())
navn = {"01": "Januar", "02": "Februar", "03": "Marts"}[mdr[5:]]
H = f'''<!doctype html><html lang="da"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TJR {navn} Sammenligning</title><style>
:root{{--bg:#f6f5f1;--panel:#fff;--ink:#1b1b1a;--mut:#6b6a66;--line:#e3e1da;--up:#127a4a;--dn:#c0392b;--acc:#2f5bd3;--enz:#e9f5ee;--mz:#fdeeee;--wz:#eef2fd}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#151515;--panel:#1e1e1d;--ink:#ecebe6;--mut:#9a9893;--line:#33322f;--up:#3fbf7f;--dn:#ef6a5a;--acc:#7c9bff;--enz:#16291f;--mz:#2e1c1a;--wz:#1b2236}}}}
:root[data-theme="dark"]{{--bg:#151515;--panel:#1e1e1d;--ink:#ecebe6;--mut:#9a9893;--line:#33322f;--up:#3fbf7f;--dn:#ef6a5a;--acc:#7c9bff;--enz:#16291f;--mz:#2e1c1a;--wz:#1b2236}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:20px 16px 40px}} h1{{font-size:22px;margin:0 0 4px}} .sub{{color:var(--mut);margin:0 0 16px;font-size:13px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:16px}}
.k{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}} .k span{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut)}} .k b{{font:600 20px ui-monospace,Menlo,monospace}}
.wrap{{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%;min-width:640px}} th,td{{padding:6px 10px;text-align:left;white-space:nowrap}} th{{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut);border-bottom:1px solid var(--line)}}
tr.ny td{{border-top:1px solid var(--line)}} td.n{{font-family:ui-monospace,Menlo,monospace;text-align:right}} .w{{color:var(--up)}} .l{{color:var(--dn)}}
.tag{{font-size:11px;font-weight:600;padding:2px 7px;border-radius:999px}} .tag.enig{{background:var(--enz);color:var(--up)}} .tag.motor{{background:var(--mz);color:var(--dn)}} .tag.william{{background:var(--wz);color:var(--acc)}}
.forkl{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:16px}}.forkl h2{{font-size:15px;margin:0 0 8px}}
table.mini{{min-width:0}}table.mini td{{white-space:normal;padding:5px 8px;border-top:1px solid var(--line)}}table.mini tr:first-child td{{border-top:0}}table.mini .m{{color:var(--mut);font-size:12px}}table.mini tr.tot td{{font-weight:700}}
td.why{{white-space:normal;color:var(--mut);font-size:12px;min-width:180px}}
</style></head><body><main><h1>{navn} · motor vs. dig</h1><p class="sub">Motoren med dagsregel (maks 2 trades, stop efter win) · din journal med rettelser og de {ntil} motor-trades du har godkendt som gyldige · dansk tid · enig = samme retning inden for 10 min</p>
<div class="kpis"><div class="k"><span>Enige</span><b class="w">{ne}</b></div><div class="k"><span>Kun motor</span><b class="l">{len(m)-ne}</b></div><div class="k"><span>Kun dig</span><b>{len(w)-ne}</b></div>
<div class="k"><span>Motor R ({len(m)} trades)</span><b class="{cls(mR)}">{f(mR)}</b></div><div class="k"><span>Dit R ({len(w)} trades)</span><b class="{cls(wR)}">{f(wR)}</b></div><div class="k"><span>Forskel (dig − motor)</span><b class="{cls(wR-mR)}">{f(wR-mR)}</b></div></div>
<div class="forkl"><h2>Hvor kommer forskellen fra?</h2><table class="mini">
<tr><td>{ne} enige trades: dit R minus motorens ({f(eW)} mod {f(eM)})</td><td class="n {cls(eW-eM)}">{f(eW-eM)}R</td><td class="m">forskellig SL/TP/exit på samme trade</td></tr>
<tr><td>{len(m)-ne} trades kun motoren tager</td><td class="n {cls(-kM)}">{f(-kM) or '0,00'}R</td><td class="m">motorens {f(kM) or '0,00'}R, som du ikke har</td></tr>
<tr><td>{len(w)-ne} trades kun du tager</td><td class="n {cls(kW)}">{f(kW) or '0,00'}R</td><td class="m">dit R på trades motoren ikke tager</td></tr>
<tr class="tot"><td>I alt: dig {f(wR)} − motor {f(mR)}</td><td class="n {cls(wR-mR)}">{f(wR-mR)}R</td><td></td></tr></table></div>
<div class="wrap"><table><thead><tr><th>Dag</th><th>Motor</th><th>Dig</th><th>Retning</th><th>Model</th><th style="text-align:right">Motor R</th><th style="text-align:right">Dit R</th><th></th><th>Hvorfor</th></tr></thead><tbody>{''.join(tr)}</tbody></table></div></main></body></html>'''
open(ud, 'w').write(H)
print(navn, "enige", ne, "kun motor", len(m) - ne, "kun dig", len(w) - ne, "motor", round(mR, 2), "dig", round(wR, 2))
