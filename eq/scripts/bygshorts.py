# -*- coding: utf-8 -*-
import json
P=json.load(open('/tmp/shortsparts.json'))
def dk(x,n=2):
    return ("%+.*f"%(n,x)).replace('.',',').replace('-',"−")
H = """<title>Shortbogen 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>
:root{
  color-scheme:light;
  --ground:#eceeed; --surface:#fbfcfb; --surface-2:#f2f4f3;
  --ink:#13181b; --ink-2:#3c484f; --muted:#6c787f; --rule:#d2d8d7; --rule-strong:#b6bfbe;
  --short:#c9501f; --es:#2a78d6; --pos:#17724a; --neg:#a83a30; --flat:#8a9499;
  --shadow:0 1px 2px rgba(19,24,27,.06), 0 8px 24px -16px rgba(19,24,27,.28);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  color-scheme:dark;
  --ground:#0e1214; --surface:#161b1e; --surface-2:#1c2225;
  --ink:#e5e9e8; --ink-2:#a9b5bb; --muted:#7d8a91; --rule:#242c30; --rule-strong:#333e43;
  --short:#e4713c; --es:#3987e5; --pos:#38a877; --neg:#e07068; --flat:#6d7a80;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
}}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#0e1214; --surface:#161b1e; --surface-2:#1c2225;
  --ink:#e5e9e8; --ink-2:#a9b5bb; --muted:#7d8a91; --rule:#242c30; --rule-strong:#333e43;
  --short:#e4713c; --es:#3987e5; --pos:#38a877; --neg:#e07068; --flat:#6d7a80;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -16px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{margin:0; background:var(--ground); color:var(--ink);
  font-family:"Source Serif 4",Georgia,serif; font-size:17px; line-height:1.6;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:900px; margin:0 auto; padding-inline:20px; padding-block:0 72px}
h1{font-family:Archivo,"Helvetica Neue",Arial,sans-serif; font-size:clamp(1.9rem,5.5vw,2.9rem);
  line-height:1.05; font-weight:700; letter-spacing:-.028em; margin:0; text-wrap:balance}
h2{font-family:Archivo,sans-serif; font-size:1.15rem; font-weight:600; letter-spacing:-.012em; margin:0}
.eyebrow{font-family:"JetBrains Mono",ui-monospace,monospace; font-size:.66rem; font-weight:500;
  letter-spacing:.17em; text-transform:uppercase; color:var(--muted)}
.mono{font-family:"JetBrains Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums}
.num{font-family:"JetBrains Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums; font-weight:500}
.pos{color:var(--pos)} .neg{color:var(--neg)} .flat{color:var(--flat)}

header{border-bottom:1px solid var(--rule-strong); padding-block:46px 0;
  display:flex; flex-direction:column; gap:14px}
.meta{display:flex; flex-wrap:wrap; border-top:1px solid var(--rule); margin-top:22px}
.meta div{flex:1 1 118px; padding:13px 16px 16px 0; border-right:1px solid var(--rule)}
.meta div:last-child{border-right:0}
.meta dt{font-family:"JetBrains Mono",monospace; font-size:.6rem; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); margin-bottom:5px}
.meta dd{margin:0; font-family:Archivo,sans-serif; font-weight:600; font-size:1rem; letter-spacing:-.01em}

section{padding-block:36px 0}
.sechead{display:flex; align-items:baseline; gap:12px; border-bottom:1px solid var(--rule);
  padding-bottom:8px; margin-bottom:0}
.sechead h2{flex:1}

.tblwrap{overflow-x:auto}
table{border-collapse:collapse; width:100%; font-size:.83rem}
table.mtab{min-width:520px}
table.bog{min-width:700px}
thead th{position:sticky; top:0; z-index:3; background:var(--ground);
  font-family:Archivo,sans-serif; font-weight:600; font-size:.62rem; letter-spacing:.08em;
  text-transform:uppercase; color:var(--muted); text-align:right; padding:11px 9px 9px;
  border-bottom:1px solid var(--rule-strong); white-space:nowrap}
table.bog thead th:nth-child(-n+3){text-align:left}
table.mtab thead th:first-child{text-align:left}
td{padding:9px; border-bottom:1px solid var(--rule); text-align:right;
  vertical-align:top; white-space:nowrap}
table.bog td:nth-child(-n+3){text-align:left}
td.sep, th.sep{border-left:1px solid var(--rule)}
td.mnd{text-align:left; font-family:Archivo,sans-serif; font-weight:600}
tr.sum td{border-top:2px solid var(--rule-strong); border-bottom:0;
  font-weight:700; background:var(--surface-2)}
td.big{font-size:1rem; font-weight:700}
tbody tr:not(.msep):hover{background:var(--surface-2)}

tr.msep td{padding:0; border-bottom:1px solid var(--rule-strong); background:var(--surface-2)}
.ms{display:flex; align-items:baseline; gap:13px; padding:14px 9px 11px; flex-wrap:wrap}
.mn{font-family:Archivo,sans-serif; font-weight:600; font-size:1.02rem; letter-spacing:-.01em}
.mm{font-family:"JetBrains Mono",monospace; font-size:.69rem; color:var(--muted)}
.mx{font-size:.69rem; color:var(--muted); flex:1}
.mt{font-size:1.12rem; font-weight:700; letter-spacing:-.02em}
.mt small{font-family:Archivo,sans-serif; font-weight:500; font-size:.6rem;
  color:var(--muted); margin-left:4px}

td.dd{font-weight:600}
td.tid{font-weight:700; font-size:.9rem}
.sw{display:block; font-family:"JetBrains Mono",monospace; font-size:.62rem;
  color:var(--muted); font-weight:400; margin-top:2px; letter-spacing:-.02em}
td.sd{color:var(--muted)}
td.udf{text-align:left}
.chip{display:inline-block; font-family:Archivo,sans-serif; font-size:.66rem; font-weight:600;
  padding:2px 7px 3px; border:1px solid currentColor; border-radius:2px; line-height:1.3}
.chip.t-nq{color:var(--short); border-style:dashed}
.chip.t-es{color:var(--es); border-style:dashed}
.chip.r-tp{color:var(--pos); background:color-mix(in srgb,var(--pos) 10%, transparent); border-color:transparent}
.chip.r-sl{color:var(--neg); background:color-mix(in srgb,var(--neg) 10%, transparent); border-color:transparent}
.chip.r-be{color:var(--flat); background:color-mix(in srgb,var(--flat) 14%, transparent); border-color:transparent}
.bedot{display:inline-block; width:5px; height:5px; border-radius:50%;
  background:var(--flat); margin-left:5px; vertical-align:middle}
footer{margin-top:44px; border-top:1px solid var(--rule); padding-top:16px;
  color:var(--muted); font-size:.78rem; font-family:Archivo,sans-serif}
@media (max-width:560px){ body{font-size:16px} .ms{gap:7px 11px} .mx{flex:1 1 100%; order:3} }
</style>

<div class="wrap">

<header>
  <span class="eyebrow">EQ-konfluens · kun shorts · NQ</span>
  <h1>Shortbogen 2026</h1>
  <div class="meta">
    <div><dt>Periode</dt><dd>1. jan – 11. sep</dd></div>
    <div><dt>Vindue</dt><dd>15:30–16:30</dd></div>
    <div><dt>Handler</dt><dd>@@N@@</dd></div>
    <div><dt>Handelsdage</dt><dd>@@DAGE@@</dd></div>
    <div><dt>Resultat</dt><dd class="pos">@@TOT@@ R</dd></div>
  </div>
</header>

<section>
  <div class="sechead"><h2>Måned for måned</h2></div>
  <div class="tblwrap">
    <table class="mtab">
      <thead><tr><th>Måned</th><th>Handler</th><th>Dage</th>
        <th class="sep">TP</th><th>SL</th><th>BE</th><th>R</th></tr></thead>
      <tbody>@@MROWS@@</tbody>
    </table>
  </div>
</section>

<section>
  <div class="sechead"><h2>Alle handler</h2><span class="eyebrow">@@N@@ shorts</span></div>
  <div class="tblwrap">
    <table class="bog">
      <thead><tr>
        <th>Dato</th><th>Entry</th><th>Sweep</th>
        <th>Indgang</th><th>Stop</th><th>Stop pts</th><th>Mål</th>
        <th>Udfald</th><th>R</th>
      </tr></thead>
@@BODY@@
    </table>
  </div>
</section>

<footer>
  1 R = 10 NQ-point · mål 75 point · stop på EQ-anchoren · dagsstop &minus;2,5 R / dagsmål +3,75 R ·
  longs spærrer pladsen men handles ikke · 15s-barer fra NinjaTrader-ticks · 11. juni udeladt
</footer>

</div>
"""
for a,b in (("@@BODY@@",P['body']), ("@@MROWS@@",P['mrows']),
            ("@@N@@",str(P['n'])), ("@@DAGE@@",str(P['dage'])), ("@@TOT@@",dk(P['tot']))):
    H = H.replace(a,b)
open('/tmp/claude-0/-home-user-Budget-/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/scratchpad/shortbogen.html','w').write(H)
print("skrevet", len(H))
