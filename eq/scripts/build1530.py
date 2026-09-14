# -*- coding: utf-8 -*-
import json
P = json.load(open('/tmp/parts.json'))
A = P['A']; NQ = A['NQ']; ES = A['ES']
def dk(x,n=2,s=True):
    if abs(x) < 0.005: return "0," + "0"*n
    return (("%+.*f" if s else "%.*f") % (n,x)).replace('.',',').replace('-',"\u2212")

CSS = """
:root{
  color-scheme:light;
  --ground:#eceeed; --surface:#fbfcfb; --surface-2:#f3f5f4;
  --ink:#13181b; --ink-2:#3c484f; --muted:#6c787f; --rule:#d2d8d7; --rule-strong:#b6bfbe;
  --es:#2a78d6; --nq:#c9501f; --pos:#17724a; --neg:#a83a30; --flat:#8a9499;
  --grid:#dfe4e3; --hl:#fdf3ea;
  --shadow:0 1px 2px rgba(19,24,27,.06), 0 8px 24px -16px rgba(19,24,27,.28);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --ground:#0e1214; --surface:#161b1e; --surface-2:#1c2225;
    --ink:#e5e9e8; --ink-2:#a9b5bb; --muted:#7d8a91; --rule:#242c30; --rule-strong:#333e43;
    --es:#3987e5; --nq:#e4713c; --pos:#38a877; --neg:#e07068; --flat:#6d7a80;
    --grid:#222a2e; --hl:#241c16;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#0e1214; --surface:#161b1e; --surface-2:#1c2225;
  --ink:#e5e9e8; --ink-2:#a9b5bb; --muted:#7d8a91; --rule:#242c30; --rule-strong:#333e43;
  --es:#3987e5; --nq:#e4713c; --pos:#38a877; --neg:#e07068; --flat:#6d7a80;
  --grid:#222a2e; --hl:#241c16;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{margin:0; background:var(--ground); color:var(--ink);
  font-family:"Source Serif 4",Georgia,serif; font-size:17px; line-height:1.62;
  -webkit-font-smoothing:antialiased;}
.wrap{max-width:1060px; margin:0 auto; padding-inline:20px; padding-block:0 80px}
.col{max-width:680px}
h1,h2,h3,.ui{font-family:Archivo,"Helvetica Neue",Arial,sans-serif}
h1{font-size:clamp(2.1rem,6vw,3.5rem); line-height:1.02; font-weight:700; letter-spacing:-.028em; margin:0; text-wrap:balance}
h2{font-size:clamp(1.3rem,3.4vw,1.7rem); font-weight:600; letter-spacing:-.015em; line-height:1.15; margin:0; text-wrap:balance}
h3{font-size:1.02rem; font-weight:600; letter-spacing:-.005em; margin:0}
p{margin:0}
.eyebrow{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:.68rem; font-weight:500;
  letter-spacing:.17em; text-transform:uppercase; color:var(--muted)}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums}
.num{font-family:"JetBrains Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums; font-weight:500}
.pos{color:var(--pos)} .neg{color:var(--neg)} .flat{color:var(--flat)} .dim{color:var(--muted)}

header.mast{border-bottom:1px solid var(--rule-strong); padding-block:48px 0}
.mast .col{display:flex; flex-direction:column; gap:18px}
.standfirst{font-size:1.17rem; line-height:1.55; color:var(--ink-2); max-width:60ch}
.runmeta{display:flex; flex-wrap:wrap; border-top:1px solid var(--rule); margin-top:28px}
.runmeta div{flex:1 1 132px; padding:14px 16px 18px 0; border-right:1px solid var(--rule)}
.runmeta div:last-child{border-right:0}
.runmeta dt{font-family:"JetBrains Mono",monospace; font-size:.62rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); margin-bottom:5px}
.runmeta dd{margin:0; font-family:Archivo,sans-serif; font-weight:600; font-size:.98rem; letter-spacing:-.01em}

section{padding-block:38px 0}
.sechead{display:flex; align-items:baseline; gap:14px; border-bottom:1px solid var(--rule);
  padding-bottom:9px; margin-bottom:22px}
.sechead h2{flex:1}
.lede{max-width:62ch; color:var(--ink-2); margin-bottom:20px}
.lede+.lede{margin-top:-8px}

/* nøgletal */
.keys{display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:0;
  border:1px solid var(--rule); background:var(--surface); box-shadow:var(--shadow)}
.keys div{padding:20px 20px 22px; border-right:1px solid var(--rule); border-bottom:1px solid var(--rule)}
.keys .v{font-family:"JetBrains Mono",monospace; font-variant-numeric:tabular-nums;
  font-weight:700; font-size:1.65rem; letter-spacing:-.035em; line-height:1}
.keys .l{font-family:Archivo,sans-serif; font-size:.76rem; color:var(--muted); margin-top:7px; line-height:1.35}

/* handelsbog */
.tblwrap{overflow-x:auto; border-top:1px solid var(--rule-strong); margin-top:26px}
table.bog{border-collapse:collapse; width:100%; min-width:900px; font-size:.82rem}
table.bog thead th{position:sticky; top:0; z-index:3; background:var(--ground);
  font-family:Archivo,sans-serif; font-weight:600; font-size:.64rem; letter-spacing:.07em;
  text-transform:uppercase; color:var(--muted); text-align:right; padding:10px 9px 9px;
  border-bottom:1px solid var(--rule-strong); white-space:nowrap}
table.bog thead th:nth-child(-n+3){text-align:left}
table.bog td{padding:9px; border-bottom:1px solid var(--rule); text-align:right;
  vertical-align:top; white-space:nowrap}
table.bog td:nth-child(-n+3){text-align:left}
table.bog tbody tr:not(.daysep):hover{background:var(--surface-2)}
tr.daysep td{padding:0; border-bottom:1px solid var(--rule-strong); background:var(--surface-2)}
.dsep{display:flex; align-items:baseline; gap:12px; padding:13px 9px 10px; flex-wrap:wrap}
.dnavn{font-family:Archivo,sans-serif; font-weight:600; font-size:.98rem; letter-spacing:-.01em}
.dmeta{font-size:.7rem; color:var(--muted); flex:1}
.dtot{font-size:1.1rem; font-weight:700; letter-spacing:-.02em}
.dtot2{font-size:.84rem; opacity:.78}
.dtot small,.dtot2 small{font-family:Archivo,sans-serif; font-weight:500; font-size:.62rem;
  color:var(--muted); margin-left:4px; letter-spacing:0}
td.tid{font-weight:700; font-size:.92rem; font-variant-numeric:tabular-nums}
.sw{display:block; font-family:"JetBrains Mono",monospace; font-size:.63rem; color:var(--muted);
  font-weight:400; margin-top:2px; letter-spacing:-.02em}
td.sd{color:var(--muted)}
td.es{color:var(--muted); font-size:.76rem}
td.big{font-size:1rem; font-weight:700}
td.udf{text-align:left}

/* chart */
.chart{border:1px solid var(--rule); background:var(--surface); padding:14px 10px 6px; box-shadow:var(--shadow)}
.chart figcaption{font-family:Archivo,sans-serif; font-size:.76rem; color:var(--muted); padding:6px 10px 10px}

/* sammenligning */
table.cmp{border-collapse:collapse; width:100%; min-width:600px; font-size:.86rem}
table.cmp th{font-family:Archivo,sans-serif; font-weight:600; font-size:.64rem; letter-spacing:.07em;
  text-transform:uppercase; color:var(--muted); text-align:right; padding:10px 9px;
  border-bottom:1px solid var(--rule-strong); white-space:nowrap}
table.cmp td{padding:11px 9px; text-align:right; border-bottom:1px solid var(--rule); white-space:nowrap}
table.cmp th:first-child, table.cmp td:first-child{text-align:left; font-family:"JetBrains Mono",monospace}
table.cmp tr.hl{background:var(--hl)}
table.cmp tr.hl td{font-weight:700}
.cmpwrap{overflow-x:auto}

/* fordeling */
.split{display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:22px}
.panel{border:1px solid var(--rule); background:var(--surface); padding:20px 22px 22px; box-shadow:var(--shadow)}
.panel h3{margin-bottom:12px}
.kv{display:flex; justify-content:space-between; gap:14px; padding:6px 0; border-bottom:1px solid var(--rule); font-size:.88rem}
.kv:last-child{border-bottom:0}
.kv span:first-child{color:var(--ink-2)}

.bars{display:flex; flex-direction:column; gap:9px; margin-top:6px}
.bar{display:grid; grid-template-columns:52px 1fr 46px; align-items:center; gap:10px; font-size:.82rem}
.bar .track{height:9px; background:var(--surface-2); border:1px solid var(--rule)}
.bar .fill{height:100%}

.note{border-left:3px solid var(--rule-strong); padding:4px 0 4px 18px; color:var(--ink-2); max-width:62ch}
ul.plain{margin:0; padding-left:20px; max-width:62ch; color:var(--ink-2)}
ul.plain li{margin-bottom:9px}
footer{margin-top:52px; border-top:1px solid var(--rule); padding-top:18px; color:var(--muted); font-size:.82rem; max-width:70ch}
@media (max-width:560px){
  body{font-size:16px}
  .keys div{padding:16px 16px 18px}
  .dsep{gap:6px 12px}
  .dmeta{flex:1 1 100%; order:3}
}
"""

def bar(label, n, tot, col):
    return ('<div class="bar"><span class="mono dim">%s</span>'
            '<span class="track"><span class="fill" style="width:%.1f%%;background:%s"></span></span>'
            '<span class="num">%d</span></div>' % (label, 100.0*n/tot, col, n))

HTML = """<title>Den første time</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>%(css)s</style>

<div class="wrap">

<header class="mast">
  <div class="col">
    <span class="eyebrow">EQ-konfluens · NQ · 12. aug – 10. sep 2026</span>
    <h1>Den første time</h1>
    <p class="standfirst">Alle 39 handler modellen tog mellem 15:30 og 16:30, dag for dag. NQ-benet er det du handler; ES er der stadig, fordi signalet ikke findes uden det.</p>
  </div>
  <div class="runmeta col" style="max-width:none">
    <div><dt>Vindue</dt><dd>15:30–16:30 CPH</dd></div>
    <div><dt>Handler</dt><dd>%(n)d på %(nd)d dage</dd></div>
    <div><dt>Resultat NQ</dt><dd class="pos">%(R)s R</dd></div>
    <div><dt>Max drawdown</dt><dd class="neg">%(dd)s R</dd></div>
    <div><dt>Dagsregler</dt><dd>−2,5 / +3,75 R</dd></div>
  </div>
</header>

<section>
  <div class="keys">
    <div><div class="v pos">%(R)s</div><div class="l">R i alt på NQ-benet<br>(1 R = 10 point)</div></div>
    <div><div class="v pos">%(pr)s</div><div class="l">R pr. handel</div></div>
    <div><div class="v">%(win)s&thinsp;%%</div><div class="l">handler i plus<br>10 TP · 11 SL · 18 BE</div></div>
    <div><div class="v neg">%(dd)s</div><div class="l">max drawdown</div></div>
    <div><div class="v">%(t)s</div><div class="l">t-værdi<br>(%(tr)s risikonormeret)</div></div>
  </div>
</section>

<section>
  <div class="sechead"><h2>Kurven</h2><span class="eyebrow">akkumuleret R, NQ</span></div>
  <figure class="chart" style="margin:0">
    %(svg)s
    <figcaption>Hver prik er én handel. Største enkeltgevinst er %(best)s R, største enkelttab %(worst)s R — ingen enkelt handel bærer resultatet. Dybeste fald fra en top er %(dd)s R.</figcaption>
  </figure>
</section>

<section>
  <div class="sechead"><h2>Handelsbogen</h2><span class="eyebrow">%(nd)d dage · %(n)d handler</span></div>
  <p class="lede">Tiden yderst til venstre er <em>entry</em>; linjen under er det 15-sekunders sweep der udløste opsætningen. <strong>Sweep</strong>-mærket siger hvilket asset der raidede sin EQ — modellen tager handlen på begge, men her står NQ som hovedtal og ES-benet yderst til højre til sammenligning. Prikken ved udfaldet betyder at stoppet nåede at flytte til break-even.</p>
  <p class="lede"><span class="chip r-tp">TP</span> ramte målet · <span class="chip r-sl">SL</span> ramte det oprindelige stop · <span class="chip r-be">BE</span> stoppet var allerede flyttet til indgangen, så handlen gik i nul eller tæt på.</p>
  <div class="tblwrap">
  <table class="bog">
    <thead><tr>
      <th>Entry</th><th>Retning</th><th>Sweep</th>
      <th>Indgang</th><th>Stop</th><th>Mål</th><th>Stop pts</th>
      <th>Exit</th><th>Udfald</th><th>R</th><th>R risiko</th><th>ES-ben</th>
    </tr></thead>
%(rows)s  </table>
  </div>
</section>

<section>
  <div class="sechead"><h2>Hvordan det fordeler sig</h2></div>
  <div class="split">
    <div class="panel">
      <h3>Udfald</h3>
      <div class="bars">
        %(b1)s%(b2)s%(b3)s
      </div>
      <div class="kv" style="margin-top:16px"><span>Stoppet nåede break-even</span><span class="num">%(bem)d af %(n)d</span></div>
      <div class="kv"><span>Gennemsnitlig RR på målet</span><span class="num">3,26 : 1</span></div>
    </div>
    <div class="panel">
      <h3>Dage</h3>
      <div class="bars">
        %(d1)s%(d2)s%(d3)s
      </div>
      <div class="kv" style="margin-top:16px"><span>Største dagsgevinst</span><span class="num pos">+7,50 R</span></div>
      <div class="kv"><span>Største dagstab</span><span class="num neg">−3,88 R</span></div>
      <div class="kv"><span>Handler pr. dag</span><span class="num">1,8 i snit</span></div>
    </div>
    <div class="panel">
      <h3>Risiko pr. handel</h3>
      <div class="kv"><span>Mindste stop</span><span class="num">8,5 pts</span></div>
      <div class="kv"><span>Median</span><span class="num">26,5 pts</span></div>
      <div class="kv"><span>Største (loftet)</span><span class="num">40,0 pts</span></div>
      <div class="kv"><span>Målet er fast</span><span class="num">75 pts</span></div>
      <div class="kv"><span>Risikonormeret i alt</span><span class="num pos">+20,38 R</span></div>
      <div class="kv"><span>… pr. handel</span><span class="num pos">+0,52 R</span></div>
    </div>
  </div>
  <p class="note" style="margin-top:24px">De to R-tal er ikke det samme. <strong>R</strong> i tabellen er modellens faste enhed på 10 NQ-point, så «+7,50 R» betyder +75 point. <strong>R risiko</strong> måler mod det faktiske stop på den enkelte handel, og det er tallet du skal bruge til positionsstørrelse: største tab er præcis −1,00 og største gevinst +5,00.</p>
</section>

<section>
  <div class="sechead"><h2>Hvorfor lige det vindue</h2></div>
  <p class="lede">Samme model, samme regler, kun entry-vinduet ændret. NQ-benet alene:</p>
  <div class="cmpwrap">
    <table class="cmp">
      <thead><tr><th>Vindue</th><th>Handler</th><th>R</th><th>Pr. handel</th><th>Max DD</th><th>Vind%%</th><th>t</th></tr></thead>
      <tbody>%(cmp)s</tbody>
    </table>
  </div>
  <p class="lede" style="margin-top:22px">Kanten slukker klokken 16:30. Den halvtime efter er ikke bare svagere — den er nul, med dobbelt så stort drawdown. Og trækker man vinduet helt til 17:00 falder både resultat og R pr. handel.</p>
</section>

<section>
  <div class="sechead"><h2>Hvad tallene ikke siger</h2></div>
  <ul class="plain">
    <li><strong>Grænsen på 16:30 er fundet i de samme data.</strong> Jeg kiggede på syv halvtimer og valgte den der så bedst ud. Det er præcis den slags beslutning der holder på en backtest og falder fra hinanden live.</li>
    <li><strong>t = %(t)s på 39 handler er ikke bevis.</strong> Det er lige akkurat over den tommelfingerregel man plejer at bruge, og det er stadig kun fire ugers data.</li>
    <li><strong>ES kan ikke skæres væk.</strong> Modellen kræver at begge assets holder en EQ og bekræfter samme vej. Handler du kun NQ, tager du kun NQ-benet af signalet — men du skal stadig have ES-data i realtid.</li>
    <li><strong>Reglerne bag er også kalibreret på perioden</strong> — lofterne på stop og break-even, fødselsbar-reglen, rækkefølge-reglen på 15-sekunders barer. Out-of-sample data er det eneste der kan afgøre om det her holder.</li>
  </ul>
</section>

<footer>
  Kørt på 15-sekunders barer fra TradingView, 12. august – 10. september 2026, med 5-sekunders data brugt til at afgøre raid-rækkefølgen hvor de findes. Konfirmation 15 s, stop på EQ-anchoren, break-even fra forrige 5-minutters ekstrem, loft på stop og BE ved 40 NQ-point. Dagen lukker ved −2,5 R eller +3,75 R på NQ-benet.
</footer>

</div>
""" % dict(
  css=CSS, svg=P['svg'], rows=P['body'], cmp=P['cmprows'],
  n=NQ['n'], nd=P['ndage'], R=dk(NQ['R']), pr=dk(NQ['pr']), dd=dk(NQ['dd']),
  win=("%.1f"%NQ['win']).replace('.',','), t=dk(NQ['t']), tr=dk(P['tr']),
  best=dk(NQ['best']), worst=dk(NQ['worst']), bem=NQ['bemoved'],
  b1=bar("TP", NQ['TP'], NQ['n'], "var(--pos)"),
  b2=bar("BE", NQ['BE'], NQ['n'], "var(--flat)"),
  b3=bar("SL", NQ['SL'], NQ['n'], "var(--neg)"),
  d1=bar("plus", P['vind'], P['ndage'], "var(--pos)"),
  d2=bar("nul", P['nul'], P['ndage'], "var(--flat)"),
  d3=bar("minus", P['tab'], P['ndage'], "var(--neg)"),
)
# ryd op i chip-klassenavne (TP/SL/BE skrives med små bogstaver i klassen)
HTML = HTML.replace('class="chip r-TP"','class="chip r-tp"')
open('/tmp/claude-0/-home-user-Budget-/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/scratchpad/foerste_time.html','w').write(HTML)
print("skrevet", len(HTML), "bytes")
