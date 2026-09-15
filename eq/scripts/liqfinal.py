# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True, daily_basis='NQ',
           daily_stop=-2.5, daily_target=3.75, be_src='liq', liq_piv=0)
def go(folder):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG)
    n = df[(df.asset=='NQ') & (df.side=='SHORT')].copy()
    dk=pd.to_datetime(n.entry_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    xd=pd.to_datetime(n.exit_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    n['t']=dk.dt.strftime('%H:%M:%S'); n['x']=xd.dt.strftime('%H:%M:%S'); n['mnd']=n.day.str[:7]
    return n.sort_values('id')
alle = pd.concat([go(f) for f in ("db2024","db2025","vendata")], ignore_index=True)
alle = alle.drop_duplicates(subset=['day','entry_t','entry']).sort_values(['day','entry_t']).reset_index(drop=True)
alle.to_csv(SP+"/eq_liq_shorts.csv", index=False)
print("gemt", len(alle), "handler ->", SP+"/eq_liq_shorts.csv")
m = alle.groupby('mnd').agg(n=('R','size'), R=('R','sum'),
        TP=('reason',lambda s:(s=='TP').sum()), SL=('reason',lambda s:(s=='SL').sum()),
        BE=('reason',lambda s:(s=='BE').sum())).round(2)
print(m.to_string())
r = alle.R.values; e=np.cumsum(r)
print("\nI ALT n %d | R %+.2f | pr.h %+.2f | maxDD %+.2f | t %+.2f"
      % (len(r), r.sum(), r.mean(), (e-np.maximum.accumulate(e)).min(),
         r.mean()*math.sqrt(len(r))/r.std()))
print(alle[['day','t','entry','stop','tp','beniv','exit','reason','R']].head(0).to_string() if 'beniv' in alle else "")
print("\nkolonner:", [c for c in alle.columns])
