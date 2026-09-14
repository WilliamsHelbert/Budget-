# -*- coding: utf-8 -*-
"""Kor samme model paa to datakilder og sammenlign handlerne."""
import sys, os, importlib, pandas as pd
ENG = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ENG)
SP  = os.path.dirname(ENG)
BASECFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
               max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
               be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
W   = dict(entry_from=15*60+30, entry_to=16*60+30)

def run(base, lo=None, hi=None):
    import model
    importlib.reload(model)
    model.BASE = base
    df,_,n,_,_ = model.run_full(**W, **DAY, **BASECFG)
    s = df[df.asset=='NQ'].copy()
    if lo: s = s[(s.day>=lo)&(s.day<=hi)]
    return s

LO, HI = "2026-08-12", "2026-09-10"
tv  = run(SP, LO, HI)
ven = run(SP+"/vendata", LO, HI)
print("TradingView (uden 5s): %2d handler  %+7.2f R" % (len(tv), tv.R.sum()))
print("Vennens data         : %2d handler  %+7.2f R" % (len(ven), ven.R.sum()))

A = {(r.day, r.entry_t[11:19]): (r.reason, round(float(r.R),2), r.entry, r.stop) for r in tv.itertuples()}
B = {(r.day, r.entry_t[11:19]): (r.reason, round(float(r.R),2), r.entry, r.stop) for r in ven.itertuples()}
same = sorted(set(A) & set(B)); only_a = sorted(set(A)-set(B)); only_b = sorted(set(B)-set(A))
print("\nsamme entry-tidspunkt: %d | kun TV: %d | kun ven: %d" % (len(same), len(only_a), len(only_b)))
dif = [(k,A[k],B[k]) for k in same if A[k][0]!=B[k][0] or abs(A[k][1]-B[k][1])>0.01]
print("af de faelles er %d identiske i udfald og R, %d afviger" % (len(same)-len(dif), len(dif)))
for k,a,b in dif: print("   %s %s  TV %s %+.2f  <->  ven %s %+.2f" % (k[0],k[1],a[0],a[1],b[0],b[1]))
print("\nKUN i TradingView:")
for k in only_a: print("   %s %s  %s %+.2f" % (k[0],k[1],A[k][0],A[k][1]))
print("KUN i vennens data:")
for k in only_b: print("   %s %s  %s %+.2f" % (k[0],k[1],B[k][0],B[k][1]))
