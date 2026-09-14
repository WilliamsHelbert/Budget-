"""Maximum favourable excursion: how far did each signal actually run
before the *initial* stop was hit? (no BE, no TP -> pure move measurement)"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M
import pandas as pd, numpy as np

C = M._data(60); BAR, TL, TOD = C["bar"], C["tl"], C["tod"]
sig = pd.read_csv(f"{M.BASE}/TRADES_allsignals.csv")
IDX = {k: {t: i for i, t in enumerate(TL)} for k in M.SYMS}
TS = {k: sorted(BAR[k].keys()) for k in M.SYMS}

def to_ts(s):
    return int(pd.Timestamp(s).tz_localize("Europe/Copenhagen").tz_convert("UTC").timestamp())

out = []
for _, r in sig.iterrows():
    k = r.asset; short = r.side == "SHORT"
    t0 = to_ts(r.entry_t); ent = r.entry; stop = r.stop
    mfe = 0.0; bars = 0; tp_hit = False
    for t in TL:
        if t <= t0: continue
        if TOD[t] >= M.CLOSE_MIN: break
        b = BAR[k].get(t)
        if b is None: continue
        o, h, l, c = b; bars += 1
        fav = (ent - l) if short else (h - ent)
        mfe = max(mfe, fav)
        if (h >= stop) if short else (l <= stop): break
    out.append(dict(id=r.id, asset=k, side=r.side, risk=r.stop_dist, mfe=round(mfe, 2),
                    mfe_R=round(mfe / M.R_UNIT[k], 2), bars=bars))
df = pd.DataFrame(out)
df.to_csv(f"{M.BASE}/mfe.csv", index=False)
for k in M.SYMS:
    s = df[df.asset == k]
    tgt = M.TP_PTS[k]
    print(f"== {k}  (target {tgt:g} pts = 7.5R)")
    print("   MFE before initial stop, points:", s.mfe.describe(percentiles=[.5,.75,.9,.95]).round(2).to_dict())
    for frac in (0.25, 0.5, 0.75, 1.0, 1.5):
        lvl = tgt * frac
        print(f"     reached {lvl:7.2f} pts ({frac*7.5:4.2f}R): {(s.mfe>=lvl).mean()*100:5.1f}%")
print()
print("== expectancy vs target size (initial stop, no BE), per signal ==")
for k in M.SYMS:
    s = df[df.asset == k]; ru = M.R_UNIT[k]
    print(f"  {k}: ", end="")
    for tgt in (5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150):
        if k == "ES" and tgt > 50: continue
        if k == "NQ" and tgt < 20: continue
        win = (s.mfe >= tgt)
        exp = (win * (tgt/ru) - (~win) * (s.risk/ru)).mean()
        print(f"{tgt}pt:{exp:+.2f}R ", end="")
    print()
