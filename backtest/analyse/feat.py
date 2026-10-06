import pandas as pd, numpy as np
U='/root/.claude/uploads/bf318d68-665f-5f21-b1c8-ad7ac58fdc7e/'
F=[U+'017f8173-NQ_2023.parquet','NQ_2024_full.parquet',U+'c485f661-NQ_2025_1.parquet','NQ_2026_full.parquet']
rows={}
for f in F:
    d=pd.read_parquet(f); t=pd.to_datetime(d.ts,unit='s',utc=True) if not str(d.ts.dtype).startswith('datetime') else d.ts
    if t.dt.tz is None: t=t.dt.tz_localize('UTC')
    t=t.dt.tz_convert('America/New_York')
    x=pd.DataFrame({'t':t,'h':d.high.values/4,'l':d.low.values/4,'o':d.open.values/4,'c':d.close.values/4})
    x['m']=x.t.dt.hour*60+x.t.dt.minute
    x['td']=(x.t+pd.Timedelta(hours=6)).dt.date   # handelsdag starter 18:00
    for dd,g in x.groupby('td'):
        rth=g[(g.m>=570)&(g.m<960)]; on=g[(g.m>=1080)|(g.m<570)]; pre=g[(g.m>=480)&(g.m<570)]
        if len(rth)<100 or len(pre)==0: continue
        p=rth.o.iloc[0]
        rows[str(dd)]=dict(px=p,rthR=(rth.h.max()-rth.l.min())/p*100,onR=(on.h.max()-on.l.min())/p*100,preR=(pre.h.max()-pre.l.min())/p*100,
                           fullR=(g.h.max()-g.l.min())/p*100, rthMove=abs(rth.c.iloc[-1]-p)/p*100)
D=pd.DataFrame(rows).T.sort_index(); D=D[~D.index.duplicated()]
D['adr20']=D.fullR.rolling(20,min_periods=5).mean().shift(1)
D['rth20']=D.rthR.rolling(20,min_periods=5).mean().shift(1)
D['move20']=D.rthMove.rolling(20,min_periods=5).mean().shift(1)
D['prevR']=D.rthR.shift(1)
D.to_pickle('dayfeat.pkl'); print(D.groupby(D.index.str[:4])[['rthR','adr20','onR','preR','move20']].median().round(3))
