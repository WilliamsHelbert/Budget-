# -*- coding: utf-8 -*-
import sys, os, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/dbfull"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
df,_,_,sig,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True,
    be_src='liq', liq_piv=0, liq_from=0, block_mode='opposite')   # INGEN caps
s = pd.DataFrame(sig)
s['t']=pd.to_datetime(s.ts,unit='s',utc=True).dt.tz_convert('Europe/Copenhagen')
s=s[s.t.dt.strftime('%Y-%m-%d')=="2024-11-13"]
pd.set_option('display.width',200)
print("ALLE armede setups 13. nov 2024 (ingen caps):")
for _,r in s.iterrows():
    print("  %s %-5s %-16s | NQ ind %8s sl %8s be %7s | ES ind %8s sl %8s be %6s | %s" %
      (r.t.strftime('%H:%M:%S'), r.side, r.status,
       f"{r.NQ_entry:.2f}" if pd.notna(r.get('NQ_entry')) else "-",
       f"{r.NQ_stop:.2f}"  if pd.notna(r.get('NQ_stop'))  else "-",
       f"{r.NQ_bedist:.2f}" if pd.notna(r.get('NQ_bedist')) else "-",
       f"{r.ES_entry:.2f}" if pd.notna(r.get('ES_entry')) else "-",
       f"{r.ES_stop:.2f}"  if pd.notna(r.get('ES_stop'))  else "-",
       f"{r.ES_bedist:.2f}" if pd.notna(r.get('ES_bedist')) else "-", r.get('why','') or ''))
t = df[df.day=="2024-11-13"]
print("\nHandler modellen tog UDEN caps:")
print(t[['asset','side','entry','stop','tp','exit','reason','R','entry_t','exit_t']].to_string(index=False) if len(t) else "  ingen")
