# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
df,_,_,_,aud = model.run_full(entry_from=9*60+30, entry_to=10*60,
    per_leg=True, one_at_a_time=True, daily_stop=None, daily_target=None,
    max_stop=None, max_be=None,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
a = aud[aud.dag=="2026-01-09"].copy()
dk = pd.to_datetime(a.tid).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
a['t']=dk.dt.strftime('%H:%M:%S')
w = a[(a.t>="15:44:00")&(a.t<="16:01:00")]
print(w[['t','asset','retning','eq_linje','eq_anker','raid_luk','status']].to_string(index=False))
