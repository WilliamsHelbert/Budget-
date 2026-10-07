import pandas as pd
exec(open('compound.py').read().split('\nrows=[]')[0])
months=pd.period_range('2023-06','2026-09',freq='M')
ev=[(d,r) for d,r in zip(t.dato,t.R)]
# +7R pr. maaned: halvdelen midt i maaneden, halvdelen sidst (approx jaevnt fordelt)
for m in months:
    ev.append((f'{m}-15z',3.5)); ev.append((f'{m}-31z',3.5))
ev.sort()
rows=[]
for p in (0.02,0.025,0.03,0.04,0.05):
    b=10000; pk=b; dd=0; low=b; ye={}; pkd=None; ddw=None
    for d,r in ev:
        if d>'2026-09-11z': continue
        b*=1+p*r
        if b>pk: pk,pkd=b,d
        if b/pk-1<dd: dd,ddw=b/pk-1,(pkd[:7],d[:7])
        low=min(low,b); ye[d[:4]]=b
    rows.append(dict(risiko=f'{p*100:g}%',slut=round(b),maxDD=f'{dd*100:.1f}%',laveste=round(low),**{f'ult {y}':round(v) for y,v in ye.items()},dd_periode=ddw))
print(pd.DataFrame(rows).to_string(index=False))
print('R i alt', round(sum(r for d,r in ev if d<='2026-09-11z'),1))
