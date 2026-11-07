"""Bygger artifact-versionen med kun de trades, motor og William er uenige om (enige og ikke-tjekkede fjernes)."""
import json, sys
skab, data, ud = sys.argv[1:4]
s = open(skab).read()
d = json.load(open(data))
# dage med uenighed: vis ALLE trades den dag (ogsaa dem vi er enige om), saa hele dagen kan ses
dage = {t["dato"] for t in d["trades"] if t["journal"] in ("kun_motor", "kun_william")}
d["trades"] = [t for t in d["trades"] if t["dato"] in dage and t["journal"] != "ikke_tjekket"]
d["bars"] = {k: v for k, v in d["bars"].items() if k in dage}
def rep(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
rep('''<button id="fj0" aria-pressed="true" data-v="">Alle motor</button><button id="fje" aria-pressed="false" data-v="enig">Enige</button>''',
    '''<button id="fj0" aria-pressed="true" data-v="">Hele dagen</button><button id="fje" aria-pressed="false" data-v="enig">Enige</button>''')
rep('''(st.journal==="kun_william" ? t.journal==="kun_william" : t.journal!=="kun_william" && (!st.journal||t.journal===st.journal))''',
    '''(!st.journal||t.journal===st.journal)''')
rep('''<span class="lbl">Din journal</span>''', '''<span class="lbl">Uenige</span>''')
rep('''Backtest 2. jan – 31. mar 2026''', '''Alle trades på de dage, hvor vi er uenige, 2. jan – 26. mar 2026 · nøgletal gælder de trades, filteret viser''')
rep("<title>TJR Trade Journal NQ</title>", "<title>TJR Uenige Trades</title>")
rep("<h1>TJR Trade Journal · NQ</h1>", "<h1>TJR · uenige trades</h1>")
s = s.replace('__DATA__', json.dumps(d, separators=(",", ":")))
open(ud, "w").write(s)
print(len(d["trades"]), sum(t["journal"] == "kun_motor" for t in d["trades"]), sum(t["journal"] == "kun_william" for t in d["trades"]))
