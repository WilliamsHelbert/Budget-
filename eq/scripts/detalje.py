# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True, one_at_a_time=False,
           daily_stop=None, daily_target=None)
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, max_stop=None, max_be=None, **CFG)
e = df[(df.asset=='ES')&(df.day>="2026-01-08")&(df.day<="2026-01-16")].copy()
dk = pd.to_datetime(e.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
xd = pd.to_datetime(e.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
e['t']=dk.dt.strftime('%H:%M'); e['x']=xd.dt.strftime('%H:%M'); e['tm']=dk.dt.hour*60+dk.dt.minute
print("ALLE MINE ES-SIGNALER 8.-16. januar (%d stk)\n" % len(e))
print("%-11s %-6s %-6s %-6s %8s %8s %8s %8s %7s %s" %
      ("dato","entry","exit","retn","indgang","stop","stop_p","maal","R","udfald"))
for r in e.sort_values('id').itertuples():
    flag = "  << over 8 pts - 8/40 dropper den" if r.stop_dist>8 else ""
    print("%-11s %-6s %-6s %-6s %8.2f %8.2f %8.2f %8.2f %+7.3f %s%s" %
          (r.day, r.t, r.x, r.side, r.entry, r.stop, r.stop_dist, r.tp, r.R, r.reason, flag))
