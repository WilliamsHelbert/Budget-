# -*- coding: utf-8 -*-
import json
P=json.load(open('/tmp/parts2.json'))
H = """<title>Long mod short</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=JetBrains+Mono:wght@400;500;700&display=swap">
<style>%(css)s</style>

<div class="wrap">

<header class="mast">
  <div class="col">
    <span class="eyebrow">EQ-konfluens · NQ · 1. jan – 11. sep 2026</span>
    <h1>Long mod short</h1>
    <p class="standfirst">Modellen har ikke én kant der svinger op og ned. Den har en side der tjener og en side der taber. Her er begge vinduer, måned for måned, med hver eneste handel.</p>
  </div>
  <div class="runmeta col" style="max-width:none">
    <div><dt>Data</dt><dd>NinjaTrader ticks</dd></div>
    <div><dt>Handelsdage</dt><dd>181</dd></div>
    <div><dt>Asset</dt><dd>NQ-benet alene</dd></div>
    <div><dt>Dagsregler</dt><dd>−2,5 / +3,75 R</dd></div>
    <div><dt>Tid</dt><dd>dansk (CPH)</dd></div>
  </div>
</header>

<section>
  <div class="verdict col" style="max-width:none">
    <div class="hl">Longs tabte penge i begge vinduer, i fuld periode og out-of-sample. Fire målinger, fire minusser.</div>
    <p>Shorts tjente i alle fire. Det er ikke et parameter fundet ved at lede i en tabel — det er ét stykke information, bekræftet på tværs af to vinduer og to regelsæt, og det holder når man fjerner den måned modellen blev bygget på.</p>
    <p>Tabellerne herunder viser hvad hver side bidrog med hver måned, og hvad der sker når man lader det ene signal spærre for det andet.</p>
    <div class="fourm">
      <div><div class="v neg">−17,75</div><div class="l">kun longs · 15:30–16:00</div></div>
      <div><div class="v neg">−35,52</div><div class="l">kun longs · 15:30–16:30</div></div>
      <div><div class="v pos">+38,50</div><div class="l">kun shorts · 15:30–16:00</div></div>
      <div><div class="v pos">+59,50</div><div class="l">kun shorts · 15:30–16:30</div></div>
    </div>
  </div>
</section>

<section>
  <div class="sechead"><h2>De tre måder at handle den på</h2></div>
  <p class="lede"><b>Normal</b> tager begge sider. <b>Variant A</b> tager kun shorts, men lader long-signalerne spærre pladsen og tælle med i dagsbudgettet — du ser dem, du tager dem ikke, men du holder dig i ro imens. <b>Variant B</b> lader som om longs ikke findes.</p>
  <h3 style="margin:26px 0 10px">Vindue 15:30–16:00</h3>
  <div class="vgrid">%(k1600)s</div>
  <h3 style="margin:30px 0 10px">Vindue 15:30–16:30</h3>
  <div class="vgrid">%(k1630)s</div>
</section>

<section>
  <div class="sechead"><h2>Måned for måned</h2><span class="eyebrow">15:30–16:00</span></div>
  <p class="lede">Kolonnen <b>Netto R</b> er den normale model med begge sider. De næste par er hvad henholdsvis longs og shorts bidrog med <em>inden i</em> den kørsel. Yderst står variant B, hvor shorts kører alene.</p>
  <div class="tblwrap"><table class="mtab">%(MTH)s<tbody>%(m1600)s</tbody></table></div>

  <div class="sechead" style="margin-top:44px"><h2>Måned for måned</h2><span class="eyebrow">15:30–16:30</span></div>
  <div class="tblwrap"><table class="mtab">%(MTH)s<tbody>%(m1630)s</tbody></table></div>
</section>

<section>
  <div class="sechead"><h2>Hvad spærringen gør</h2></div>
  <p class="lede">Læg mærke til at longs inde i den normale kørsel kun taber <b>−7,20 R</b> (kort vindue) og <b>−7,05 R</b> (langt). Men når longs kører alene, uden shorts til at optage pladsen, taber de <b>−17,75</b> og <b>−35,52</b>.</p>
  <p class="lede">Det går begge veje. Shorts alene giver +38,50 i det korte vindue. Shorts <em>med</em> longs som spærring giver +52,73 — på 16 handler færre. De handler der forsvinder, er tilsammen −14,23 R.</p>
  <p class="note">Et long-signal er ikke bare værdiløst. Det er en advarsel. Når modellen peger op, virker shorts heller ikke — så den rigtige reaktion er at holde sig helt væk, ikke at vende den om.</p>
</section>

<section>
  <div class="sechead"><h2>Alle handler · 15:30–16:00</h2><span class="eyebrow">116 handler</span></div>
  <div class="legend">
    <span><i class="sw2" style="background:var(--tintl)"></i> long</span>
    <span><i class="sw2" style="background:var(--tints)"></i> short</span>
    <span><span class="chip r-tp">TP</span> ramte målet</span>
    <span><span class="chip r-sl">SL</span> ramte stoppet</span>
    <span><span class="chip r-be">BE</span> stoppet var flyttet til indgang</span>
    <span><i class="bedot"></i> break-even nået</span>
  </div>
  <div class="tblwrap"><table class="bog">%(TH)s%(l1600)s</table></div>
</section>

<section>
  <div class="sechead"><h2>Alle handler · 15:30–16:30</h2><span class="eyebrow">226 handler</span></div>
  <div class="tblwrap"><table class="bog">%(TH)s%(l1630)s</table></div>
</section>

<section>
  <div class="sechead"><h2>Forbehold</h2></div>
  <ul class="plain">
    <li><b>Jeg har kigget på otte celler og peger på den bedste.</b> Det er samme fremgangsmåde der gav anbefalingen om 16:30, som jeg måtte trække tilbage. Selve fundet — at longs taber — er stærkere, fordi det er ét bit information bekræftet fire gange, ikke et tal valgt fra en tabel.</li>
    <li><b>t = +1,84 er ikke bevis.</b> Det betyder «sandsynligvis ikke tilfældigt», ikke «det virker». 57 handler er stadig få.</li>
    <li><b>Januar taber i hver eneste variant</b>, og september er svagt negativ i begge short-varianter. Kurven stiger ikke jævnt.</li>
    <li><b>Ét år, ét marked.</b> 2026 var et stigende år for NQ. At shorts i åbningstimen tjente penge i et stigende marked kan være mean reversion — eller det kan være dette ene år.</li>
    <li><b>ES er stadig nødvendig.</b> Signalet kræver at begge assets holder en EQ og bekræfter samme vej. Du handler kun NQ, men du kan ikke slukke for ES-dataen.</li>
  </ul>
</section>

<footer>
  15-sekunders barer bygget fra NinjaTrader Last-ticks via Tradovate, 1. januar – 11. september 2026, volumenrullet mellem kvartalskontrakter. 11. juni udeladt på grund af manglende ES-barer. Motoren kører i New York-tid så åbningen altid rammer 09:30 ET; alle klokkeslæt vises i dansk tid. Konfirmation 15 s, stop på EQ-anchoren, mål 75 point, break-even fra forrige 5-minutters ekstrem, loft på stop og BE ved 40 point.
</footer>

</div>
""" % dict(css=P['css'], k1600=P['k1600'], k1630=P['k1630'], m1600=P['m1600'],
           m1630=P['m1630'], l1600=P['l1600'], l1630=P['l1630'], TH=P['TH'], MTH=P['MTH'])
open('/tmp/claude-0/-home-user-Budget-/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/scratchpad/long_mod_short.html','w').write(H)
print("skrevet", len(H))
