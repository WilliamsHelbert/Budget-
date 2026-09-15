# -*- coding: utf-8 -*-
import sys, os, math, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40}, be_min={'ES':0.25,'NQ':2.0},
           conf_now=True, be_src='liq', liq_piv=0, liq_from=0,
           sides=('bear',))          # LONGS HELT UDE
def go(folder):
    import model; importlib.reload(model)
    model.BASE=SP+"/"+folder; model.TZ="America/New_York"
    model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, **CFG)
    # saml de to ben paa samme handel side om side
    nq = df[df.asset=='NQ'].set_index('id')
    es = df[df.asset=='ES'].set_index('id')
    a = nq.join(es[['entry','stop','tp','exit','reason','R']], rsuffix='_es', how='left')
    a = a.reset_index()
    dk=pd.to_datetime(a.entry_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    xd=pd.to_datetime(a.exit_t).dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    a['t']=dk.dt.strftime('%H:%M:%S'); a['x']=xd.dt.strftime('%H:%M:%S'); a['mnd']=a.day.str[:7]
    a['kilde']=folder
    return a.sort_values('id')
db  = go("dbfull")
ven = go("vendata"); ven = ven[ven.day>="2026-03-01"]
alle = pd.concat([db,ven], ignore_index=True).sort_values(['day','entry_t']).reset_index(drop=True)
alle['akk']    = alle.R.cumsum()
alle['akk_es'] = alle.R_es.cumsum()
alle.to_csv(SP+"/eq_shorts_final.csv", index=False)
def st(r, lbl):
    r=np.asarray(r); e=np.cumsum(r)
    print("%-22s n %3d | R %+8.2f | pr.h %+5.2f | maxDD %+7.2f | t %+5.2f"
          % (lbl,len(r),r.sum(),r.mean(),(e-np.maximum.accumulate(e)).min(),
             r.mean()*math.sqrt(len(r))/r.std()))
print("=== KUN SHORTS | intet dagsstop | SL paa EQ-toppen | BE = naermeste levende 5m-liq | 8/40 ===")
print("nov 2024 - sep 2026")
st(alle.R.values, "NQ")
st(alle.R_es.dropna().values, "ES")
print("\nudfald NQ:", alle.reason.value_counts().to_dict())
print("udfald ES:", alle.reason_es.value_counts().to_dict())
print("\n--- aar for aar (NQ / ES) ---")
for lbl, sel in (("2024 nov-dec", alle.mnd<"2025-01"), ("2025",(alle.mnd>="2025-01")&(alle.mnd<"2026-01")),
                 ("2026 jan-sep", alle.mnd>="2026-01")):
    g=alle[sel]
    print("%-14s n %3d | NQ %+8.2f | ES %+8.2f" % (lbl, len(g), g.R.sum(), g.R_es.sum()))
print("\n--- maaned for maaned ---")
m = alle.groupby('mnd').agg(n=('R','size'), NQ=('R','sum'), ES=('R_es','sum'),
      TP=('reason',lambda s:(s=='TP').sum()), SL=('reason',lambda s:(s=='SL').sum()),
      BE=('reason',lambda s:(s=='BE').sum())).round(2)
print(m.to_string())
print("\n--- 13. november 2024 ---")
print(alle[alle.day=="2024-11-13"][['day','t','entry','stop','tp','exit','reason','R','entry_es','reason_es','R_es']].to_string(index=False))
