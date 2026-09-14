"""Symmetric edge test: from each entry, does price reach +X before -X?
50% = no directional information in the signal."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M
import pandas as pd, numpy as np
C = M._data(60); BAR, TL, TOD = C["bar"], C["tl"], C["tod"]
sig = pd.read_csv(f"{M.BASE}/TRADES_allsignals.csv")
def to_ts(s): return int(pd.Timestamp(s).tz_localize("Europe/Copenhagen").tz_convert("UTC").timestamp())
X = {"ES": [2, 4, 6, 10, 15], "NQ": [10, 20, 30, 50, 75]}
res = {}
for _, r in sig.iterrows():
    k = r.asset; short = r.side == "SHORT"; ent = r.entry; t0 = to_ts(r.entry_t)
    done = {x: None for x in X[k]}
    for t in TL:
        if t <= t0: continue
        if TOD[t] >= M.CLOSE_MIN: break
        b = BAR[k].get(t)
        if b is None: continue
        o, h, l, c = b
        up, dn = h - ent, ent - l
        for x in X[k]:
            if done[x] is not None: continue
            fav, adv = (dn, up) if short else (up, dn)
            if fav >= x and adv >= x: done[x] = "both"      # same bar -> ambiguous
            elif fav >= x: done[x] = "win"
            elif adv >= x: done[x] = "loss"
        if all(v is not None for v in done.values()): break
    for x, v in done.items():
        res.setdefault((k, x), []).append(v)
print("Symmetric ±X test (50% = signal carries no directional information)")
for (k, x), v in sorted(res.items()):
    s = pd.Series(v)
    w, l, b, na = (s == "win").sum(), (s == "loss").sum(), (s == "both").sum(), s.isna().sum()
    tot = w + l
    print(f"  {k} ±{x:>3} pts:  hit-target-first {w/tot*100:5.1f}%   (win {w}, loss {l}, same-bar {b}, unresolved {na})")
