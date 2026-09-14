# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
# ingen dagsregler overhovedet, saa vi ser ALLE signaler den dag uden at noget spaerrer
df,_,_,_,aud = model.run_full(entry_from=9*60+30, entry_to=10*60,
    per_leg=True, one_at_a_time=True, daily_stop=None, daily_target=None,
    max_stop=None, max_be=None,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
d=df[df.day=="2026-01-09"].copy()
dk=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
xd=pd.to_datetime(d.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
d['t']=dk.dt.strftime('%H:%M:%S'); d['x']=xd.dt.strftime('%H:%M:%S')
print("ALLE signaler 9. jan (ingen dagsregler, saa intet blokerer):")
for r in d.sort_values(['asset','id']).itertuples():
    print("  %s  %s -> %s  %-5s  entry %9.2f stop %9.2f (%.2f p)  %+7.3f R  %s"
          % (r.asset, r.t, r.x, r.side, r.entry, r.stop, r.stop_dist, r.R, r.reason))

# raa 15s barer omkring 15:41-15:56 dansk tid paa ES, for at se hvad der skete ved 15:36-udgangen
esraw = pd.read_parquet(SP+'/vendata/ES.parquet')
t = pd.to_datetime(esraw.time, utc=True).dt.tz_convert('Europe/Copenhagen')
w = esraw[(t>="2026-01-09 15:34:00+01:00")&(t<="2026-01-09 15:56:00+01:00")].copy()
w['t']=pd.to_datetime(w.time,utc=True).dt.tz_convert('Europe/Copenhagen').dt.strftime('%H:%M:%S')
print("\nES 15s-barer 15:34-15:56:")
for r in w.itertuples():
    print("  %s  o%8.2f h%8.2f l%8.2f c%8.2f" % (r.t,r.open,r.high,r.low,r.close))
