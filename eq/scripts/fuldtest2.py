# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
def go(**kw):
    import model; importlib.reload(model)
    model.BASE=SP+"/dbfull"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    base = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
                max_stop={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
                conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75,
                be_src='liq'); base.update(kw)
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **base)
    n = df[(df.asset=='NQ') & (df.side=='SHORT')].copy(); n['mnd']=n.day.str[:7]
    return n.sort_values('id')
def st(g,lbl):
    if len(g)<2: return "%-24s n %3d"%(lbl,len(g))
    r=g.R.values; e=np.cumsum(r)
    return ("%-24s n %3d | R %+7.2f | pr.h %+5.2f | DD %+7.2f | TP %2d SL %3d BE %2d | t %+5.2f"
      % (lbl,len(r),r.sum(),r.mean(),(e-np.maximum.accumulate(e)).min(),
         (g.reason=='TP').sum(),(g.reason=='SL').sum(),(g.reason=='BE').sum(),
         r.mean()*math.sqrt(len(r))/r.std() if r.std()>0 else float('nan')))
A = go(liq_piv=0, liq_from=9*60+30, max_be={'ES':8,'NQ':40})
B = go(liq_piv=0, liq_from=0,       max_be={'ES':8,'NQ':40})
C = go(liq_piv=1, liq_from=0,       max_be={'ES':8,'NQ':40})
D = go(liq_piv=0, liq_from=0,       max_be={'ES':6,'NQ':30})
E = go(liq_piv=0, liq_from=0,       max_be={'ES':4,'NQ':20})
for lbl, g in (("RTH cap40",A),("DOEGN cap40",B),("DOEGN piv1 cap40",C),
               ("DOEGN cap30",D),("DOEGN cap20",E)):
    print(st(g, lbl))
    for p, sel in (("2024-11..12", g.mnd<"2025-01"), ("2025", (g.mnd>="2025-01")&(g.mnd<"2026-01")),
                   ("2026-01..02", g.mnd>="2026-01")):
        print("     " + st(g[sel], "   "+p))
    print(flush=True)
B.to_csv(SP+"/eq_doegn_cap40.csv", index=False)
A.to_csv(SP+"/eq_rth_cap40.csv", index=False)
print("--- DOEGN cap40 maaned for maaned ---")
print(B.groupby('mnd').agg(n=('R','size'),R=('R','sum'),TP=('reason',lambda s:(s=='TP').sum()),
    SL=('reason',lambda s:(s=='SL').sum()),BE=('reason',lambda s:(s=='BE').sum())).round(2).to_string())
# hvilke handler kommer TIL naar natten taelles med?
ka = set(zip(A.day, A.entry_t)); kb = set(zip(B.day, B.entry_t))
ekstra = B[[k in (kb-ka) for k in zip(B.day,B.entry_t)]]
faldet  = A[[k in (ka-kb) for k in zip(A.day,A.entry_t)]]
print("\nhandler der KOMMER TIL med natteniveauer: %d, R %+.2f" % (len(ekstra), ekstra.R.sum()))
print("handler der FORSVINDER:                  %d, R %+.2f" % (len(faldet), faldet.R.sum()))
faelles = B[[k in (ka&kb) for k in zip(B.day,B.entry_t)]]
fa = A[[k in (ka&kb) for k in zip(A.day,A.entry_t)]]
print("faelles handler: %d | RTH R %+.2f -> DOEGN R %+.2f" % (len(faelles), fa.R.sum(), faelles.R.sum()))
