"""Bygger artifact-versionen med kun de trades, motor og William er uenige om (enige og ikke-tjekkede fjernes)."""
import json, sys
skab, data, ud = sys.argv[1:4]
s = open(skab).read()
d = json.load(open(data))
# marker motor-trades, som dagsreglen (maks 2, stop efter win) ville skaere vaek
dag = {}
for t in d["trades"]:
    if t["model"] == "William":
        continue
    n, vundet = dag.get(t["dato"], (0, False))
    t["efter_regel"] = n >= 2 or vundet
    dag[t["dato"]] = (n + 1, vundet or (t["R"] or 0) > 0)
d["trades"] = [t for t in d["trades"] if t["journal"] in ("kun_motor", "kun_william")]
dage = {t["dato"] for t in d["trades"]}
d["bars"] = {k: v for k, v in d["bars"].items() if k in dage}
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
rep('t.journal==="kun_motor" ? ` · <b class="l">ikke i din journal</b>`', 't.journal==="kun_motor" ? ` · <b class="l">ikke i din journal</b>${t.efter_regel?" · <b>efter dagsregel</b>":""}`')
rep(" · maks 2 trades om dagen, stop efter en vinder", "")
rep("<title>TJR Trade Journal NQ</title>", "<title>TJR Uenige Trades</title>")
rep("<h1>TJR Trade Journal · NQ</h1>", "<h1>TJR · uenige trades</h1>")
s = s.replace('__DATA__', json.dumps(d, separators=(",", ":")))
open(ud, "w").write(s)
print(len(d["trades"]), sum(t["journal"] == "kun_motor" for t in d["trades"]), sum(t["journal"] == "kun_william" for t in d["trades"]))
