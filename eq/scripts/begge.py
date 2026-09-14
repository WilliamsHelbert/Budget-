# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
J = pd.read_csv("/root/.claude/uploads/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/ca5c89db-trading_journal_2026-09-13.csv")
J['day']=pd.to_datetime(J.Date,format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
J['mi']=J.Entry.str[:2].astype(int)*60+J.Entry.str[3:5].astype(int)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, max_stop=None, max_be=None,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True, one_at_a_time=False,
    daily_stop=None, daily_target=None)
df=df[(df.day>="2026-01-08")&(df.day<="2026-01-16")].copy()
dk=pd.to_datetime(df.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
df['mi']=dk.dt.hour*60+dk.dt.minute
piv={}
for (d,m,s),g in df.groupby(['day','mi','side']):
    piv[(d,m,s)]={r.asset:r for r in g.itertuples()}
print("%-11s %-6s %-6s | %8s | %-22s | %-22s | %s" %
      ("dato","tid","retn","din ES R","MIT ES-ben","MIT NQ-ben","note"))
print("-"*118)
for r in J.itertuples():
    s=r.Direction.upper(); hit=None
    for dm in (0,-1,1,-2,2,-3,3):
        k=(r.day,r.mi+dm,s)
        if k in piv: hit=(dm,piv[k]); break
    if hit is None:
        opp="SHORT" if s=="LONG" else "LONG"; alt=None
        for dm in (0,-1,1):
            k=(r.day,r.mi+dm,opp)
            if k in piv: alt=piv[k]; break
        note = "jeg har %s paa samme tid" % opp if alt else "intet signal hos mig"
        print("%-11s %-6s %-6s | %+8.3f | %-22s | %-22s | %s" % (r.day,r.Entry,s,float(r.R),"—","—",note))
        continue
    dm,L=hit; e=L.get('ES'); n=L.get('NQ')
    fe=("%+.3f %-2s stop %5.2f" % (e.R,e.reason,e.stop_dist)) if e is not None else "—"
    fn=("%+.3f %-2s stop %5.1f" % (n.R,n.reason,n.stop_dist)) if n is not None else "—"
    note=[]
    if dm: note.append("%+dmin" % dm)
    if e is not None and abs(float(r.R)-e.R)>0.01: note.append("ES afviger")
    if e is not None and e.stop_dist>8: note.append("8-loft dropper")
    if n is not None and n.stop_dist>40: note.append("40-loft dropper")
    print("%-11s %-6s %-6s | %+8.3f | %-22s | %-22s | %s" %
          (r.day,r.Entry,s,float(r.R),fe,fn," · ".join(note)))
