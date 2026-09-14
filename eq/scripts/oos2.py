import sys, os, math, numpy as np, importlib
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
import model; model.BASE=SP+"/vendata"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
                            daily_stop=-2.5, daily_target=3.75, daily_basis='NQ', **CFG)
df = df[(df.asset=='NQ') & (df.day!="2026-06-11")]
for lbl, g in (("HELE 1. jan - 11. sep", df),
               ("OUT-OF-SAMPLE 1. jan - 11. aug", df[df.day<"2026-08-12"]),
               ("IN-SAMPLE 12. aug - 11. sep", df[df.day>="2026-08-12"])):
    x=g.R.values; e=np.cumsum(x)
    print("%-32s n %3d | R %+7.2f | pr.handel %+5.2f | maxDD %+7.2f | vind%% %4.1f | t %+5.2f"
          % (lbl,len(x),x.sum(),x.mean(),(e-np.maximum.accumulate(e)).min(),(x>0).mean()*100,
             x.mean()*math.sqrt(len(x))/x.std()))
