# -*- coding: utf-8 -*-
import sys, os, math, numpy as np, pandas as pd, importlib
ENG = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ENG)
SP = os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)

def go(frm, to, day, base=SP+"/vendata"):
    import model; importlib.reload(model)
    model.BASE = base; model.TZ = "America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=frm, entry_to=to, **day, **CFG)
    return df[df.day != "2026-06-11"]

def stat(g, col='R'):
    x = g[col].values
    if len(x) < 2: return (len(x), 0,0,0,0,float('nan'))
    e = np.cumsum(x)
    return (len(x), x.sum(), x.mean(), (e-np.maximum.accumulate(e)).min(),
            (x>0).mean()*100, x.mean()*math.sqrt(len(x))/x.std())

DAYS = [("dagsregler -2,5/+3,75", dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')),
        ("ingen dagsregler",      dict(daily_stop=None, daily_target=None, daily_basis='NQ'))]
WINS = [("09:30-10:00", 9*60+30, 10*60), ("10:00-10:30", 10*60, 10*60+30),
        ("09:30-10:30", 9*60+30, 10*60+30)]
print("HELE PERIODEN 1. jan - 11. sep 2026 (ekskl. 11. juni)\n")
for dl, dk in DAYS:
    print("--- %s ---" % dl)
    print("%-12s %-4s %5s %9s %9s %9s %7s %7s" % ("vindue","ass","n","R","pr.handel","maxDD","vind%","t"))
    for wl, a, b in WINS:
        df = go(a, b, dk)
        for k in ("NQ","ES"):
            n,R,pr,dd,w,t = stat(df[df.asset==k])
            print("%-12s %-4s %5d %+9.2f %+9.2f %+9.2f %6.1f%% %+7.2f" % (wl,k,n,R,pr,dd,w,t))
        p = df.groupby('id').R.sum().reset_index()
        n,R,pr,dd,w,t = stat(p)
        print("%-12s %-4s %5d %+9.2f %+9.2f %+9.2f %6.1f%% %+7.2f" % (wl,"par",n,R,pr,dd,w,t))
    print()
