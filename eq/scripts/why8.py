# -*- coding: utf-8 -*-
import sys, os, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')
df,_,_,_,_ = model.run_full(entry_from=15*60+30, entry_to=16*60+30, **DAY, **BASE)
s = df[df.asset=='NQ']
byday = {}
for r in s.itertuples():
    byday.setdefault(r.day, []).append((r.entry_t[11:19], r.exit_t[11:19], float(r.R)))

DROP = [("2026-08-14","16:01:15",0.00),("2026-08-14","16:12:15",-2.48),
        ("2026-08-17","16:06:00",0.00),("2026-08-20","16:07:00",-3.52),
        ("2026-08-25","16:10:00",0.00),("2026-09-01","16:12:45",-2.95),
        ("2026-09-04","16:09:00",0.00),("2026-09-09","16:09:15",-3.42)]
for d, t, R in DROP:
    ts = byday.get(d, [])
    run = [x for x in ts if x[0] <= t <= x[1]]
    before = sum(x[2] for x in ts if x[1] <= t)
    if run:
        why = "handel fra %s loeb stadig (exit %s)" % (run[0][0], run[0][1])
    elif before >= 3.75: why = "dagsmaal ramt (dagen stod %+.2f R)" % before
    elif before <= -2.5: why = "dagsstop ramt (dagen stod %+.2f R)" % before
    else: why = "?? dagen stod %+.2f R" % before
    print("%s %s  (%+5.2f R sprunget over)  ->  %s" % (d, t, R, why))
