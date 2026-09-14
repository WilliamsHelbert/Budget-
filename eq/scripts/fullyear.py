# -*- coding: utf-8 -*-
import sys, os, numpy as np, pandas as pd, math
ENG = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ENG)
from nytz import run
SP = os.path.dirname(ENG)
nq, both, aud = run(SP+"/vendata", ny=True)
nq = nq[nq.day != "2026-06-11"]          # ES-huller den dag, udelades
nq = nq.sort_values('id').reset_index(drop=True)
r = nq.R.values; eq = np.cumsum(r)
rr = (nq.pts/nq.stop_dist).values; eqr = np.cumsum(rr)
print("=== HELE 2026 (1. jan - 11. sep), NQ-benet, 09:30-10:30 NY ===")
print("handler %d | handelsdage %d | R %+.2f | pr. handel %+.2f" % (len(r), nq.day.nunique(), r.sum(), r.mean()))
print("maxDD %+.2f R | vind%% %.1f | sd %.2f | t %+.2f" %
      ((eq-np.maximum.accumulate(eq)).min(), (r>0).mean()*100, r.std(), r.mean()*math.sqrt(len(r))/r.std()))
print("risikonormeret: %+.2f R | pr. handel %+.2f | maxDD %+.2f | t %+.2f" %
      (rr.sum(), rr.mean(), (eqr-np.maximum.accumulate(eqr)).min(), rr.mean()*math.sqrt(len(rr))/rr.std()))
print("TP %d  SL %d  BE %d  EOD %d" % ((nq.reason=='TP').sum(),(nq.reason=='SL').sum(),
                                        (nq.reason=='BE').sum(),(nq.reason=='EOD').sum()))
print("stoerste gevinst %+.2f | stoerste tab %+.2f" % (r.max(), r.min()))

nq['m'] = nq.day.str[:7]
print("\n%-9s %5s %9s %9s %8s" % ("maaned","n","R","pr.handel","vind%"))
for m, g in nq.groupby('m'):
    print("%-9s %5d %+9.2f %+9.2f %7.1f" % (m, len(g), g.R.sum(), g.R.mean(), (g.R>0).mean()*100))

# in-sample (aug-sep) vs out-of-sample (jan-aug 11)
IS0, IS1 = "2026-08-12", "2026-09-11"
os_ = nq[nq.day < IS0]; is_ = nq[(nq.day>=IS0)]
for lbl, g in (("OUT-OF-SAMPLE  1. jan - 11. aug", os_), ("IN-SAMPLE     12. aug - 11. sep", is_)):
    x = g.R.values; e = np.cumsum(x)
    print("\n%s" % lbl)
    print("  handler %d | dage %d | R %+.2f | pr. handel %+.2f | maxDD %+.2f | vind%% %.1f | t %+.2f" %
          (len(x), g.day.nunique(), x.sum(), x.mean(), (e-np.maximum.accumulate(e)).min(),
           (x>0).mean()*100, x.mean()*math.sqrt(len(x))/x.std()))
nq.to_csv('/tmp/fullyear_nq.csv', index=False)
both.to_csv('/tmp/fullyear_both.csv', index=False)
