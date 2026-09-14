import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
SUM = dict(BASE, daily_stop=-5, daily_target=7.5, daily_basis='sum')

def leg(df, k):
    s = df[df.asset==k].sort_values('id')
    r = s.R.values
    eq = np.cumsum(r); dd = float((eq-np.maximum.accumulate(eq)).min()) if len(r) else 0
    t = r.mean()*np.sqrt(len(r))/r.std() if len(r)>1 and r.std()>0 else float('nan')
    best = r.max() if len(r) else 0
    return dict(n=len(r), R=r.sum(), pr=r.mean() if len(r) else 0, dd=dd,
                win=(r>0).mean()*100 if len(r) else 0, t=t,
                ub=r.sum()-best, TP=int((s.reason=='TP').sum()),
                SL=int((s.reason=='SL').sum()), BE=int((s.reason=='BE').sum()))

WINS = [("15:30-16:00",15*60+30,16*60), ("16:00-16:30",16*60,16*60+30),
        ("16:30-17:00",16*60+30,17*60), ("17:00-17:30",17*60,17*60+30),
        ("15:30-16:30",15*60+30,16*60+30), ("15:30-17:00",15*60+30,17*60)]

print("=== A) NUVAERENDE REGLER (dagsstop -5 / dagsmaal +7,5 paa BEGGE ben) ===")
print("%-13s %-3s %4s %8s %8s %8s %8s %6s %6s" % ("vindue","ass","n","R","pr.handel","u/bedste","maxDD","vind%","t"))
for name,a,b in WINS:
    df,_,n,_,_ = model.run_full(entry_from=a, entry_to=b, **SUM)
    for k in ("NQ","ES"):
        s = leg(df,k)
        print("%-13s %-3s %4d %+8.2f %+9.2f %+8.2f %+8.2f %6.1f %+6.2f" %
              (name,k,s['n'],s['R'],s['pr'],s['ub'],s['dd'],s['win'],s['t']))
    print()

print("=== B) KUN NQ - dagsstop/maal regnet paa NQ-benet alene ===")
for lbl, ds, dt in [("uaendret -5/+7,5", -5, 7.5), ("halveret -2,5/+3,75", -2.5, 3.75)]:
    print("\n-- %s --" % lbl)
    print("%-13s %4s %8s %8s %8s %8s %6s %6s  %s" % ("vindue","n","R","pr.handel","u/bedste","maxDD","vind%","t","TP/SL/BE"))
    for name,a,b in WINS:
        df,_,n,_,_ = model.run_full(entry_from=a, entry_to=b,
                                    daily_stop=ds, daily_target=dt, daily_basis='NQ', **BASE)
        s = leg(df,"NQ")
        print("%-13s %4d %+8.2f %+9.2f %+8.2f %+8.2f %6.1f %+6.2f  %d/%d/%d" %
              (name,s['n'],s['R'],s['pr'],s['ub'],s['dd'],s['win'],s['t'],s['TP'],s['SL'],s['BE']))
