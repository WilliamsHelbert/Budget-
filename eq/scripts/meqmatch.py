# -*- coding: utf-8 -*-
import sys, os, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
DAGE = ["2026-01-08","2026-01-09","2026-01-13","2026-01-14","2026-01-15","2026-01-16"]
def go(folder, **kw):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    cfg = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
               max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
               conf_now=True, be_src='liq', liq_piv=0, liq_from=0)
    cfg.update(kw)
    df,_,_,sig,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **cfg)
    n = df[(df.asset=='NQ') & df.day.isin(DAGE)].copy()
    if len(n):
        dk=pd.to_datetime(n.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
        xd=pd.to_datetime(n.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
        n['ind']=dk.dt.strftime('%H:%M'); n['ud']=xd.dt.strftime('%H:%M')
        n['dir']=n.side.str.title()
    return n.sort_values(['day','entry_t'])
jour = pd.read_csv(SP+"/meq.csv")
def match(mod, lbl):
    mk = set(zip(mod.day, mod.ind, mod.dir)) if len(mod) else set()
    jk = set(zip(jour.dag, jour.ind, jour.dir))
    # match paa dag+retning inden for +-2 min
    tm = lambda s: int(s[:2])*60+int(s[3:])
    par=[]; brugt=set()
    for _,j in jour.iterrows():
        bedst=None
        for i,m in mod.iterrows():
            if i in brugt or m.day!=j.dag or m.dir!=j.dir: continue
            d=abs(tm(m.ind)-tm(j.ind))
            if d<=2 and (bedst is None or d<bedst[1]): bedst=(i,d)
        if bedst: brugt.add(bedst[0]); par.append((j, mod.loc[bedst[0]], bedst[1]))
        else: par.append((j, None, None))
    ekstra = mod[~mod.index.isin(brugt)]
    print("\n%s" % lbl)
    print("  modellen tog %d | journalen har %d | matchet %d | modellen mangler %d | modellen har for meget %d"
          % (len(mod), len(jour), len(brugt), len(jour)-len(brugt), len(ekstra)))
    return par, ekstra
for lbl, kw in (("ingen dagsstop, block=any",      dict(block_mode='any')),
                ("ingen dagsstop, block=opposite", dict(block_mode='opposite')),
                ("dagsstop -2.5, block=any",       dict(block_mode='any', daily_stop=-2.5, daily_target=3.75, daily_basis='NQ'))):
    mod = go("dbfull", **kw)
    par, ekstra = match(mod, lbl)
print("\n" + "="*100)
print("DETALJE: ingen dagsstop, block=opposite")
mod = go("dbfull", block_mode='opposite')
par, ekstra = match(mod, "")
print("\n%-11s %-6s %-6s %-8s | %-6s %-6s %-8s %-9s" % ("dag","jour","dir","jour R","model","dir","model R","udfald"))
for j, m, d in par:
    if m is None:
        print("%-11s %-6s %-6s %+8.3f | %s" % (j.dag, j.ind, j.dir, j.R, "-- INGEN --"))
    else:
        print("%-11s %-6s %-6s %+8.3f | %-6s %-6s %+8.2f %-9s (%+d min)"
              % (j.dag, j.ind, j.dir, j.R, m.ind, m.dir, m.R, m.reason, int(m.ind[:2])*60+int(m.ind[3:])-(int(j.ind[:2])*60+int(j.ind[3:]))))
if len(ekstra):
    print("\nModellen tog disse som IKKE er i journalen:")
    for _,m in ekstra.iterrows():
        print("  %-11s %-6s %-6s %+8.2f %-6s  stop %.2f pt" % (m.day, m.ind, m.dir, m.R, m.reason, m.stop_dist))
