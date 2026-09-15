# -*- coding: utf-8 -*-
import sys, os, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
DAGE = ["2026-01-08","2026-01-09","2026-01-13","2026-01-14","2026-01-15","2026-01-16"]
import model; importlib.reload(model)
model.BASE=SP+"/dbfull"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
df,_,stat,sig,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
    max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
    conf_now=True, be_src='liq', liq_piv=0, liq_from=0, block_mode='opposite')
s = pd.DataFrame(sig)
s['t'] = pd.to_datetime(s.ts, unit='s', utc=True).dt.tz_convert('Europe/Copenhagen')
s['dag'] = s.t.dt.strftime('%Y-%m-%d'); s['kl'] = s.t.dt.strftime('%H:%M:%S')
s = s[s.dag.isin(DAGE)]
print("SIGNALER modellen naaede at ARME paa de 6 dage:", len(s))
print(s.status.value_counts().to_string())
jour = pd.read_csv(SP+"/meq.csv")
for d in DAGE:
    print("\n" + "="*92); print("###", d)
    j = jour[jour.dag==d]
    print("JOURNAL:  " + " | ".join("%s %s %+.3f" % (r.ind, r.dir, r.R) for _,r in j.iterrows()))
    g = s[s.dag==d]
    if not len(g): print("MODEL:    ingen armede setups overhovedet"); continue
    for _,r in g.iterrows():
        why = r.get('why','') or ''
        print("MODEL:    %s %-5s %-22s %s" % (r.kl, r.side, r.status, why))
print("\n" + "="*92)
print("MOTOR-STATISTIK (hele koerslen):")
for k,v in stat.items(): print("  %-14s %s" % (k,v))
