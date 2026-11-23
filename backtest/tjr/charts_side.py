"""Bygger artifact-siden med et chart + steps pr. trade (enige + uenige). Brug: charts_side.py ud_mappe"""
import json, sys, os, subprocess, tempfile, html
from charts import d, navn, tegn, step_felter
UD = sys.argv[1]; os.makedirs(f"{UD}/img", exist_ok=True)
tmp = tempfile.mkdtemp()
subprocess.run([sys.executable, "byg_uenige.py", "artifact_skabelon.html",
                "/mnt/project-files/backtest/tjr/jan-mar2026_alle/artifact_data.json", f"{tmp}/u.html", f"{tmp}/t.json"],
               check=True, stdout=subprocess.DEVNULL)
uenige = {navn(t) for t in json.load(open(f"{tmp}/t.json"))}
valg = [t for t in d["trades"] if t["journal"] == "enig" or navn(t) in uenige]
valg.sort(key=lambda t: (t["dato"], t["entry_tid"]))
kort = []
for t in valg:
    n = navn(t)
    if not os.path.exists(f"{UD}/img/{n}.png"):
        tegn(t, f"{UD}/img/{n}.png")
    tag = {"enig": "Enig", "kun_motor": "Kun motor", "kun_william": "Kun dig"}[t["journal"]]
    rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in step_felter(t).items())
    who = "din" if t["model"] == "William" else f"motor {t['model']}"
    kort.append(f'''<article id="{n}" data-g="{t['journal']}"><h2>{t['dato']} · {t['entry_tid']} · {who} {t['retning']} · <span class="r {'w' if (t['R'] or 0) > 0 else 'l'}">{(t['R'] or 0):+.2f}R</span> <span class="tag {t['journal']}">{tag}</span></h2>
<table>{rows}</table><img loading="lazy" src="img/{n}.png" alt="Chart {t['dato']} {t['entry_tid']}"></article>''')
H = '''<!doctype html><html lang="da"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TJR Trade Charts</title><style>
:root{--bg:#f6f5f1;--panel:#fff;--ink:#1b1b1a;--mut:#6b6a66;--line:#e3e1da;--up:#127a4a;--dn:#c0392b;--acc:#2f5bd3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151515;--panel:#1e1e1d;--ink:#ecebe6;--mut:#9a9893;--line:#33322f;--up:#3fbf7f;--dn:#ef6a5a;--acc:#7c9bff}}
:root[data-theme="dark"]{--bg:#151515;--panel:#1e1e1d;--ink:#ecebe6;--mut:#9a9893;--line:#33322f;--up:#3fbf7f;--dn:#ef6a5a;--acc:#7c9bff}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 40px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin:0 0 12px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px}nav button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:999px;padding:4px 12px;cursor:pointer;font:inherit;font-size:13px}nav button[aria-pressed=true]{background:var(--acc);color:#fff;border-color:var(--acc)}
article{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:14px}article h2{font-size:15px;margin:0 0 8px}
table{border-collapse:collapse;font-size:13px;margin-bottom:10px;width:100%}th{text-align:left;color:var(--mut);font-weight:500;padding:2px 12px 2px 0;white-space:nowrap;vertical-align:top;width:90px}td{padding:2px 0}
img{width:100%;height:auto;border-radius:6px;background:#fff}.w{color:var(--up)}.l{color:var(--dn)}
.tag{font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;margin-left:6px;border:1px solid var(--line)}.tag.enig{color:var(--up)}.tag.kun_motor{color:var(--dn)}.tag.kun_william{color:var(--acc)}
#alle{display:none;margin-bottom:12px}
</style></head><body><main><h1>TJR · charts pr. trade</h1>
<p class="sub">Alle steps markeret på chartet: 1 liq (sweep / 5m close), 2 5m BOS/iFVG (kun 4-step), pullback, entry. Stiplet gul = liq, prikket = entry/SL/TP, lodret prik = exit. Dansk tid.</p>
<a id="alle" href="#">← Vis alle trades</a>
<nav><button data-g="" aria-pressed="true">Alle (__N__)</button><button data-g="enig" aria-pressed="false">Enige</button><button data-g="kun_motor" aria-pressed="false">Kun motor</button><button data-g="kun_william" aria-pressed="false">Kun dig</button></nav>
__KORT__</main><script>
const A=[...document.querySelectorAll("article")],B=[...document.querySelectorAll("nav button")];
function vis(){const h=decodeURIComponent(location.hash.slice(1));const en=h&&document.getElementById(h);
 document.getElementById("alle").style.display=en?"inline-block":"none";document.querySelector("nav").style.display=en?"none":"flex";
 const g=(B.find(b=>b.getAttribute("aria-pressed")==="true")||B[0]).dataset.g;
 A.forEach(a=>a.hidden=en?a!==en:!!(g&&a.dataset.g!==g));if(en)window.scrollTo(0,0);}
B.forEach(b=>b.onclick=()=>{B.forEach(x=>x.setAttribute("aria-pressed",x===b));vis();});
window.addEventListener("hashchange",vis);vis();
</script></body></html>'''
open(f"{UD}/index.html", "w").write(H.replace("__KORT__", "\n".join(kort)).replace("__N__", str(len(kort))))
print(len(kort))
