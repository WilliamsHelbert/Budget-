# -*- coding: utf-8 -*-
import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')

def nq(a,b):
    df,_,_,_,_ = model.run_full(entry_from=a, entry_to=b, **DAY, **BASE)
    s = df[df.asset=='NQ'].copy()
    return {(r.day, r.entry_t[11:19]): float(r.R) for r in s.itertuples()}

A = nq(15*60+30, 16*60+30)     # 15:30-16:30
B = nq(16*60+30, 17*60)        # 16:30-17:00 alene
C = nq(15*60+30, 17*60)        # 15:30-17:00

print("15:30-16:30 alene : %2d handler  %+7.2f R" % (len(A), sum(A.values())))
print("16:30-17:00 alene : %2d handler  %+7.2f R" % (len(B), sum(B.values())))
print("15:30-17:00 samlet: %2d handler  %+7.2f R" % (len(C), sum(C.values())))
print("  naiv sum A+B = %+7.2f R  -> forskel til C: %+7.2f R\n" % (sum(A.values())+sum(B.values()),
                                                                   sum(C.values())-sum(A.values())-sum(B.values())))

mist_A = {k:v for k,v in A.items() if k not in C}
mist_B = {k:v for k,v in B.items() if k not in C}
nye    = {k:v for k,v in C.items() if k not in A and k not in B}
med_B  = {k:v for k,v in B.items() if k in C}
print("Handler fra 15:30-16:30 der FORSVINDER naar vinduet aabnes til 17:00:")
for k,v in sorted(mist_A.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print("   i alt %d handler, %+7.2f R\n" % (len(mist_A), sum(mist_A.values())))

print("Handler fra 16:30-17:00 der KOMMER MED i det samlede vindue:")
for k,v in sorted(med_B.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print("   i alt %d handler, %+7.2f R\n" % (len(med_B), sum(med_B.values())))

print("Handler fra 16:30-17:00 der ALDRIG naar at blive taget (dagen var lukket / anden handel loeb):")
for k,v in sorted(mist_B.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print("   i alt %d handler, %+7.2f R\n" % (len(mist_B), sum(mist_B.values())))

print("Helt nye handler der kun findes i det samlede vindue:")
for k,v in sorted(nye.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print("   i alt %d handler, %+7.2f R" % (len(nye), sum(nye.values())))

print("\nREGNSKAB:  A %+7.2f" % sum(A.values()))
print("           - mistede fra A %+7.2f" % (-sum(mist_A.values())))
print("           + medtagne fra B %+7.2f" % sum(med_B.values()))
print("           + helt nye       %+7.2f" % sum(nye.values()))
print("           = C              %+7.2f  (facit %+7.2f)" %
      (sum(A.values())-sum(mist_A.values())+sum(med_B.values())+sum(nye.values()), sum(C.values())))
