# -*- coding: utf-8 -*-
import sys, os, math, numpy as np, pandas as pd, importlib
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
MND = {1:"januar",2:"februar",3:"marts",4:"april",5:"maj",6:"juni",
       7:"juli",8:"august",9:"september"}
def dk(x,n=2,s=True):
    if abs(x)<0.005: return "0,00"
    return (("%+.*f" if s else "%.*f")%(n,x)).replace('.',',').replace('-','−')

def go(frm,to):
    import model; importlib.reload(model)
    model.BASE=SP+"/vendata"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=frm, entry_to=to, **DAY, **CFG)
    g = df[(df.asset=='NQ') & (df.day!="2026-06-11")].copy()
    g['m'] = g.day.str[5:7].astype(int)
    g['Rr'] = g.pts/g.stop_dist
    return g

for lbl, frm, to in [("15:30-16:00 dansk  (09:30-10:00 NY)", 9*60+30, 10*60),
                     ("15:30-16:30 dansk  (09:30-10:30 NY)", 9*60+30, 10*60+30)]:
    g = go(frm,to)
    print("\n" + "="*94)
    print("%s   -   NQ-benet, dagsstop −2,5 / dagsmål +3,75" % lbl)
    print("="*94)
    print("%-11s %4s %5s %5s %5s %10s %10s %10s %9s %9s" %
          ("måned","n","vind","tab","nul","tjent R","mistet R","netto R","dage","t")) 
    tot = dict(n=0,w=0,l=0,z=0,gw=0.0,gl=0.0)
    for m, x in g.groupby('m'):
        w = x[x.R>0.005]; l = x[x.R<-0.005]; z = x[(x.R>=-0.005)&(x.R<=0.005)]
        tot['n']+=len(x); tot['w']+=len(w); tot['l']+=len(l); tot['z']+=len(z)
        tot['gw']+=w.R.sum(); tot['gl']+=l.R.sum()
        r = x.R.values
        t = r.mean()*math.sqrt(len(r))/r.std() if len(r)>1 and r.std()>0 else float('nan')
        print("%-11s %4d %5d %5d %5d %10s %10s %10s %9d %9s" %
              (MND[m], len(x), len(w), len(l), len(z), dk(w.R.sum()), dk(l.R.sum()),
               dk(x.R.sum()), x.day.nunique(), dk(t)))
    print("-"*94)
    print("%-11s %4d %5d %5d %5d %10s %10s %10s %9d %9s" %
          ("I ALT", tot['n'], tot['w'], tot['l'], tot['z'], dk(tot['gw']), dk(tot['gl']),
           dk(tot['gw']+tot['gl']), g.day.nunique(),
           dk(g.R.mean()*math.sqrt(len(g))/g.R.std())))
    print("   profitfaktor %.2f   |   gns. gevinst %s R   |   gns. tab %s R" %
          (abs(tot['gw']/tot['gl']), dk(tot['gw']/tot['w'],2), dk(tot['gl']/tot['l'],2)))
    # risikonormeret
    w = g[g.Rr>0.005]; l = g[g.Rr<-0.005]
    print("   risikonormeret: tjent %s R  mistet %s R  netto %s R  (profitfaktor %.2f)" %
          (dk(w.Rr.sum()), dk(l.Rr.sum()), dk(g.Rr.sum()), abs(w.Rr.sum()/l.Rr.sum())))
