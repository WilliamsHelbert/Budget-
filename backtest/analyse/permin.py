import json,sys,pandas as pd
def load(v):
    p=[]
    for y in ('2023','2024','2025','2026'):
        d=pd.DataFrame(json.load(open(f'res_{y}_{v}.json'))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); d['y']=y; p.append(d)
    return pd.concat(p,ignore_index=True)
v=sys.argv[1]; d=load(v)
m=d.tid.str[:5]
b=pd.Series(pd.cut(d.tid.str[3:5].astype(int)+60*(d.tid.str[:2].astype(int)-15),[29,30,31,32,33,35,39,44,49,59,60,75,90,120],labels=['15:30','15:31','15:32','15:33','15:34-35','15:36-39','15:40-44','15:45-49','15:50-59','16:00','16:01-15','16:16-30','16:31-59']))
t=d.groupby([b,'y'],observed=False).R.sum().unstack().round(1)
t['alle R']=d.groupby(b,observed=False).R.sum().round(1); t['n']=d.groupby(b,observed=False).size()
t['R/trade']=(t['alle R']/t.n).round(2); t['win%']=(d.groupby(b,observed=False).R.apply(lambda s:(s>0).mean())*100).round(0)
print(v); print(t.to_string())
