# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True, daily_basis='NQ')
def go(a,b,**extra):
    import model; importlib.reload(model)
    model.BASE=SP+"/db2025"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=a, entry_to=b, **CFG, **extra)
    d = df[df.asset=='NQ'].copy()
    return d[(d.day>="2025-01-01")&(d.day<="2025-12-31")]     # rent 2025
def st(g,lbl):
    if len(g)<2: print("%-34s n %3d"%(lbl,len(g))); return
    r=g.sort_values('id').R.values; e=np.cumsum(r)
    print("%-34s n %4d | R %+7.2f | pr.h %+5.2f | maxDD %+7.2f | vind%% %4.1f | TP %2d SL %3d BE %3d | t %+5.2f"
      % (lbl,len(r),r.sum(),r.mean(),(e-np.maximum.accumulate(e)).min(),(r>0.005).mean()*100,
         (g.reason=='TP').sum(),(g.reason=='SL').sum(),(g.reason=='BE').sum(),
         r.mean()*math.sqrt(len(r))/r.std() if r.std()>0 else float('nan')))

D1=dict(daily_stop=-2.5, daily_target=3.75); D2=dict(daily_stop=-5.0, daily_target=7.5)
print("=== 2025 ALENE (rent out-of-sample, aldrig set foer) ===\n")
for wl,a,b in [("15:30-16:00",9*60+30,10*60), ("15:30-16:30",9*60+30,10*60+30)]:
    print("--- %s ---" % wl)
    n=go(a,b,**D1)
    st(n[n.side=='SHORT'], "  kun shorts (dagsr. -2,5/+3,75)")
    st(n[n.side=='LONG' ], "  kun longs")
    st(n,                  "  begge sider")
    n2=go(a,b,**D2)
    st(n2[n2.side=='SHORT'],"  kun shorts (dagsr. -5/+7,5)")
    n3=go(a,b,daily_stop=None,daily_target=None)
    st(n3[n3.side=='SHORT'],"  kun shorts (ingen dagsregel)")
    print()
# gem hovedkonfigurationen
best=go(9*60+30,10*60+30,**D1)
best[best.side=='SHORT'].to_csv('/tmp/y2025_shorts.csv',index=False)
print("gemt:", len(best[best.side=='SHORT']), "shorts")
