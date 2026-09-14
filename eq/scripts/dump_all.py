# -*- coding: utf-8 -*-
import sys, os, json, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
def go(frm,to,sides=None):
    import model; importlib.reload(model)
    model.BASE=SP+"/vendata"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=frm, entry_to=to, sides=sides, **DAY, **CFG)
    g = df[(df.asset=='NQ') & (df.day!="2026-06-11")].copy()
    # tidsstempler tilbage til dansk tid til visning
    for c in ('entry_t','exit_t','hit_t','be_t'):
        s = pd.to_datetime(g[c], errors='coerce').dt.tz_localize('America/New_York', ambiguous='NaT', nonexistent='NaT')
        g[c+'_dk'] = s.dt.tz_convert('Europe/Copenhagen').dt.strftime('%H:%M:%S').fillna('')
    g['Rr'] = g.pts/g.stop_dist
    return g
for tag, frm, to in [("1600", 9*60+30, 10*60), ("1630", 9*60+30, 10*60+30)]:
    for v, sides in [("normal",None), ("bear",("bear",)), ("bull",("bull",))]:
        g = go(frm,to,sides)
        g.to_csv(f'/tmp/D_{tag}_{v}.csv', index=False)
        print(tag, v, len(g), round(g.R.sum(),2), flush=True)
