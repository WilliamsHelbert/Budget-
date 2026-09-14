# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
def nq(a,b):
    df,_,_,_,_ = model.run_full(entry_from=a, entry_to=b, **DAY, **BASE)
    s = df[df.asset=='NQ']
    return {(r.day, r.entry_t[11:19]): float(r.R) for r in s.itertuples()}

H1 = nq(15*60+30, 16*60)      # 15:30-16:00
H2 = nq(16*60, 16*60+30)      # 16:00-16:30
A  = nq(15*60+30, 16*60+30)   # 15:30-16:30 samlet

print("15:30-16:00 alene : %2d handler  %+7.2f R" % (len(H1), sum(H1.values())))
print("16:00-16:30 alene : %2d handler  %+7.2f R" % (len(H2), sum(H2.values())))
print("naiv sum          : %2d handler  %+7.2f R" % (len(H1)+len(H2), sum(H1.values())+sum(H2.values())))
print("15:30-16:30 samlet: %2d handler  %+7.2f R\n" % (len(A), sum(A.values())))

fra1 = {k:v for k,v in A.items() if k in H1}
fra2 = {k:v for k,v in A.items() if k in H2}
nye  = {k:v for k,v in A.items() if k not in H1 and k not in H2}
v1   = {k:v for k,v in H1.items() if k not in A}
v2   = {k:v for k,v in H2.items() if k not in A}
print("Af de %d i det samlede vindue:" % len(A))
print("  %2d fandtes ogsaa i 15:30-16:00  %+7.2f R" % (len(fra1), sum(fra1.values())))
print("  %2d fandtes ogsaa i 16:00-16:30  %+7.2f R" % (len(fra2), sum(fra2.values())))
print("  %2d findes KUN naar begge halvtimer koerer sammen  %+7.2f R\n" % (len(nye), sum(nye.values())))

print("HELT NYE handler (opstaar foerst naar vinduet er sammenhaengende):")
for k,v in sorted(nye.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print()
print("Handler fra 15:30-16:00 der IKKE er med i det samlede:")
for k,v in sorted(v1.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print("   i alt %d, %+6.2f R" % (len(v1), sum(v1.values())))
print()
print("Handler fra 16:00-16:30 der IKKE er med i det samlede:")
for k,v in sorted(v2.items()): print("   %s %s  %+6.2f R" % (k[0], k[1], v))
print("   i alt %d, %+6.2f R" % (len(v2), sum(v2.values())))

# dage hvor de nye handler ligger
print("\nDAGE hvor en helt ny handel dukker op - hvad stod dagen paa foer den?")
import collections
bydag = collections.defaultdict(list)
for k,v in sorted(A.items()): bydag[k[0]].append((k[1],v))
for d in sorted(set(k[0] for k in nye)):
    print("   %s:" % d, "  ".join("%s %+.2f" % (t,v) for t,v in bydag[d]))
