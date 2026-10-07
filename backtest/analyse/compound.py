import pandas as pd
exec(open('simlim.py').read().split('\nfor lim')[0])
t=both.sort_values(['dato','tid']).reset_index(drop=True)
rows=[]
for p in (0.02,0.025,0.03,0.04,0.05):
    b=10000; pk=b; dd=0; ye={}; low=b
    for d,r in zip(t.dato,t.R):
        b*=1+p*r; pk=max(pk,b); dd=min(dd,b/pk-1); low=min(low,b); ye[d[:4]]=b
    rows.append(dict(risiko=f'{p*100:g}%',slut=round(b),maxDD=f'{dd*100:.1f}%',laveste=round(low),**{f'ult {y}':round(v) for y,v in ye.items()}))
print(pd.DataFrame(rows).to_string(index=False)); print(len(t), t.dato.min(), t.dato.max())
for p in (0.02,0.05):
    b=10000; pk=b; pkd=None; best=(0,None,None,0,0)
    for d,r in zip(t.dato,t.R):
        b*=1+p*r
        if b>pk: pk,pkd=b,d
        if b/pk-1<best[0]: best=(b/pk-1,pkd,d,round(pk),round(b))
    print(p,best)
