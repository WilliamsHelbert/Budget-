# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True,
           one_at_a_time=False,                 # din journal har overlap
           daily_stop=None, daily_target=None)  # og ingen dagsregler
# UDEN 8/40-loftet:
df,_,_,_,aud = model.run_full(entry_from=9*60+30, entry_to=10*60, max_stop=None, max_be=None, **CFG)
d = df[(df.asset=='NQ') & (df.day>="2026-01-08") & (df.day<="2026-01-16")].copy()
d['dk']=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
d['xdk']=pd.to_datetime(d.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
d=d.sort_values('id')
print("MIN MODEL (uden 8/40-loft, ingen dagsregler, overlap tilladt)")
print("%-12s %-6s %-6s %-6s %8s %8s %8s %s" % ("dato","entry","exit","retning","stop_pts","R","Rrisiko","udfald"))
for r in d.itertuples():
    print("%-12s %-6s %-6s %-6s %8.2f %+8.3f %+8.2f %s%s" %
          (r.day, r.dk.strftime('%H:%M'), r.xdk.strftime('%H:%M'), r.side,
           r.stop_dist, r.R, r.pts/r.stop_dist, r.reason,
           "   <-- 8/40 ville droppe den" if r.stop_dist>40 else ""))
print("\nn=%d  sum %+0.3f R" % (len(d), d.R.sum()))
d.to_csv('/tmp/jan_mine.csv', index=False)
