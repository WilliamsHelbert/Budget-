import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, max_stop=None, max_be=None,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True, one_at_a_time=False,
    daily_stop=None, daily_target=None)
d=df[(df.day>="2026-01-01")&(df.day<="2026-01-16")].copy()
dk=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
d['t']=dk.dt.strftime('%H:%M')
J=pd.read_csv("/root/.claude/uploads/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/ca5c89db-trading_journal_2026-09-13.csv")
J['day']=pd.to_datetime(J.Date,format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
JS={(r.day,r.Entry) for r in J.itertuples()}
rows=[]
for tid,g in d.groupby('id'):
    g=g.set_index('asset'); e=g.loc['ES']; n=g.loc['NQ']
    rows.append((e.day,e.t,e.side,float(e.R),float(n.R),float(e.stop_dist),float(n.stop_dist)))
rows.sort()
cur=None
for day,t,side,er,nr,es,ns in rows:
    if day!=cur: print("\n%s" % day); cur=day
    dr=[]
    if es>8: dr.append("8")
    if ns>40: dr.append("40")
    mark = "DIN" if any(abs(int(t[:2])*60+int(t[3:5])-(int(x[1][:2])*60+int(x[1][3:5])))<=1 and x[0]==day for x in JS) else "   "
    print("  %s %-5s %-5s  ES %+6.3f  NQ %+6.3f   %-5s %s" %
          (mark, t, side.title(), er, nr, ("drop "+"/".join(dr)) if dr else "", ""))
print("\nI ALT %d handler | ES %+0.2f R | NQ %+0.2f R" %
      (len(rows), sum(r[3] for r in rows), sum(r[4] for r in rows)))
