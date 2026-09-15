# -*- coding: utf-8 -*-
# Hvor langt vaek ligger det naermeste LEVENDE 5m-liq i forhold til TP?
import sys, os, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
           max_stop={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
           conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75,
           be_src='liq', liq_piv=0)
import model; importlib.reload(model)
model.BASE=SP+"/db2025"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
df,_,_,sig,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG)
s = pd.DataFrame(sig); s = s[s.status=="TAGET"]
b = s.NQ_bedist.dropna()
print("NQ BE-afstand (levende 5m-liq) paa 2025, n=%d" % len(b))
print(b.describe(percentiles=[.1,.25,.5,.75,.9]).round(1).to_string())
print("\nandel under 75 pt (dvs. foer TP): %.1f%%" % ((b<75).mean()*100))
for c in (20,30,40,50,60,75,100,150):
    print("  <= %3d pt: %5.1f%%" % (c,(b<=c).mean()*100))
