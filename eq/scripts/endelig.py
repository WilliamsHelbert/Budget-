# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
           conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75,
           be_src='liq', liq_piv=0, liq_from=0)
def go(folder):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG)
    n = df[(df.asset=='NQ') & (df.side=='SHORT')].copy()
    dk=pd.to_datetime(n.entry_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    xd=pd.to_datetime(n.exit_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    n['t']=dk.dt.strftime('%H:%M:%S'); n['x']=xd.dt.strftime('%H:%M:%S'); n['mnd']=n.day.str[:7]
    n['kilde']=folder
    return n.sort_values('id')
db  = go("dbfull")                       # nov 2024 - feb 2026, Databento
ven = go("vendata")                      # 2026 hele aaret, NinjaTrader
ven = ven[ven.day >= "2026-03-01"]       # kun perioden Databento ikke daekker
alle = pd.concat([db, ven], ignore_index=True).sort_values(['day','entry_t']).reset_index(drop=True)
alle['akk'] = alle.R.cumsum()
alle.to_csv(SP+"/eq_endelig_fuld.csv", index=False)
r = alle.R.values; e=np.cumsum(r)
print("=== ENDELIG: naermeste levende 5m-liq (hele doegnet), 8/40-loft ===")
print("nov 2024 - sep 2026 | n %d | R %+.2f | pr.h %+.2f | maxDD %+.2f | t %+.2f"
      % (len(r), r.sum(), r.mean(), (e-np.maximum.accumulate(e)).min(),
         r.mean()*math.sqrt(len(r))/r.std()))
print("TP %d | SL %d | BE %d" % ((alle.reason=='TP').sum(),(alle.reason=='SL').sum(),(alle.reason=='BE').sum()))
print("\n--- aar for aar ---")
for lbl, sel in (("2024 (nov-dec)", alle.mnd<"2025-01"),
                 ("2025", (alle.mnd>="2025-01")&(alle.mnd<"2026-01")),
                 ("2026 (jan-sep)", alle.mnd>="2026-01")):
    g=alle[sel]; rr=g.R.values
    print("%-16s n %3d | R %+7.2f | pr.h %+5.2f | t %+5.2f" %
          (lbl, len(rr), rr.sum(), rr.mean(), rr.mean()*math.sqrt(len(rr))/rr.std()))
print("\n--- maaned for maaned ---")
print(alle.groupby('mnd').agg(n=('R','size'),R=('R','sum'),TP=('reason',lambda s:(s=='TP').sum()),
    SL=('reason',lambda s:(s=='SL').sum()),BE=('reason',lambda s:(s=='BE').sum())).round(2).to_string())
