import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
K = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
         daily_stop=-5, daily_target=7.5, daily_basis='sum',
         max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
         be_min={'ES':0.25,'NQ':2.0}, conf_now=True)

print("A) HVER HALVTIME FOR SIG (egen dag-stop/dag-maal)")
print("%-14s %4s %8s %8s %8s %8s %6s %6s" % ("vindue","par","R","pr.par","maxDD","sd","vind%","t"))
for h in range(15*60+30, 19*60, 30):
    df, st, n, sig, aud = model.run_full(entry_from=h, entry_to=h+30, **K)
    lbl = "%02d:%02d-%02d:%02d" % (h//60, h%60, (h+30)//60, (h+30)%60)
    if not len(df): print("%-14s %4d" % (lbl,0)); continue
    r = df.groupby('id').R.sum().sort_index(); eq = r.cumsum()
    dd = float((eq-eq.cummax()).min())
    t = r.mean()*np.sqrt(len(r))/r.std() if len(r)>1 and r.std()>0 else float('nan')
    print("%-14s %4d %+8.2f %+8.2f %+8.2f %8.2f %6.1f %+6.2f" %
          (lbl, n, r.sum(), r.mean(), dd, r.std(), (r>0).mean()*100, t))

print("\nB) EEN KOERSEL 15:30-19:00, opdelt paa entry-halvtime (samme dag-stop for alle)")
df, st, n, sig, aud = model.run_full(entry_from=15*60+30, entry_to=19*60, **K)
df['et'] = pd.to_datetime(df.entry_t)
df['hh'] = df.et.dt.hour*60 + (df.et.dt.minute//30)*30
per = df.groupby('id').agg(R=('R','sum'), hh=('hh','first'), day=('day','first'))
print("%-14s %4s %8s %8s %6s" % ("halvtime","par","R","pr.par","vind%"))
for hh, g in per.groupby('hh'):
    lbl = "%02d:%02d" % (hh//60, hh%60)
    print("%-14s %4d %+8.2f %+8.2f %6.1f" % (lbl, len(g), g.R.sum(), g.R.mean(), (g.R>0).mean()*100))
print("%-14s %4d %+8.2f %+8.2f %6.1f" % ("I ALT", len(per), per.R.sum(), per.R.mean(), (per.R>0).mean()*100))

print("\nC) 16:30-17:00 alene - alle par")
df2, st2, n2, sig2, aud2 = model.run_full(entry_from=16*60+30, entry_to=17*60, **K)
p2 = df2.groupby('id').agg(day=('day','first'), t=('entry_t','first'), side=('side','first'), R=('R','sum'))
for i, row in p2.iterrows():
    print("  %2d  %s  %-5s  %+7.2f R" % (i, row.t, row.side, row.R))
