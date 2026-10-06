import json,pandas as pd,numpy as np
D=pd.read_pickle('dayfeat.pkl')
def load(v):
    p=[]
    for y in ('2023','2024','2025','2026'):
        d=pd.DataFrame(json.load(open(f'res_{y}_{v}.json'))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); p.append(d)
    d=pd.concat(p).sort_values(['dato','tid']).reset_index(drop=True); d['y']=d.dato.str[:4]
    return d.join(D,on='dato')
pd.set_option('display.width',250)
for v in ('base','vrg30'):
    d=load(v); print('=====',v)
    for c in ('adr20','rth20','move20','prevR','onR','preR'):
        q=pd.qcut(d[c],5,labels=['1 lav','2','3','4','5 høj'])
        t=d.groupby([q,'y'],observed=False).R.sum().unstack().round(1); t['alle']=d.groupby(q,observed=False).R.sum().round(1); t['n']=d.groupby(q,observed=False).size()
        print('--',c); print(t.to_string())
