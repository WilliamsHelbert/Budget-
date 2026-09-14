import sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
df,_,n,_,_ = model.run_full(entry_from=15*60+30, entry_to=16*60+30,
                            daily_stop=-2.5, daily_target=3.75, daily_basis='NQ', **BASE)
s = df[df.asset=='NQ'].sort_values('id')
print("KUN NQ  15:30-16:30  dagsstop -2,5 / dagsmaal +3,75\n")
dag = s.groupby('day').R.agg(['count','sum'])
for d,row in dag.iterrows():
    print("  %s  %d handler  %+7.2f R" % (d,row['count'],row['sum']))
print("\n  vindende dage %d / %d   |  stoerste dagstab %+.2f  stoerste dagsgevinst %+.2f"
      % ((dag['sum']>0).sum(), len(dag), dag['sum'].min(), dag['sum'].max()))
r = s.R.values; eq=np.cumsum(r)
print("  handler %d | R %+.2f | pr.handel %+.2f | maxDD %+.2f | vind%% %.1f | t %+.2f"
      % (len(r), r.sum(), r.mean(), (eq-np.maximum.accumulate(eq)).min(), (r>0).mean()*100,
         r.mean()*np.sqrt(len(r))/r.std()))
print("  stoerste enkeltgevinst %+.2f R | stoerste enkelttab %+.2f R" % (r.max(), r.min()))
print("  fordeling: TP %d  SL %d  BE %d" % ((s.reason=='TP').sum(),(s.reason=='SL').sum(),(s.reason=='BE').sum()))
print("\n  gns. stop-afstand %.1f pts (= %.2f R)" % (s.stop_dist.mean(), s.risk_R.mean()))
