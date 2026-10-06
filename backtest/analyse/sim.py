import json,pandas as pd,numpy as np
def load(v,m):
    p=[]
    for y in ('2023','2024','2025','2026'):
        d=pd.DataFrame(json.load(open(f'res_{y}_{v}.json'))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); p.append(d)
    d=pd.concat(p,ignore_index=True); d['model']=m; return d[['dato','tid','R','model','resultat']]
S=load('base','SMT'); V=load('vrg30','VRG')
days=sorted(set(pd.concat([S,V]).dato))
dix={d:i for i,d in enumerate(days)}
def stats(t):
    if len(t)==0: return dict(n=0,R=0,maxDD=0,blows=0)
    eq=t.R.cumsum(); peak=cur=0; b=0
    for r in t.R:
        cur+=r; peak=max(peak,cur)
        if cur<=peak-10: b+=1; peak=cur=0
    yr={y:round(t[t.dato.str.startswith(y)].R.sum(),1) for y in ('2023','2024','2025','2026')}
    return dict(n=len(t),R=round(t.R.sum(),1),maxDD=round((eq-eq.cummax()).min(),1),blows=b,**yr)
def maxday(t,k,by_model=True):
    t=t.sort_values(['dato','tid'])
    g=['dato','model'] if by_model else ['dato']
    return t[t.groupby(g).cumcount()<k]
def pause_streak(t,k,ndays):
    t=t.sort_values(['dato','tid']); keep=[]; st=0; until=-1
    for i,r in t.iterrows():
        if dix[r.dato]<=until: continue
        keep.append(i)
        st=st+1 if r.R<0 else (0 if r.R>0 else st)
        if st>=k: until=dix[r.dato]+ndays; st=0
    return t.loc[keep]
def pause_blow(t,ndays,lim=10):
    t=t.sort_values(['dato','tid']); keep=[]; peak=cur=0; until=-1
    for i,r in t.iterrows():
        if dix[r.dato]<=until: continue
        keep.append(i); cur+=r.R; peak=max(peak,cur)
        if cur<=peak-lim: until=dix[r.dato]+ndays; peak=cur=0
    return t.loc[keep]
def eqfilter(t,n):
    t=t.sort_values(['dato','tid']).copy(); sh=t.R.cumsum(); ma=sh.rolling(n,min_periods=n).mean()
    ok=(sh.shift(1)>=ma.shift(1))|ma.shift(1).isna()
    return t[ok.values]
rows=[]
for nm,base in (('SMT',S),('Vergence',V),('Begge',pd.concat([S,V],ignore_index=True))):
    b2=maxday(base,2)
    tests=[('Ingen grænse',base),('Max 2/dag pr. model',b2)]
    if nm=='Begge': tests.append(('Max 2/dag samlet',maxday(base,2,False)))
    for k in (3,4):
        for nd in (5,10): tests.append((f'Max 2/dag + pause {nd} dage efter {k} tab i træk',pause_streak(b2,k,nd)))
    for nd in (10,20): tests.append((f'Max 2/dag + pause {nd} dage efter blow',pause_blow(b2,nd)))
    for n in (10,20): tests.append((f'Max 2/dag + kun når kurven er over snit af {n} trades',eqfilter(b2,n)))
    for tn,t in tests: rows.append(dict(model=nm,regel=tn,**stats(t)))
r=pd.DataFrame(rows); pd.set_option('display.width',250); pd.set_option('display.max_colwidth',60)
print(r.to_string(index=False)); r.to_csv('sim.csv',index=False)
