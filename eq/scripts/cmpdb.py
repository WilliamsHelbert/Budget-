# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True,
           daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
def go(base):
    import model; importlib.reload(model)
    model.BASE=base; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60+30, **CFG)
    return df[(df.asset=='NQ')&(df.side=='SHORT')].copy()
LO,HI="2026-01-01","2026-02-27"
a=go(SP+"/db2025"); a=a[(a.day>=LO)&(a.day<=HI)]
b=go(SP+"/vendata"); b=b[(b.day>=LO)&(b.day<=HI)]
print("Databento : %2d shorts  %+7.2f R" % (len(a), a.R.sum()))
print("Vens data : %2d shorts  %+7.2f R" % (len(b), b.R.sum()))
A={(r.day,r.entry_t[11:19]):(r.reason,round(float(r.R),2)) for r in a.itertuples()}
B={(r.day,r.entry_t[11:19]):(r.reason,round(float(r.R),2)) for r in b.itertuples()}
faelles=sorted(set(A)&set(B))
ens=[k for k in faelles if A[k]==B[k]]
print("\nsamme entry-sekund: %d | kun Databento: %d | kun ven: %d" % (len(faelles),len(set(A)-set(B)),len(set(B)-set(A))))
print("af de faelles er %d helt ens i udfald+R" % len(ens))
for k in faelles:
    if A[k]!=B[k]: print("   %s %s  DB %s %+.2f  <->  ven %s %+.2f" % (k[0],k[1],A[k][0],A[k][1],B[k][0],B[k][1]))
print("\nKUN Databento:"); [print("   %s %s %s %+.2f"%(k[0],k[1],A[k][0],A[k][1])) for k in sorted(set(A)-set(B))]
print("KUN ven:");        [print("   %s %s %s %+.2f"%(k[0],k[1],B[k][0],B[k][1])) for k in sorted(set(B)-set(A))]
