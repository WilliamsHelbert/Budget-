import os
"""Matcher Williams journal (dansk tid) mod motorens trades (NY-tid)."""
import json, sys
import pandas as pd

J = "/mnt/project-files/backtest/tjr/journal/william_journal_jan-mar2026.json"
def load_j():
    w = pd.DataFrame(json.load(open(J)))
    w["ts"] = pd.to_datetime(w.date + " " + w.entry, format="%d-%m-%Y %H:%M").dt.tz_localize("Europe/Copenhagen").dt.tz_convert("America/New_York")
    w["dato"] = w.ts.dt.strftime("%Y-%m-%d"); w["ny"] = w.ts.dt.strftime("%H:%M"); w["retning"] = w.dir.str.lower()
    # trades William har slettet fra journalen (dato, dansk entry-tid, retning)
    try:
        ud = json.load(open(os.path.join(os.path.dirname(J), "fjernet.json")))["trades"]
    except FileNotFoundError:
        ud = []
    try:
        rr = json.load(open(os.path.join(os.path.dirname(J), "fjernet.json"))).get("ret_retning", [])
    except FileNotFoundError:
        rr = []
    for x in rr:
        m = (w.dato == x["dato"]) & (w.entry == x["dk"]) & (w.retning == x["fra"])
        w.loc[m, "retning"] = x["til"]
    fj = {(x["dato"], x["dk"], x["retning"]) for x in ud}
    w = w[[(d, e, r) not in fj for d, e, r in zip(w.dato, w.entry, w.retning)]].reset_index(drop=True)
    return w

def match(m, w, tol=10):
    m = m.copy(); m["ts"] = pd.to_datetime(m.dato + " " + m.entry_tid).dt.tz_localize("America/New_York")
    used = set(); par = []
    for i, r in w.iterrows():
        c = m[(m.dato == r.dato) & (m.retning == r.retning) & (~m.index.isin(used))]
        c = c.assign(diff=(c.ts - r.ts).abs().dt.total_seconds() / 60)
        c = c[c["diff"] <= tol].sort_values("diff")
        if len(c):
            used.add(c.index[0]); par.append((i, c.index[0], c["diff"].iloc[0]))
    return par, used
