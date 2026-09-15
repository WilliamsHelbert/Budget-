# -*- coding: utf-8 -*-
import sys, os, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
def go(lf):
    import model; importlib.reload(model)
    model.BASE=SP+"/dbfull"; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,sig,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
        conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
        max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
        conf_now=True, daily_basis='NQ', daily_stop=-2.5, daily_target=3.75,
        be_src='liq', liq_piv=0, liq_from=lf)
    n = df[(df.asset=='NQ') & (df.side=='SHORT')].copy()
    s = pd.DataFrame(sig); s = s[s.status=="TAGET"][['ts','NQ_beref','NQ_bedist']]
    return n, s
A,_  = go(9*60+30)
B,sB = go(0)
ka=set(zip(A.day,A.entry_t)); kb=set(zip(B.day,B.entry_t))
B['ny'] = [k in (kb-ka) for k in zip(B.day,B.entry_t)]
e = B[B.ny]
print("85-tjek: %d nye handler, R %+.2f, af dem BE %d / SL %d / TP %d"
      % (len(e), e.R.sum(), (e.reason=='BE').sum(), (e.reason=='SL').sum(), (e.reason=='TP').sum()))
# find BE-niveauets afstand for de nye
B['be_afst'] = B.entry - B.stop.where(B.moved_be, np.nan)
print("\nBE-afstand (entry til BE-niveau) fra signalloggen:")
sB['t'] = pd.to_datetime(sB.ts, unit='s', utc=True).dt.tz_convert('America/New_York')
m = sB[sB.NQ_bedist.notna()]
print("  alle taget: median %.1f pt, 25%% %.1f, 75%% %.1f" %
      (m.NQ_bedist.median(), m.NQ_bedist.quantile(.25), m.NQ_bedist.quantile(.75)))
B.to_csv(SP+"/eq_endelig.csv", index=False)
print("\ngemt eq_endelig.csv:", len(B), "handler")
