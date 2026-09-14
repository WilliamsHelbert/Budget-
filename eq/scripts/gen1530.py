# -*- coding: utf-8 -*-
import json, math, datetime, statistics as st
D = json.load(open('/tmp/w1530.json'))
T = D['trades']; A = D['A']
MINUS = "−"
def dk(x, n=2, sign=True):
    if abs(x) < 0.005: return "0," + "0"*n
    s = ("%+.*f" if sign else "%.*f") % (n, x)
    return s.replace('.', ',').replace('-', MINUS)
def dkp(x, n=2): return dk(x, n, False)
def cls(x): return "pos" if x > 0.005 else ("neg" if x < -0.005 else "flat")

UGE = ["mandag","tirsdag","onsdag","torsdag","fredag","lørdag","søndag"]
MND = ["januar","februar","marts","april","maj","juni","juli","august","september","oktober","november","december"]
def dagnavn(s):
    d = datetime.date.fromisoformat(s)
    return "%s %d. %s" % (UGE[d.weekday()], d.day, MND[d.month-1])

dage = {}
for t in T: dage.setdefault(t['day'], []).append(t)
for k in dage: dage[k].sort(key=lambda x: x['entry_t'])

seq = [t['NQ']['R'] for t in sorted(T, key=lambda x: x['id'])]
eq = []; c = 0.0
for r in seq: c += r; eq.append(c)
seqr = [t['NQ']['Rr'] for t in sorted(T, key=lambda x: x['id'])]
tr = st.mean(seqr)*math.sqrt(len(seqr))/st.stdev(seqr)

W, H, PL, PR, PT, PB = 940, 250, 46, 14, 16, 30
lo = math.floor(min(0, min(eq))/10)*10; hi = math.ceil(max(eq)/10)*10
def X(i): return PL + (W-PL-PR) * i/(len(eq)-1)
def Y(v): return PT + (H-PT-PB) * (1 - (v-lo)/(hi-lo))
pts = " ".join("%.1f,%.1f" % (X(i), Y(v)) for i, v in enumerate(eq))
area = "M%.1f,%.1f L" % (X(0), Y(0)) + pts + " L%.1f,%.1f Z" % (X(len(eq)-1), Y(0))
grid = "".join('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--grid)" stroke-width="1"/>'
               '<text x="%.1f" y="%.1f" fill="var(--muted)" font-size="10.5" text-anchor="end" '
               'font-family="JetBrains Mono,monospace">%s</text>'
               % (PL, Y(v), W-PR, Y(v), PL-8, Y(v)+3.5, dk(v,0)) for v in range(int(lo), int(hi)+1, 10))
zero = '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--rule-strong)" stroke-width="1.25"/>' % (PL, Y(0), W-PR, Y(0))
marks = "".join('<circle cx="%.1f" cy="%.1f" r="2.4" fill="var(--nq)" opacity=".85"/>' % (X(i), Y(v))
                for i, v in enumerate(eq))
firstid = {}
for t in sorted(T, key=lambda x: x['id']): firstid.setdefault(t['day'], t['id'])
idx = {t['id']: i for i, t in enumerate(sorted(T, key=lambda x: x['id']))}
xlab = ""
for d in ["2026-08-12","2026-08-19","2026-08-26","2026-09-02","2026-09-09"]:
    if d in firstid:
        i = idx[firstid[d]]; dd = datetime.date.fromisoformat(d)
        xlab += ('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="var(--rule)" stroke-width="1"/>'
                 '<text x="%.1f" y="%.1f" fill="var(--muted)" font-size="10.5" text-anchor="middle" '
                 'font-family="JetBrains Mono,monospace">%d/%d</text>'
                 % (X(i), PT, X(i), H-PB, X(i), H-PB+14, dd.day, dd.month))
SVG = ('<svg viewBox="0 0 %d %d" width="100%%" role="img" aria-label="Akkumuleret R for NQ-benet over 39 handler">'
       '%s%s<path d="%s" fill="var(--nq)" opacity=".09"/>'
       '<polyline points="%s" fill="none" stroke="var(--nq)" stroke-width="2" '
       'stroke-linejoin="round" stroke-linecap="round"/>%s%s</svg>'
       % (W, H, grid, xlab, area, pts, zero, marks))

# ---------- én samlet tabel med dag-skillere ----------
body = ""
for day in sorted(dage):
    ts = dage[day]
    dR = sum(t['NQ']['R'] for t in ts); dRr = sum(t['NQ']['Rr'] for t in ts)
    body += ('<tbody class="dag">\n<tr class="daysep"><td colspan="12"><div class="dsep">'
             '<span class="dnavn">%s</span><span class="dmeta mono">%s &nbsp;·&nbsp; %d handler</span>'
             '<span class="dtot num %s">%s<small>R</small></span>'
             '<span class="dtot2 num %s">%s<small>R risiko</small></span></div></td></tr>\n'
             % (dagnavn(day), day, len(ts), cls(dR), dk(dR), cls(dRr), dk(dRr)))
    for t in ts:
        nq, es = t['NQ'], t['ES']
        body += ("""<tr>
<td class="tid mono">%s<span class="sw">sweep %s</span></td>
<td><span class="chip %s">%s</span></td>
<td><span class="chip trig %s">%s</span></td>
<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>
<td class="num sd">%s</td>
<td class="num">%s<span class="sw">%s</span></td>
<td class="udf"><span class="chip r-%s">%s</span>%s</td>
<td class="num big %s">%s</td>
<td class="num %s">%s</td>
<td class="num es %s">%s</td>
</tr>
""" % (t['entry_t'][11:16], t['hit_t'][11:19],
       "short" if t['side']=="SHORT" else "long", "Short" if t['side']=="SHORT" else "Long",
       t['trig'].lower(), t['trig'],
       dkp(nq['entry']), dkp(nq['stop']), dkp(nq['tp']), dkp(nq['sd']),
       dkp(nq['exit']), nq['exit_t'][11:16],
       nq['reason'].lower(), nq['reason'],
       '<span class="bedot" title="stop flyttet til break-even kl. %s"></span>' % nq['be_t'][11:16] if nq['be'] else '',
       cls(nq['R']), dk(nq['R']), cls(nq['Rr']), dk(nq['Rr']), cls(es['R']), dk(es['R'])))
    body += "</tbody>\n"

dagsum = {d: sum(t['NQ']['R'] for t in dage[d]) for d in dage}
vind = sum(1 for v in dagsum.values() if v > 0.005)
tab  = sum(1 for v in dagsum.values() if v < -0.005)
nul  = len(dagsum) - vind - tab

cmprows = ""
for c in D['cmp']:
    hl = ' class="hl"' if c['name'] == "15:30–16:30" else ''
    cmprows += ('<tr%s><td>%s</td><td class="num">%d</td><td class="num %s">%s</td>'
                '<td class="num %s">%s</td><td class="num neg">%s</td><td class="num">%s</td>'
                '<td class="num">%s</td></tr>'
                % (hl, c['name'], c['n'], cls(c['R']), dk(c['R']), cls(c['pr']), dk(c['pr']),
                   dk(c['dd']), dkp(c['win'],1)+"&thinsp;%", dk(c['t'])))

json.dump(dict(svg=SVG, body=body, cmprows=cmprows, vind=vind, tab=tab, nul=nul,
               tr=tr, ndage=len(dage), A=A), open('/tmp/parts.json','w'))
print("ok", len(dage), "dage,", len(T), "handler, t risiko %.2f" % tr)
