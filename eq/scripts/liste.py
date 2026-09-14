import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
    one_at_a_time=True, oaat_leg="ES",          # spaerring pr. ben, ikke pr. par
    max_stop=None, max_be=None,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True, daily_stop=None, daily_target=None)
d=df[(df.day>="2026-01-02")&(df.day<="2026-01-16")].copy()
dk=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
xd=pd.to_datetime(d.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
d['t']=dk.dt.strftime('%H:%M'); d['x']=xd.dt.strftime('%H:%M')
J=pd.read_csv("/root/.claude/uploads/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/ca5c89db-trading_journal_2026-09-13.csv")
J['day']=pd.to_datetime(J.Date,format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
JS={(r.day,r.Entry):float(r.R) for r in J.itertuples()}
out=[]
for tid,g in d.groupby('id'):
    g=g.set_index('asset'); e=g.loc['ES']; n=g.loc['NQ']
    mi=int(e.t[:2])*60+int(e.t[3:5]); din=None
    for k,v in JS.items():
        if k[0]==e.day and abs(int(k[1][:2])*60+int(k[1][3:5])-mi)<=1: din=v; break
    out.append((e.day,e.t,e.x,e.side,float(e.R),float(n.R),float(e.stop_dist),float(n.stop_dist),din))
out.sort()
cur=None
for day,t,x,side,er,nr,es,ns,din in out:
    if day!=cur:
        print("\n%s" % day); cur=day
    d8 = "!" if es>8 else " "
    print("  %s-%s %-5s  ES %+6.2f  NQ %+6.2f   stop ES %5.2f%s NQ %5.1f%s   din %s" %
          (t,x,side.title(),er,nr,es,d8,ns,"!" if ns>40 else " ",
           ("%+.3f"%din) if din is not None else "-"))
print("\n%d handler | ES %+0.2f R | NQ %+0.2f R | din journal %d handler" %
      (len(out), sum(o[4] for o in out), sum(o[5] for o in out), len(JS)))
