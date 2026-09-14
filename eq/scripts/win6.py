import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
print("RISIKO-NORMALISERET (1R = den faktiske stop-afstand pr. handel)\n")
print("%-13s %-3s %4s %9s %9s %8s %7s" % ("vindue","ass","n","sum Rrisk","pr.handel","maxDD","snit RR"))
for name,a,b in [("15:30-16:00",15*60+30,16*60),("16:00-16:30",16*60,16*60+30),
                 ("16:30-17:00",16*60+30,17*60),("15:30-16:30",15*60+30,16*60+30)]:
    df,_,n,_,_ = model.run_full(entry_from=a, entry_to=b, daily_stop=-5, daily_target=7.5,
                                daily_basis='sum', **BASE)
    for k in ("NQ","ES"):
        s = df[df.asset==k].sort_values('id').copy()
        s['Rr'] = s.pts / s.stop_dist
        rr = (abs(s.tp - s.entry) / s.stop_dist).mean()
        r = s.Rr.values; eq=np.cumsum(r)
        print("%-13s %-3s %4d %+9.2f %+9.2f %+8.2f %7.2f" %
              (name,k,len(r),r.sum(),r.mean(),(eq-np.maximum.accumulate(eq)).min(),rr))
    print()

print("Samme, men KUN NQ med dagsregler paa NQ-benet (-2,5/+3,75):")
df,_,n,_,_ = model.run_full(entry_from=15*60+30, entry_to=16*60+30, daily_stop=-2.5,
                            daily_target=3.75, daily_basis='NQ', **BASE)
s = df[df.asset=='NQ'].sort_values('id').copy()
s['Rr']=s.pts/s.stop_dist
r=s.Rr.values; eq=np.cumsum(r)
print("  n %d | sum %+.2f Rrisk | pr.handel %+.2f | maxDD %+.2f | snit RR %.2f:1 | vind%% %.1f | t %+.2f"
      % (len(r), r.sum(), r.mean(), (eq-np.maximum.accumulate(eq)).min(),
         (abs(s.tp-s.entry)/s.stop_dist).mean(), (r>0).mean()*100, r.mean()*np.sqrt(len(r))/r.std()))
print("  stoerste gevinst %+.2f | stoerste tab %+.2f | stop-afstand min %.1f med %.1f max %.1f pts"
      % (r.max(), r.min(), s.stop_dist.min(), s.stop_dist.median(), s.stop_dist.max()))
