import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
    per_leg=True, one_at_a_time=True,
    daily_stop=-5.0, daily_target=7.5,
    max_stop=None, max_be=None,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
d=df[(df.day>="2026-01-02")&(df.day<="2026-01-16")].copy()
dk=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
xd=pd.to_datetime(d.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
d['t']=dk.dt.strftime('%H:%M'); d['x']=xd.dt.strftime('%H:%M')
J=pd.read_csv("/root/.claude/uploads/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/ca5c89db-trading_journal_2026-09-13.csv")
J['day']=pd.to_datetime(J.Date,format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
JS={(r.day,r.Entry) for r in J.itertuples()}
d.to_csv('/tmp/jan_perleg.csv', index=False)
cur=None
for tid,g in d.groupby('id'):
    g=g.set_index('asset'); r0=g.iloc[0]
    if r0.day!=cur: print("\n%s"%r0.day); cur=r0.day
    mi=int(r0.t[:2])*60+int(r0.t[3:5])
    star="*" if any(k[0]==r0.day and abs(int(k[1][:2])*60+int(k[1][3:5])-mi)<=1 for k in JS) else " "
    def f(a):
        if a not in g.index: return "  --  "
        return "%+6.2f" % g.loc[a].R
    print("  %s %s-%s %-5s  ES %s  NQ %s   [%s]" %
          (star, r0.t, r0.x, r0.side.title(), f('ES'), f('NQ'), "+".join(g.index)))
es=d[d.asset=='ES']; nq=d[d.asset=='NQ']
print("\npar/entries %d | ES-ben %d (%+0.2f R) | NQ-ben %d (%+0.2f R)" %
      (d.id.nunique(), len(es), es.R.sum(), len(nq), nq.R.sum()))
