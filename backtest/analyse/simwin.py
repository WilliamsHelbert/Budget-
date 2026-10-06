import re,pandas as pd
src=open('sim.py').read().split('rows=[]')[0]
src=src.replace("S=load('base','SMT'); V=load('vrg30','VRG')","S=load('s_pm','SMT'); V=load('v_pm','VRG')")
exec(src)
def stopwin(t):
    t=t.sort_values(['dato','tid']); keep=[]; done=set()
    for i,r in t.iterrows():
        k=(r.dato,r.model)
        if k in done: continue
        keep.append(i)
        if r.R>0: done.add(k)
    return t.loc[keep]
rows=[]
for nm,f in (('Max 2/dag',lambda t: maxday(t,2)),('Max 2/dag + stop efter win',lambda t: maxday(stopwin(t),2))):
    s=f(S); v=f(V); sf=eqfilter(s,30)
    for m,t in (('SMT',s),('SMT filter30',sf),('Vergence',v),('SMT f30 + Vergence',pd.concat([sf,v],ignore_index=True).sort_values(['dato','tid']))):
        rows.append(dict(regel=nm,model=m,**stats(t)))
print(pd.DataFrame(rows).to_string(index=False))
s=maxday(S,2); w=maxday(stopwin(S),2); x=s.loc[~s.index.isin(w.index)]; print('SMT fjernet',len(x),x.R.sum().round(1)); print(x[x.dato.str[:4]=='2026'][['dato','tid','R']].to_string())
v=maxday(V,2); w=maxday(stopwin(V),2); x=v.loc[~v.index.isin(w.index)]; print('VRG fjernet',len(x),x.R.sum().round(1)); print(x[x.dato.str[:4]=='2026'][['dato','tid','R']].to_string())
