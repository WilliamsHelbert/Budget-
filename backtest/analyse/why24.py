import json,pandas as pd,numpy as np
U='/root/.claude/uploads/bf318d68-665f-5f21-b1c8-ad7ac58fdc7e/'
F={'2023':U+'017f8173-NQ_2023.parquet','2024':'NQ_2024_full.parquet','2025':U+'c485f661-NQ_2025_1.parquet','2026':'NQ_2026_full.parquet'}
def daily(f):
    d=pd.read_parquet(f); t=pd.to_datetime(d.ts,unit='s',utc=True) if not str(d.ts.dtype).startswith('datetime') else d.ts
    if t.dt.tz is None: t=t.dt.tz_localize('UTC')
    t=t.dt.tz_convert('America/New_York'); m=t.dt.hour*60+t.dt.minute; day=t.dt.date
    x=pd.DataFrame({'day':day,'m':m,'o':d.open/4,'h':d.high/4,'l':d.low/4,'c':d.close/4})
    out={}
    for dd,g in x.groupby('day'):
        pre=g[(g.m>=480)&(g.m<570)]; op=g[g.m>=570]; win=g[(g.m>=570)&(g.m<600)]; aft=g[(g.m>=600)&(g.m<960)]
        if len(op)==0 or len(pre)==0: continue
        out[str(dd)]=dict(preR=pre.h.max()-pre.l.min(), open=op.o.iloc[0], winR=win.h.max()-win.l.min() if len(win) else np.nan,
            day_move=(aft.c.iloc[-1]-op.o.iloc[0]) if len(aft) else np.nan, win_move=(win.c.iloc[-1]-win.o.iloc[0]) if len(win) else np.nan)
    return pd.DataFrame(out).T
rows=[]
for y,f in F.items():
    D=daily(f)
    r=pd.DataFrame(json.load(open(f'res_{y}_base.json'))); r=r[r.status=='OK'].copy(); r['R']=r.R.fillna(0); r['y']=y
    r=r.join(D,on='dato')
    rows.append(r)
d=pd.concat(rows)
d['m']=d.tid.str[3:5].astype(int); d['t']=np.where(d.m==30,'15:30','senere')
d['sh']=d.retning=='SHORT'
d['mod_dag']=np.where(d.sh, d.day_move>0, d.day_move<0)   # trade mod resten af dagens bevaegelse (efter 10:00)
d['win']=d.R>0
pd.set_option('display.width',220)
print(d.groupby('y').agg(n=('R','size'),R=('R','sum'),win=('win','mean'),preR=('preR','median'),winR=('winR','median'),sl=('sl_pts','median'),
    open1530=('t',lambda s:(s=='15:30').mean())).round(2))
for c in ['t','retning','swept','tp_kilde']:
    print('\n==',c); print(d.pivot_table(index=c,columns='y',values='R',aggfunc=['count','sum']).round(1))
d['lvl']=d.niveau.str.split(' / ').str[0].str.replace(' high','').str.replace(' low','')
print('\n== niveau'); print(d.pivot_table(index='lvl',columns='y',values='R',aggfunc=['count','sum']).round(1))
d['preB']=pd.qcut(d.preR/d.open*1e4,3,labels=['lille','mellem','stor'])
print('\n== NY PRE range (relativ)'); print(d.pivot_table(index='preB',columns='y',values='R',aggfunc=['count','sum'],observed=False).round(1))
d['winB']=pd.qcut(d.winR/d.open*1e4,3,labels=['rolig','mellem','vild'])
print('\n== 15:30-16:00 range'); print(d.pivot_table(index='winB',columns='y',values='R',aggfunc=['count','sum'],observed=False).round(1))
d.to_pickle('why24.pkl')
