# -*- coding: utf-8 -*-
import sys, os, math, numpy as np, pandas as pd, importlib
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
MND={1:"januar",2:"februar",3:"marts",4:"april",5:"maj",6:"juni",7:"juli",8:"august",9:"sept"}
import model; model.BASE=SP+"/vendata"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60+30, **DAY, **CFG)
g = df[(df.asset=='NQ') & (df.day!="2026-06-11")].copy()
g['m']=g.day.str[5:7].astype(int)

# markedets bevaegelse i timen
d = pd.read_parquet(SP+'/vendata/NQ.parquet')
t = pd.to_datetime(d.time, utc=True).dt.tz_convert('America/New_York')
d = d.assign(day=t.dt.strftime('%Y-%m-%d'), tod=t.dt.hour*60+t.dt.minute)
w = d[(d.tod>=9*60+30)&(d.tod<10*60+30)].groupby('day').agg(
    o=('open','first'), h=('high','max'), l=('low','min'), c=('close','last'))
w['spa']=w.h-w.l; w['net']=w.c-w.o
w['eff']=(w.net.abs()/w.spa)           # hvor meget af spaendet der blev til retning
w['m']=pd.to_datetime(w.index).month

print("%-8s %4s %5s %5s %6s %7s %7s | %6s %7s | %7s %6s %6s" %
      ("maaned","n","LONG","SHORT","TP%","R/dag","R/handel","spaend","effekt","LONG R","SHORT R","dage"))
for m in sorted(g.m.unique()):
    x=g[g.m==m]; mw=w[w.m==m]
    L=x[x.side=='LONG']; S=x[x.side=='SHORT']
    print("%-8s %4d %5d %5d %5.0f%% %+7.2f %+8.2f | %6.0f %6.2f | %+7.2f %+6.2f %6d" %
          (MND[m], len(x), len(L), len(S), 100*(x.reason=='TP').mean(),
           x.R.sum()/x.day.nunique(), x.R.mean(), mw.spa.mean(), mw.eff.mean(),
           L.R.sum(), S.R.sum(), x.day.nunique()))

print("\n--- MARTS: retning vs. hvad markedet gjorde i timen ---")
mar = g[g.m==3]
for dd, x in mar.groupby('day'):
    mv = w.loc[dd]
    print("  %s  marked %+7.1f pts (spaend %5.0f)  |  %s  = %+6.2f R" %
          (dd, mv.net, mv.spa, " ".join("%s%+.2f" % (r.side[0], r.R) for r in x.itertuples()), x.R.sum()))

print("\n--- LONG vs SHORT hele aaret ---")
for s in ('LONG','SHORT'):
    x=g[g.side==s]; r=x.R.values
    print("  %-6s n %3d | R %+7.2f | pr.handel %+5.2f | TP %2d | vind%% %4.1f | t %+5.2f" %
          (s,len(r),r.sum(),r.mean(),(x.reason=='TP').sum(),(r>0).mean()*100,
           r.mean()*math.sqrt(len(r))/r.std()))
print("\n--- takt: R pr. handelsdag ---")
per = g.groupby('day').R.sum()
print("  hele aaret        : %+5.2f R/dag over %d dage" % (per.mean(), len(per)))
ins = per[(per.index>="2026-08-12")&(per.index<="2026-09-11")]
print("  12. aug - 11. sep : %+5.2f R/dag over %d dage" % (ins.mean(), len(ins)))
oos = per[per.index<"2026-08-12"]
print("  1. jan - 11. aug  : %+5.2f R/dag over %d dage" % (oos.mean(), len(oos)))
