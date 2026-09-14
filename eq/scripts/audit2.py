# -*- coding: utf-8 -*-
import sys, os, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
pd.set_option('display.width',200); pd.set_option('display.max_colwidth',60)
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
for lbl,a,b in [("SAMLET 15:30-16:30",15*60+30,16*60+30), ("KUN 16:00-16:30",16*60,16*60+30)]:
    df,_,_,_,aud = model.run_full(entry_from=a, entry_to=b, **DAY, **BASE)
    for d in ("2026-08-17","2026-09-04"):
        x = aud[aud.dag==d][['tid','asset','retning','status']]
        print("\n--- %s | %s ---" % (lbl, d))
        for r in x.itertuples():
            print("  %s %s %-5s  %s" % (r.tid[11:], r.asset, r.retning, r.status))
