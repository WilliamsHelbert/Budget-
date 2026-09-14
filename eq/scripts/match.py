# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd, numpy as np
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
J = pd.read_csv("/root/.claude/uploads/9cd0cf78-f7d9-5321-b0ed-f908d1ea157c/ca5c89db-trading_journal_2026-09-13.csv")
J['day'] = pd.to_datetime(J.Date, format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
J['min'] = J.Entry.str[:2].astype(int)*60 + J.Entry.str[3:5].astype(int)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True, one_at_a_time=False,
           daily_stop=None, daily_target=None)
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, max_stop=None, max_be=None, **CFG)
df = df[(df.day>="2026-01-08")&(df.day<="2026-01-16")].copy()
dk = pd.to_datetime(df.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
df['dkmin'] = dk.dt.hour*60+dk.dt.minute
df['dktid'] = dk.dt.strftime('%H:%M')
piv = {}
for (d,m,side), g in df.groupby(['day','dkmin','side']):
    piv[(d,m,side)] = {r.asset: r for r in g.itertuples()}

print("%-11s %-6s %-6s %8s | %-18s | %-18s" % ("dato","tid","retning","din R","MIN NQ","MIN ES"))
res=[]
for r in J.itertuples():
    side = r.Direction.upper()
    best=None
    for dm in (0,-1,1,-2,2,-3,3):
        k=(r.day, r._4 if False else r.__getattribute__('min')+dm, side)
        if k in piv: best=(dm,piv[k]); break
    if best is None:
        print("%-11s %-6s %-6s %+8.3f | %-18s | %s" % (r.day, r.Entry, side, float(r.R), "INGEN", "INGEN"))
        res.append((r.day,r.Entry,side,float(r.R),None,None)); continue
    dm,leg = best
    nq = leg.get('NQ'); es = leg.get('ES')
    fn = ("%+.3f %s %.1fp" % (nq.R, nq.reason, nq.stop_dist)) if nq is not None else "-"
    fe = ("%+.3f %s %.2fp" % (es.R, es.reason, es.stop_dist)) if es is not None else "-"
    print("%-11s %-6s %-6s %+8.3f | %-18s | %-18s %s" %
          (r.day, r.Entry, side, float(r.R), fn, fe, ("(%+dmin)"%dm) if dm else ""))
    res.append((r.day,r.Entry,side,float(r.R), nq.R if nq is not None else None,
                es.R if es is not None else None))
R=pd.DataFrame(res, columns=['day','tid','side','din','nq','es']).dropna()
print("\nafvigelse |din - NQ| : median %.3f  | antal eksakte %d/%d" %
      ((R.din-R.nq).abs().median(), int(((R.din-R.nq).abs()<0.01).sum()), len(R)))
print("afvigelse |din - ES| : median %.3f  | antal eksakte %d/%d" %
      ((R.din-R.es).abs().median(), int(((R.din-R.es).abs()<0.01).sum()), len(R)))
print("\ndin sum %+0.3f | NQ %+0.3f | ES %+0.3f" % (R.din.sum(), R.nq.sum(), R.es.sum()))
