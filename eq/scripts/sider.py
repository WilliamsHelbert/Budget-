# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
           conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75,
           be_src='liq', liq_piv=0, liq_from=0)
def go(folder, **kw):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG, **kw)
    n = df[df.asset=='NQ'].copy(); n['mnd']=n.day.str[:7]
    return n.sort_values('id')
def kom(folder_liste, **kw):
    dele=[]
    for f, fra in folder_liste:
        g = go(f, **kw)
        if fra: g = g[g.day >= fra]
        dele.append(g)
    return pd.concat(dele, ignore_index=True).sort_values(['day','entry_t']).reset_index(drop=True)
def st(g,lbl):
    if len(g)<2: return "%-30s n %3d"%(lbl,len(g))
    r=g.R.values; e=np.cumsum(r)
    return ("%-30s n %3d | R %+7.2f | pr.h %+5.2f | DD %+7.2f | vind%% %4.1f | TP %2d SL %3d BE %2d | t %+5.2f"
      % (lbl,len(r),r.sum(),r.mean(),(e-np.maximum.accumulate(e)).min(),(r>0.005).mean()*100,
         (g.reason=='TP').sum(),(g.reason=='SL').sum(),(g.reason=='BE').sum(),
         r.mean()*math.sqrt(len(r))/r.std() if r.std()>0 else float('nan')))
KILDER=[("dbfull",None),("vendata","2026-03-01")]
for lbl, kw in (("A: enhver aaben position blokerer", dict(block_mode="any")),
                ("B: kun MODSAT retning blokerer",   dict(block_mode="opposite"))):
    a = kom(KILDER, **kw)
    print("="*112); print("###", lbl)
    print(st(a[a.side=='SHORT'], "kun shorts"))
    print(st(a[a.side=='LONG'],  "kun longs"))
    print(st(a,                  "BEGGE SIDER samlet"))
    for p, sel in (("  2024 nov-dec", a.mnd<"2025-01"), ("  2025",(a.mnd>="2025-01")&(a.mnd<"2026-01")),
                   ("  2026 jan-sep", a.mnd>="2026-01")):
        print(st(a[sel], p))
    a.to_csv(SP+"/eq_sider_%s.csv" % kw["block_mode"], index=False)
    print(flush=True)
