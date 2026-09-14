# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True, per_leg=True, one_at_a_time=True)

def go(**extra):
    import model; importlib.reload(model)
    model.BASE=SP+"/vendata"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG, **extra)
    return df[(df.asset=='NQ') & (df.day!="2026-06-11")].copy()

def stat(g, lbl):
    if len(g)<2: print("%-40s for faa handler (%d)"%(lbl,len(g))); return
    r=g.sort_values('id').R.values; e=np.cumsum(r)
    rr=(g.sort_values('id').pts/g.sort_values('id').stop_dist).values
    t=r.mean()*math.sqrt(len(r))/r.std() if r.std()>0 else float('nan')
    print("%-40s n %4d | R %+7.2f | pr.h %+5.2f | maxDD %+7.2f | vind%% %4.1f | TP %2d SL %2d BE %2d | t %+5.2f | Rrisk %+6.2f"
          % (lbl, len(r), r.sum(), r.mean(), (e-np.maximum.accumulate(e)).min(), (r>0.005).mean()*100,
             (g.reason=='TP').sum(), (g.reason=='SL').sum(), (g.reason=='BE').sum(), t, rr.sum()))
    o=g[g.day<"2026-08-12"]
    if len(o)>1:
        ro=o.R.values
        print("   heraf out-of-sample: n %3d | R %+7.2f | pr.h %+5.2f | t %+5.2f" %
              (len(ro), ro.sum(), ro.mean(), ro.mean()*math.sqrt(len(ro))/ro.std() if ro.std()>0 else float('nan')))

print("HELE 2026 (1. jan - 11. sep), NQ-benet alene, dagsregel PR. BEN\n")
stat(go(daily_stop=-2.5, daily_target=3.75), "A) faste taersk. -2,5/+3,75 (nuvaerende)")
stat(go(stop_after_decisive=True), "B) stop efter foerste afgoerende (TP/SL), BE tæller ikke")
stat(go(daily_stop=None, daily_target=None), "C) ingen dagsregel overhovedet")
