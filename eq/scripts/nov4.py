# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
           max_stop={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
           conf_now=True, daily_basis='NQ')
def go(**extra):
    import model; importlib.reload(model)
    model.BASE=SP+"/db2024"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG, **extra)
    return df[df.asset=='NQ'].copy()
for lbl, kw in [("GAMMEL prev5",      dict(be_ref='prev', max_be={'ES':8,'NQ':40})),
                ("liq piv0, cap 40",  dict(be_src='liq', liq_piv=0, max_be={'ES':8,'NQ':40})),
                ("liq piv0, ingen cap",dict(be_src='liq', liq_piv=0)),
                ("liq piv1, ingen cap",dict(be_src='liq', liq_piv=1))]:
    n = go(daily_stop=-2.5, daily_target=3.75, **kw)
    a = n[n.day=="2024-11-04"]
    print("==", lbl, "| hele nov-dec n=%d R=%+.2f" % (len(n), n.R.sum()))
    print(a[['day','entry_t','side','entry','stop','tp','exit','reason','be_t','R']].to_string(index=False) or "  (ingen)")
