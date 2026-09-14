# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
def go(a,b,**extra):
    import model; importlib.reload(model)
    model.BASE=SP+"/vendata"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=a, entry_to=b, daily_basis='NQ', **CFG, **extra)
    return df[(df.asset=='NQ') & (df.day!="2026-06-11")].copy()

def stat(g, lbl):
    r=g.sort_values('id').R.values; e=np.cumsum(r)
    t=r.mean()*math.sqrt(len(r))/r.std() if len(r)>1 and r.std()>0 else float('nan')
    print("%-26s n %4d | R %+7.2f | pr.h %+5.2f | maxDD %+7.2f | vind%% %4.1f | TP %2d SL %2d BE %2d | t %+5.2f"
          % (lbl, len(r), r.sum(), r.mean(), (e-np.maximum.accumulate(e)).min(), (r>0.005).mean()*100,
             (g.reason=='TP').sum(), (g.reason=='SL').sum(), (g.reason=='BE').sum(), t))
    o=g[g.day<"2026-08-12"]; ro=o.R.values
    if len(ro)>1:
        print("   heraf out-of-sample: n %3d | R %+7.2f | pr.h %+5.2f | t %+5.2f" %
              (len(ro), ro.sum(), ro.mean(), ro.mean()*math.sqrt(len(ro))/ro.std() if ro.std()>0 else float('nan')))

for wl,a,b in [("15:30-16:00",9*60+30,10*60), ("15:30-16:30",9*60+30,10*60+30)]:
    print("\n=== %s ===" % wl)
    stat(go(a,b, daily_stop=-5.0, daily_target=7.5), "-5 / +7,5 (helt ben)")
    stat(go(a,b, daily_stop=-2.5, daily_target=3.75), "-2,5 / +3,75 (halveret)")
