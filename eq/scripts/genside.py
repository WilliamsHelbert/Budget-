# -*- coding: utf-8 -*-
import json, math, datetime, numpy as np, pandas as pd
MINUS="−"
def dk(x,n=2,s=True):
    if x is None or (isinstance(x,float) and math.isnan(x)): return "–"
    if abs(x)<0.005: return "0,"+"0"*n
    return (("%+.*f" if s else "%.*f")%(n,x)).replace('.',',').replace('-',MINUS)
def dkp(x,n=2): return dk(x,n,False)
def cl(x): return "pos" if x>0.005 else ("neg" if x<-0.005 else "flat")
MND={1:"januar",2:"februar",3:"marts",4:"april",5:"maj",6:"juni",7:"juli",8:"august",9:"september"}
UGE=["mandag","tirsdag","onsdag","torsdag","fredag","lørdag","søndag"]

def load(tag,v):
    d = pd.read_csv(f'/tmp/D_{tag}_{v}.csv')
    d['m'] = d.day.str[5:7].astype(int)
    return d.sort_values('id').reset_index(drop=True)

def agg(g):
    if not len(g): return dict(n=0,R=0.0,Rr=0.0,tp=0,w=0,l=0,z=0)
    return dict(n=len(g), R=float(g.R.sum()), Rr=float(g.Rr.sum()),
                tp=int((g.reason=='TP').sum()),
                w=int((g.R>0.005).sum()), l=int((g.R<-0.005).sum()),
                z=int((g.R.abs()<=0.005).sum()))
def tval(g):
    r=g.R.values
    if len(r)<2 or r.std()==0: return float('nan')
    return float(r.mean()*math.sqrt(len(r))/r.std())

DATA={}
for tag in ("1600","1630"):
    nor=load(tag,"normal"); bear=load(tag,"bear"); bull=load(tag,"bull")
    A = nor[nor.side=='SHORT']; L = nor[nor.side=='LONG']
    rows=[]
    for m in range(1,10):
        rows.append(dict(m=m, navn=MND[m],
            nor=agg(nor[nor.m==m]), lng=agg(L[L.m==m]), sht=agg(A[A.m==m]),
            B=agg(bear[bear.m==m]), Bull=agg(bull[bull.m==m]),
            dage=int(nor[nor.m==m].day.nunique())))
    tot=dict(nor=agg(nor), lng=agg(L), sht=agg(A), B=agg(bear), Bull=agg(bull),
             dage=int(nor.day.nunique()),
             t_nor=tval(nor), t_sht=tval(A), t_B=tval(bear), t_lng=tval(L), t_Bull=tval(bull))
    for k,g in (("nor",nor),("sht",A),("B",bear),("lng",L),("Bull",bull)):
        r=g.sort_values('id').R.values; e=np.cumsum(r)
        tot["dd_"+k]=float((e-np.maximum.accumulate(e)).min()) if len(r) else 0.0
        o=g[g.day<"2026-08-12"]
        tot["oos_"+k]=dict(n=len(o), R=float(o.R.sum()),
                           pr=float(o.R.mean()) if len(o) else 0.0, t=tval(o))
    # handelsliste (normal-koersel), mdr -> handler
    inB = set(zip(bear.day, bear.entry_t))
    liste={}
    for m in range(1,10):
        ts=[]
        for r in nor[nor.m==m].itertuples():
            ts.append(dict(dag=r.day, ugedag=UGE[datetime.date.fromisoformat(r.day).weekday()],
                dk=r.entry_t_dk[:5], ny=r.entry_t[11:16], side=r.side, trig=r.trigger_asset,
                entry=float(r.entry), stop=float(r.stop), tp=float(r.tp), exit=float(r.exit),
                exit_dk=r.exit_t_dk[:5], reason=r.reason, be=bool(r.moved_be),
                sd=float(r.stop_dist), R=float(r.R), Rr=float(r.Rr),
                inB=(r.day, r.entry_t) in inB))
        liste[m]=ts
    DATA[tag]=dict(rows=rows, tot=tot, liste=liste)
json.dump(DATA, open('/tmp/side.json','w'))
for tag in ("1600","1630"):
    t=DATA[tag]['tot']
    print(tag, "normal", t['nor']['n'], round(t['nor']['R'],2),
          "| shorts", t['sht']['n'], round(t['sht']['R'],2),
          "| longs", t['lng']['n'], round(t['lng']['R'],2),
          "| B", t['B']['n'], round(t['B']['R'],2))
