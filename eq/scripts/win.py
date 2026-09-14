import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model

K = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
         daily_stop=-5, daily_target=7.5, daily_basis='sum',
         max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
         be_min={'ES':0.25,'NQ':2.0}, conf_now=True)

WINS = [
    ("15:30-16:00  (nuvaerende)", 15*60+30, 16*60),
    ("16:00-17:00", 16*60, 17*60),
    ("16:00-16:30", 16*60, 16*60+30),
    ("16:30-17:00", 16*60+30, 17*60),
    ("15:30-16:30", 15*60+30, 16*60+30),
    ("15:30-17:00", 15*60+30, 17*60),
]

def stats(df, n):
    if not len(df): return None
    out = {}
    out['pairs'] = n
    out['R'] = df.R.sum()
    out['perpair'] = df.R.sum()/n if n else 0
    for k in ('ES','NQ'):
        s = df[df.asset==k]
        out[k] = s.R.sum()
    r = df.groupby('id').R.sum().sort_index()
    eq = r.cumsum(); out['dd'] = float((eq - eq.cummax()).min()) if len(eq) else 0.0
    out['days'] = df.day.nunique()
    for rsn in ('TP','SL','BE','EOD'):
        out[rsn] = int((df.reason==rsn).sum())
    out['be_hit'] = int(df.moved_be.sum())
    # t-stat pr. par
    out['sd'] = float(r.std()) if len(r)>1 else float('nan')
    out['t'] = float(r.mean()*np.sqrt(len(r))/r.std()) if len(r)>1 and r.std()>0 else float('nan')
    out['win'] = float((r>0).mean()*100)
    return out

rows = []
store = {}
for name, a, b in WINS:
    df, st, n, sig, aud = model.run_full(entry_from=a, entry_to=b, **K)
    s = stats(df, n)
    store[name] = df
    rows.append((name, s))
    print(f"\n=== {name} ===")
    if s is None:
        print("  ingen handler"); continue
    print(f"  par {s['pairs']:3d} | R {s['R']:+7.2f} | pr.par {s['perpair']:+6.2f} | ES {s['ES']:+7.2f} NQ {s['NQ']:+7.2f}")
    print(f"  maxDD {s['dd']:+7.2f} | dage {s['days']:2d} | vind% {s['win']:5.1f} | sd {s['sd']:5.2f} | t {s['t']:+5.2f}")
    print(f"  TP {s['TP']:2d} SL {s['SL']:2d} BE {s['BE']:2d} EOD {s['EOD']:2d} | BE-flyt {s['be_hit']}/{len(df)}")

print("\n\n%-26s %4s %8s %8s %8s %8s %8s %6s %6s" % ("vindue","par","R","pr.par","ES","NQ","maxDD","vind%","t"))
for name, s in rows:
    if s is None:
        print("%-26s %4d" % (name,0)); continue
    print("%-26s %4d %+8.2f %+8.2f %+8.2f %+8.2f %+8.2f %6.1f %+6.2f" %
          (name, s['pairs'], s['R'], s['perpair'], s['ES'], s['NQ'], s['dd'], s['win'], s['t']))

import pickle
pickle.dump({k: v for k, v in store.items()}, open('/tmp/win_store.pkl','wb'))
