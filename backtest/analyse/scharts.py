import sys, json, pandas as pd
S='/tmp/claude-0/-home-user-Budget-/bf318d68-665f-5f21-b1c8-ad7ac58fdc7e/scratchpad/'
sys.path.insert(0,'/home/user/Budget-/backtest'); import smt_backtest as s
from vcharts import bars
ex=json.load(open(S+'cmpall.json'))['SMT']['extra']
days=sorted({e['dato'] for e in ex})
s.SNAP={}; s.DBG=set(days); s.LOG=[]
tr,_=s.run(S+'NQ_2026_full.parquet',S+'ES_2026_full.parquet','2026-01-01','2026-09-11')
full={(r['dato'],r['tid']):r for r in tr if r['status']=='OK'}
N=bars(S+'NQ_2026_full.parquet',None); E=bars(S+'ES_2026_full.parquet',None)
out=[]
for e in ex:
    r=full[(e['dato'],e['tid'])]; day=e['dato']
    a=N.loc[day+' 09:15':day+' 09:59:59']; b=E.loc[day+' 09:15':day+' 09:59:59']
    fx=lambda df:[[round(v/4,2) for v in row] for row in df[['open','high','low','close']].values.tolist()]
    logs=[l[1]+' '+l[2] for l in s.LOG if l[0]==day and 'STATUS' not in l[2]]
    out.append(dict(yr='2026',model='SMT',**{k:r.get(k) for k in ('dato','tid','retning','niveau','swept','entry','sl','tp','be','be_kilde','tp_kilde','resultat','R','sl_pts')},vinfo='',
        nq=fx(a),es=fx(b),esT=[t.strftime('%H:%M:%S') for t in b.index],nqT=[t.strftime('%H:%M:%S') for t in a.index],lv=s.SNAP.get(day),log=logs))
json.dump(out,open(S+'scharts.json','w'),default=str); print(len(out))
