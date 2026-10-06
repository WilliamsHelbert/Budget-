import pandas as pd
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
for k in ('pm','noreset'):
    s=maxday(stopwin(load('s_'+k,'SMT')),2); v=maxday(stopwin(load('v_'+k,'VRG')),2); sf=eqfilter(s,30)
    for m,t in (('SMT',s),('SMT filter30',sf),('Vergence',v),('SMT f30 + Vergence',pd.concat([sf,v],ignore_index=True).sort_values(['dato','tid']))):
        rows.append(dict(var=k,model=m,**stats(t)))
print(pd.DataFrame(rows).to_string(index=False))
