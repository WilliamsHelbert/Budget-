"""Alle trades motor og William er enige om (motoren uden dagsregel) som JSON-pakke i Trade-indbakkens format.
Brug: json_enige.py ud.json"""
import json, sys, datetime as dt
import match
ud = sys.argv[1]
d = json.load(open("/mnt/project-files/backtest/tjr/jan-mar2026_alle/artifact_data.json"))
W = match.load_j()
wx = {(r.dato, r.entry, r.retning): r for r in W.itertuples()}
tr = []
for t in sorted((t for t in d["trades"] if t["journal"] == "enig"), key=lambda t: (t["dato"], t["entry_tid"])):
    y, m, dd = t["dato"].split("-")
    w = wx.get((t["dato"], t["w_tid"], t["retning"]))
    tr.append(dict(date=f"{dd}-{m}-{y}", entry=t["entry_tid"], exit=(t.get("exit") or "")[:5], dir=t["retning"].capitalize(),
                   type=f"TJR {t['model']}", r=t["R"],
                   note=f"{t['liq']} · {t['pullback_type']}",
                   custom={"Din entry": t["w_tid"], "Din exit": (getattr(w, "exit", "") or "") if w is not None else "",
                           "Dit R": t.get("w_R"), "Tilføjet af dig": bool(w is not None and getattr(w, "tilfoejet", False) is True),
                           "Taget?": "", "Hvorfor / hvorfor ikke": ""}))
mR = sum(x["r"] for x in tr); wR = sum(x["custom"]["Dit R"] or 0 for x in tr)
pk = dict(name="TJR · enige trades jan–mar 2026", model="TJR model", source="NQ 15s-data", precision="præcis",
          thread="TJR Trading Model", createdAt=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
          note=f"De {len(tr)} trades motor og William er enige om (samme retning inden for 10 min). r = motorens R ({mR:+.2f}), "
               f"'Dit R' = journalens R ({wR:+.2f}). Motoren uden dagsregel. Godkendte motor-trades tæller som journal-trades.",
          trades=tr)
json.dump(pk, open(ud, "w"), ensure_ascii=False, indent=1)
print(len(tr), round(mR, 2), round(wR, 2))
