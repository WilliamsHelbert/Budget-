"""Beregner kendetegn for motorens trades, saa enige og kun-motor trades kan sammenlignes."""
import sys, pandas as pd, numpy as np, tjr, match
m = pd.read_pickle(sys.argv[1])
d = tjr.load("2026-01-02", "2026-03-31")
w = match.load_j(); mm = m[m.dato <= "2026-03-26"].copy()
par, used = match.match(mm, w)
mm["enig"] = mm.index.isin(used)
f = []
for j, r in mm.iterrows():
    lv = r["_lv"]; long = r.retning == "long"; ts = r["_ts"]
    liqp = lv["sweep"][2]; t1 = lv["sweep"][1]
    x = d[(d.index >= t1) & (d.index < ts)]
    ext = x.low.min() if long else x.high.max()           # ekstrem fra step 1 til entry
    # ekstrem til step 2 (4-step) / step 1 close (3-step)
    t2 = lv["s2"][1] if "s2" in lv else t1 + pd.Timedelta(minutes=5)
    x2 = d[(d.index >= t1) & (d.index < t2)]
    ext2 = (x2.low.min() if long else x2.high.max()) if len(x2) else np.nan
    x3 = d[(d.index >= t2) & (d.index < ts)]
    resweep = bool(len(x3)) and ((x3.low.min() < ext2) if long else (x3.high.max() > ext2))
    f.append(dict(idx=j, dist_liq=round(abs(r.entry - liqp), 2), dist_R=round(abs(r.entry - liqp) / r.risk, 2),
                  min_til_entry=round((ts - t1).total_seconds() / 60), resweep=resweep))
F = pd.DataFrame(f).set_index("idx"); mm = mm.join(F)
mm.to_pickle(sys.argv[2])
for col in ["dist_liq", "dist_R", "min_til_entry", "risk"]:
    print(col, "enig median", mm[mm.enig][col].median(), "| kun motor median", mm[~mm.enig][col].median())
print("resweep andel: enig", round(mm[mm.enig].resweep.mean(), 2), "kun motor", round(mm[~mm.enig].resweep.mean(), 2))
for th in [50, 75, 100, 150]:
    a = mm[mm.dist_liq > th]; print(f"dist>{th}: n={len(a)} enige={a.enig.sum()} sumR={a.R.sum():.1f}")
for th in [30, 45, 60, 90]:
    a = mm[mm.min_til_entry > th]; print(f"tid>{th}m: n={len(a)} enige={a.enig.sum()} sumR={a.R.sum():.1f}")
a = mm[mm.resweep]; print(f"resweep: n={len(a)} enige={a.enig.sum()} sumR={a.R.sum():.1f}")
