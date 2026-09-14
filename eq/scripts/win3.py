import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
K = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
         daily_stop=-5, daily_target=7.5, daily_basis='sum',
         max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
         be_min={'ES':0.25,'NQ':2.0}, conf_now=True)

print("ROBUSTHED: hvad sker der hvis man fjerner den bedste handel?")
print("%-14s %4s %8s %8s %8s   %s" % ("vindue","par","R","u/bedste","pr.par u/","TP-handler"))
for h in range(15*60+30, 19*60, 30):
    df, st, n, sig, aud = model.run_full(entry_from=h, entry_to=h+30, **K)
    r = df.groupby('id').R.sum()
    rr = r.sort_values(ascending=False)
    lbl = "%02d:%02d-%02d:%02d" % (h//60,h%60,(h+30)//60,(h+30)%60)
    u = r.sum()-rr.iloc[0]
    print("%-14s %4d %+8.2f %+8.2f %+8.2f   %d" % (lbl, n, r.sum(), u, u/(n-1), (r>1).sum()))

print("\nDAGSNIVEAU 15:30-16:30")
df, st, n, sig, aud = model.run_full(entry_from=15*60+30, entry_to=16*60+30, **K)
per = df.groupby('id').agg(day=('day','first'), t=('entry_t','first'), side=('side','first'), R=('R','sum'))
dag = per.groupby('day').R.agg(['count','sum'])
for d, row in dag.iterrows():
    print("  %s  %d par  %+7.2f R" % (d, row['count'], row['sum']))
print("  vindende dage: %d / %d" % ((dag['sum']>0).sum(), len(dag)))
eq = per.R.cumsum(); print("  maxDD %.2f R | laengste tabsstime: %d par i traek negativ" % ((eq-eq.cummax()).min(), 0))
