import pandas as pd
exec(open('simnr.py').read().split('\nrows=[]')[0])
def blows(t,lim):
    peak=cur=0; b=[]; 
    for d,r in zip(t.dato,t.R):
        cur+=r; peak=max(peak,cur)
        if cur<=peak-lim: b.append(d); peak=cur=0
    return b
s=maxday(stopwin(load('s_pm','SMT')),2); v=maxday(stopwin(load('v_pm','VRG')),2); sf=eqfilter(s,30)
both=pd.concat([sf,v],ignore_index=True).sort_values(['dato','tid'])
for lim in (10,15,20,22.5,25):
    print(lim, {m:(len(b:=blows(t,lim)),b) for m,t in (('SMT f30',sf),('Vergence',v),('Begge',both))})
