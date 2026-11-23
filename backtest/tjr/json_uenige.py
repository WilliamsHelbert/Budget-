"""Uenige trades (samme filter som uenige-artifacten) som JSON-pakke i Trade-indbakkens format.
Brug: json_uenige.py ud.json"""
import json, sys, subprocess, tempfile, datetime as dt
import match
ud = sys.argv[1]
tmp = tempfile.mkdtemp()
subprocess.run([sys.executable, "byg_uenige.py", "artifact_skabelon.html",
                "/mnt/project-files/backtest/tjr/jan-mar2026_alle/artifact_data.json", f"{tmp}/u.html", f"{tmp}/t.json"],
               check=True, stdout=subprocess.DEVNULL)
T = json.load(open(f"{tmp}/t.json"))
W = match.load_j()
wexit = {(r.dato, r.date and r.entry, r.retning): r.exit for r in W.itertuples()}
ud_tr = []
for t in sorted(T, key=lambda t: (t["dato"], t["entry_tid"])):
    y, mth, dd = t["dato"].split("-"); dato = f"{dd}-{mth}-{y}"
    if t["model"] == "William":
        ud_tr.append(dict(date=dato, entry=t["entry_tid"], exit=wexit.get((t["dato"], t["entry_tid"], t["retning"]), "") or "",
                          dir=t["retning"].capitalize(), type="TJR (din journal)", r=t["R"], match=True,
                          note=t["vurdering"], custom={"uenig": "Kun dig", "motor_samme_dag": t.get("motor_dag", "")}))
    else:
        ud_tr.append(dict(date=dato, entry=t["entry_tid"], exit=(t.get("exit") or "")[:5], dir=t["retning"].capitalize(),
                          type=f"TJR motor {t['model']}", r=t["R"], price=t["entry"], sl=t["sl"], tp=t["tp"], match=False,
                          note=t["vurdering"], custom={"uenig": "Kun motor", "liq": t["liq"], "tp_navn": t["tp_navn"],
                                                      "efter_dagsregel": bool(t.get("efter_regel"))}))
nm = sum(x["custom"]["uenig"] == "Kun motor" for x in ud_tr)
pk = dict(name="TJR · uenige trades feb–mar 2026", model="TJR model", source="NQ 15s-data", precision="præcis",
          thread="TJR Trading Model", createdAt=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          note=f"Kun de trades motor og William er uenige om ({nm} kun motor, {len(ud_tr)-nm} kun dig). Januar er gennemgået og ikke med. "
               "Motoren uden dagsregel. Kolonnen 'uenig' siger hvem der tog den, note = kort grund.",
          trades=ud_tr)
json.dump(pk, open(ud, "w"), ensure_ascii=False, indent=1)
print(len(ud_tr), nm, len(ud_tr) - nm)
