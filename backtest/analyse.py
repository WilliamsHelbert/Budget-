"""Hvilke regler koster / misser R? Kører på alle setups (ES-eksekvering) 2023-2026.
Brug: python3 analyse.py DATA_DIR  -> results/analyse_setups.csv (MFE, faste RR-udfald, omkostning m.m.)"""
import sys, re, numpy as np, pandas as pd
sys.path.insert(0,'.')
import continuation_model as cm
cm.DATA_DIR=sys.argv[1]
TZ='Europe/Copenhagen'; NY='America/New_York'
d=pd.concat([pd.read_csv(f'results/{y}_trades_ES.csv',dtype={'entry_t':str,'sweep_t':str,'exit_t':str}) for y in ['2023','2024','2025','2026']],ignore_index=True)
es=cm.load('ES')
cost_pt=2*0.25+4.5/50
rows=[]
for r in d.itertuples():
    et=pd.Timestamp(f'{r.day} {r.entry_t}',tz=TZ)
    ex=pd.Timestamp(f'{r.day} 16:00',tz=NY).tz_convert(TZ)
    sgn=1 if r.dir=='LONG' else -1
    risk=sgn*(r.entry-r.sl)
    w=es[(es.index>=et)&(es.index<ex)]
    fav=(w.high-r.entry) if sgn>0 else (r.entry-w.low)
    adv=(r.entry-w.low) if sgn>0 else (w.high-r.entry)
    hit_sl=np.where(adv.values>=risk)[0]; isl=hit_sl[0] if len(hit_sl) else len(w)
    mfe=fav.values[:isl+1].max()/risk if len(w) else 0        # max gevinst foer SL (i R)
    out={}
    for k in (1,1.5,2,3):
        hit=np.where(fav.values[:isl+1]>=k*risk)[0]
        # samme 15s-bar som SL taeller som tab
        out[k]=k if len(hit) and (hit[0]<isl) else (-1 if isl<len(w) else (sgn*(w.close.iloc[-1]-r.entry)/risk if len(w) else 0))
    rows.append(dict(i=r.Index,risk=risk,mfe=mfe,R1=out[1],R15=out[1.5],R2=out[2],R3=out[3],
                     cost=cost_pt/risk, mins=(et-pd.Timestamp(f'{r.day} 09:30',tz=NY).tz_convert(TZ)).total_seconds()/60,
                     sweep_age=(et-pd.Timestamp(f'{r.day} {r.sweep_t}',tz=TZ)).total_seconds()/60,
                     rr=(sgn*(r.tp-r.entry)/risk) if r.tp==r.tp else np.nan))
a=pd.concat([d,pd.DataFrame(rows).set_index('i')],axis=1)
a.loc[:,~a.columns.duplicated(keep='last')].to_csv('results/analyse_setups.csv',index=False); print('ok',len(a))
