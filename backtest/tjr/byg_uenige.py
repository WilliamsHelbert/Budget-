"""Bygger artifact-versionen med kun de trades, motor og William er uenige om (enige og ikke-tjekkede fjernes)."""
import json, sys
skab, data, ud = sys.argv[1:4]
s = open(skab).read()
d = json.load(open(data))
n_enige = sum(t["journal"] == "enig" for t in d["trades"])
# marker motor-trades, som dagsreglen (maks 2, stop efter win) ville skaere vaek
dag = {}
for t in d["trades"]:
    if t["model"] == "William":
        continue
    n, vundet = dag.get(t["dato"], (0, False))
    t["efter_regel"] = n >= 2 or vundet
    dag[t["dato"]] = (n + 1, vundet or (t["R"] or 0) > 0)
# efter et win, vi er enige om, stopper vi begge for dagen: senere trades vises ikke
# ... og det samme efter 2 trades, vi er enige om
stop = {}; n_enig = {}
for t in sorted(d["trades"], key=lambda t: (t["dato"], t["entry_tid"])):
    if t["journal"] != "enig":
        continue
    n_enig[t["dato"]] = n_enig.get(t["dato"], 0) + 1
    if ((t["R"] or 0) > 0 and (t.get("w_R") or 0) > 0) or n_enig[t["dato"]] >= 2:
        stop[t["dato"]] = min(stop.get(t["dato"], "99:99"), t["entry_tid"])
d["trades"] = [t for t in d["trades"] if not (t["dato"] in stop and t["entry_tid"] > stop[t["dato"]])]
# dage William har gennemgaaet og bekraeftet, er loest og vises ikke
try:
    ok = set(json.load(open("/mnt/project-files/backtest/tjr/journal/bekraeftet.json"))["dage"])
except FileNotFoundError:
    ok = set()
d["trades"] = [t for t in d["trades"] if t["dato"] not in ok]
d["trades"] = [t for t in d["trades"] if t["journal"] in ("kun_motor", "kun_william")]
# min vurdering af hver uenig trade (fra vurdering.py)
try:
    V = json.load(open(data.replace("artifact_data.json", "vurdering.json")))
except FileNotFoundError:
    V = {}
for t in d["trades"]:
    t["vurdering_lang"] = V.get(f'{t["dato"]}|{t["retning"]}|{int(t["t_entry"])}|{"w" if t["model"] == "William" else "m"}', "")
dage = {t["dato"] for t in d["trades"]}
d["bars"] = {k: v for k, v in d["bars"].items() if k in dage}
KORT_M = [("du var selv i", "Du var i en anden trade"), ("allerede et win", "Du havde allerede et win"),
          ("2 trades den dag", "Du havde allerede 2 trades"), ("forkert side", "Entry på forkert side af liq"),
          ("gammelt", "Over 90 min fra step 1"), ("modsatte retning", "Du handlede modsat retning"),
          ("samme setup", "Samme setup, anden entry-swing")]
KORT_W = [("uden for vinduet", "Efter 18:00"), ("motoren var i en", "Motoren var i en anden trade"),
          ("venter på 1m entry-BOS", "Motoren fik ingen 1m entry-BOS"), ("venter på step 2", "Motoren fik ingen 5m step 2"),
          ("venter på pullback", "Motoren fik ingen pullback"), ("intet step 1", "Motoren fandt intet step 1")]
for t in d["trades"]:
    v = t.pop("vurdering_lang", "")
    k = KORT_W if t["model"] == "William" else KORT_M
    t["vurdering"] = next((n for key, n in k if key in v), "Ingen grund fundet, tjek chartet")
n_m = sum(t["journal"] == "kun_motor" for t in d["trades"]); n_w = sum(t["journal"] == "kun_william" for t in d["trades"])
def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
rep('''<button id="fj0" aria-pressed="true" data-v="">Alle motor</button><button id="fje" aria-pressed="false" data-v="enig">Enige</button>''',
    '''<button id="fj0" aria-pressed="true" data-v="">Begge</button>''')
rep('''(st.journal==="kun_william" ? t.journal==="kun_william" : t.journal!=="kun_william" && (!st.journal||t.journal===st.journal))''',
    '''(!st.journal||t.journal===st.journal)''')
rep('''<span class="lbl">Din journal</span>''', '''<span class="lbl">Uenige</span>''')
rep('''Backtest 2. jan – 31. mar 2026''', '''Kun de trades vi er uenige om, 2. jan – 26. mar 2026 · motoren uden dagsregel, så alle setups ses · nøgletal gælder de trades, filteret viser''')
rep('<b class="l">ikke i din journal</b>${', '<b class="l">ikke i din journal</b>${t.efter_regel?" · <b>efter dagsregel</b>":""}${')
rep(" · maks 2 trades om dagen, stop efter en vinder", "")
rep("Kun de trades vi er uenige om", f"Kun de trades vi er uenige om ({len(ok)} dage bekræftet og fjernet)")
rep("<title>TJR Trade Journal NQ</title>", "<title>TJR Uenige Trades</title>")
rep("<h1>TJR Trade Journal · NQ</h1>", "<h1>TJR · uenige trades</h1>")
rep('<p class="sub">', '<p class="sub" id="langsub" hidden>')
rep('<div class="eq"><div class="eqh">', '<div class="eq" hidden><div class="eqh">')
rep('<p class="note">', '<p class="note" hidden>')
rep('Motoren fandt ikke et setup i den retning inden for 10 min af din entry. Den lodrette linje er dit entry-tidspunkt.', 'Lodret linje = din entry.')
s = s.replace('<b>Min vurdering:</b> ', '<b>Grund:</b> ')
rep('${t.model==="William" ? "Motor samme dag: "+t.motor_dag : `${t.liq} · ${t.pullback_type} · TP ${t.tp_navn}`}${jtag(t)}', '${t.model==="William" ? "Kun dig · " : "Kun motor · "}${t.vurdering}')
rep('function kpis(){', f'''function kpis(){{
  $("#kpis").innerHTML=[["Enige",{n_enige},"w"],["Kun motor",{n_m},"l"],["Kun William",{n_w},""]].map(([n,v,c])=>`<div class="kpi"><span>${{n}}</span><b class="${{c}}">${{v}}</b></div>`).join("");
  return;''')
s = s.replace('__DATA__', json.dumps(d, separators=(",", ":")))
open(ud, "w").write(s)
print(len(d["trades"]), sum(t["journal"] == "kun_motor" for t in d["trades"]), sum(t["journal"] == "kun_william" for t in d["trades"]))

