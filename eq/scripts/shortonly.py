# -*- coding: utf-8 -*-
import sys, os, math, numpy as np, pandas as pd, importlib
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')

def go(frm, to, sides=None):
    import model; importlib.reload(model)
    model.BASE=SP+"/vendata"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=frm, entry_to=to, sides=sides, **DAY, **CFG)
    return df[(df.asset=='NQ') & (df.day!="2026-06-11")].copy()

def st(g, navn):
    if len(g) < 2: return "%-34s  for faa handler" % navn
    r = g.sort_values('id').R.values; e = np.cumsum(r)
    rr = (g.sort_values('id').pts/g.sort_values('id').stop_dist).values
    w = r[r>0.005].sum(); l = r[r<-0.005].sum()
    return ("%-34s n %3d | R %+7.2f | pr.h %+5.2f | maxDD %+7.2f | TP %2d | vind%% %4.1f | PF %4.2f | t %+5.2f | Rrisk %+6.2f"
            % (navn, len(r), r.sum(), r.mean(), (e-np.maximum.accumulate(e)).min(),
               (g.reason=='TP').sum(), (r>0).mean()*100, abs(w/l) if l else 99,
               r.mean()*math.sqrt(len(r))/r.std(), rr.sum()))

OUT=[]
for wl, frm, to in [("15:30-16:00", 9*60+30, 10*60), ("15:30-16:30", 9*60+30, 10*60+30)]:
    full = go(frm,to)                      # normal: begge sider
    bonly = go(frm,to, sides=("bear",))    # kun shorts eksisterer
    OUT.append("\n" + "="*116)
    OUT.append("VINDUE %s dansk   -   NQ-benet, 1. jan - 11. sep 2026" % wl)
    OUT.append("="*116)
    for lbl, g in [("0  normal (begge sider)", full),
                   ("A  kun shorts, longs blokerer", full[full.side=='SHORT']),
                   ("B  kun shorts findes", bonly),
                   ("   (til sml.) kun longs findes", go(frm,to,sides=("bull",)))]:
        OUT.append(st(g, lbl))
        o = g[g.day<"2026-08-12"]
        OUT.append("   " + st(o, "   heraf out-of-sample").strip())
    # maanedsvis for B
    b = bonly.copy(); b['m']=b.day.str[5:7].astype(int)
    MND={1:"jan",2:"feb",3:"mar",4:"apr",5:"maj",6:"jun",7:"jul",8:"aug",9:"sep"}
    OUT.append("   maanedsvis (B kun shorts): " + "  ".join(
        "%s %+.1f" % (MND[m], x.R.sum()) for m,x in b.groupby('m')))
    bonly.to_csv('/tmp/shorts_%s.csv' % wl.replace(':',''), index=False)
print("\n".join(OUT))
