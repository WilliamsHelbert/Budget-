# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
BASECFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
               max_stop={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
               conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75)
def go(folder, **extra):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **BASECFG, **extra)
    return df[df.asset=='NQ'].copy()
def st(g,lbl):
    if len(g)<2: return "%-30s n %3d"%(lbl,len(g))
    r=g.sort_values('id').R.values; e=np.cumsum(r)
    return ("%-30s n %3d | R %+7.2f | pr.h %+5.2f | DD %+7.2f | vind%% %4.1f | TP %2d SL %2d BE %2d | t %+5.2f"
      % (lbl,len(r),r.sum(),r.mean(),(e-np.maximum.accumulate(e)).min(),(r>0.005).mean()*100,
         (g.reason=='TP').sum(),(g.reason=='SL').sum(),(g.reason=='BE').sum(),
         r.mean()*math.sqrt(len(r))/r.std() if r.std()>0 else float('nan')))
VAR = [("GAMMEL prev5 cap40", dict(be_ref='prev', max_be={'ES':8,'NQ':40})),
       ("liq RTH cap40",      dict(be_src='liq', liq_piv=0, max_be={'ES':8,'NQ':40})),
       ("liq RTH cap75",      dict(be_src='liq', liq_piv=0, max_be={'ES':15,'NQ':75})),
       ("liq RTH ingen cap",  dict(be_src='liq', liq_piv=0)),
       ("liq HELE DOEGN cap40",dict(be_src='liq', liq_piv=0, liq_from=0, max_be={'ES':8,'NQ':40})),
       ("liq HELE DOEGN cap75",dict(be_src='liq', liq_piv=0, liq_from=0, max_be={'ES':15,'NQ':75})),
       ("liq HELE DOEGN ingen",dict(be_src='liq', liq_piv=0, liq_from=0)),
       ("liq RTH piv1 cap75", dict(be_src='liq', liq_piv=1, max_be={'ES':15,'NQ':75})),
       ("liq RTH piv1 ingen", dict(be_src='liq', liq_piv=1))]
print("### 2026 (vendata, fuld doegndata)")
for vl, kw in VAR:
    n = go("vendata", **kw); print(st(n[n.side=='SHORT'], vl+" short"), flush=True)
