# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
            max_stop={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
            conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75,
            be_src='liq', liq_piv=0)
def go(folder, **extra):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **BASE, **extra)
    n = df[(df.asset=='NQ') & (df.side=='SHORT')].copy()
    n['mnd']=n.day.str[:7]
    return n.sort_values('id')
def st(g,lbl):
    if len(g)<2: return "%-32s n %3d"%(lbl,len(g))
    r=g.R.values; e=np.cumsum(r)
    return ("%-32s n %3d | R %+7.2f | pr.h %+5.2f | DD %+7.2f | TP %2d SL %3d BE %2d | t %+5.2f"
      % (lbl,len(r),r.sum(),r.mean(),(e-np.maximum.accumulate(e)).min(),
         (g.reason=='TP').sum(),(g.reason=='SL').sum(),(g.reason=='BE').sum(),
         r.mean()*math.sqrt(len(r))/r.std() if r.std()>0 else float('nan')))
VAR = [("RTH-niveauer  cap40", dict(liq_from=9*60+30, max_be={'ES':8,'NQ':40})),
       ("HELE DOEGN    cap40", dict(liq_from=0,       max_be={'ES':8,'NQ':40})),
       ("HELE DOEGN    cap60", dict(liq_from=0,       max_be={'ES':12,'NQ':60})),
       ("HELE DOEGN    cap75", dict(liq_from=0,       max_be={'ES':15,'NQ':75})),
       ("HELE DOEGN    ingen", dict(liq_from=0)),
       ("HELE DOEGN piv1 cap40",dict(liq_from=0, liq_piv=1, max_be={'ES':8,'NQ':40}))]
print("### nov 2024 - feb 2026, fuld doegndata fra Databento (341 dage)")
res={}
for vl, kw in VAR:
    n = go("dbfull", **kw); res[vl]=n
    print(st(n, vl), flush=True)
best = res["HELE DOEGN    cap40"]
best.to_csv(SP+"/eq_dbfull_cap40.csv", index=False)
res["RTH-niveauer  cap40"].to_csv(SP+"/eq_dbfull_rth_cap40.csv", index=False)
print("\n--- maaned for maaned, HELE DOEGN cap40 ---")
print(best.groupby('mnd').agg(n=('R','size'),R=('R','sum'),
    TP=('reason',lambda s:(s=='TP').sum()),SL=('reason',lambda s:(s=='SL').sum()),
    BE=('reason',lambda s:(s=='BE').sum())).round(2).to_string())
