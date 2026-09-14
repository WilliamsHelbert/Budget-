import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/db2025"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True,
    daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
d=df[(df.asset=='NQ')&(df.side=='SHORT')].copy()
d=d[(d.day>="2025-01-01")&(d.day<="2025-12-31")]
dk=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
xd=pd.to_datetime(d.exit_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
d['dag']=d.day; d['t']=dk.dt.strftime('%H:%M'); d['x']=xd.dt.strftime('%H:%M')
d=d.sort_values('id')
d.to_csv('/tmp/y2025_1600.csv',index=False)
print(len(d), round(d.R.sum(),2))
print(d.groupby(d.dag.str[:7]).R.agg(['count','sum']).round(2).to_string())
