import json,pandas as pd
U='/root/.claude/uploads/bf318d68-665f-5f21-b1c8-ad7ac58fdc7e/'
END='2026-09-11'
n=json.load(open(U+'310a2c55-trading_journal_2026-10-06.json'))
def jl(t):
    r=[]
    for x in n:
        if x['type']!=t: continue
        dd,mm,yy=x['date'].split('-'); c=x.get('custom',{})
        r.append(dict(dato=f'{yy}-{mm}-{dd}',min=x['entry'],dir=x['dir'].upper(),r=x['r'],be=c.get('col_1782162121195_z91f'),snap=x.get('snapshot')))
    return pd.DataFrame(r)
def bt(v):
    d=pd.DataFrame(json.load(open(f'res_2026_{v}.json'))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); d['min']=d.tid.str[:5]; return d.reset_index(drop=True)
cl=lambda v: None if isinstance(v,float) and v!=v else (v.item() if hasattr(v,'item') else v)
OUT={}
for nm,t,v in (('SMT','SMT','s_tid2'),('Vergence','Vergence','v_tid2')):
    u=jl(t); late=u[u.dato>END]; u=u[u.dato<=END]; b=bt(v)
    used=set(); rows=[]
    for r in u.itertuples():
        c=b[(b.dato==r.dato)&(~b.index.isin(used))]; c=c[c['min'].map(lambda m: m[:2]==r.min[:2] and abs(int(m[3:])-int(r.min[3:]))<=1)]
        if len(c):
            x=c.iloc[0]; used.add(x.name)
            same=(r.r>0)==(x.R>0) and (abs(r.r)<0.05)==(x.resultat=='BE')
            rows.append(dict(dato=r.dato,min=r.min,dir=r.dir,r=r.r,be_u=r.be,tid=x.tid,res=x.resultat,R=cl(x.R),be=x.be_kilde,niv=x.niveau,ok=True,same=bool(same)))
        else: rows.append(dict(dato=r.dato,min=r.min,dir=r.dir,r=r.r,be_u=r.be,ok=False,same=False))
    ex=b[~b.index.isin(used)]
    exl=[{k:cl(x) for k,x in e.items()} for e in ex[['dato','tid','retning','niveau','swept','sl_pts','be_kilde','resultat','R']].to_dict('records')]
    mon={}
    for m in sorted(set(u.dato.str[:7])|set(b.dato.str[:7])):
        mon[m]=dict(u_n=int((u.dato.str[:7]==m).sum()),u_R=round(float(u[u.dato.str[:7]==m].r.sum()),1),b_n=int((b.dato.str[:7]==m).sum()),b_R=round(float(b[b.dato.str[:7]==m].R.sum()),1))
    OUT[nm]=dict(rows=rows,extra=exl,mon=mon,late=dict(n=len(late),R=round(float(late.r.sum()),1)),
        st=dict(u_n=len(u),u_R=round(float(u.r.sum()),1),b_n=len(b),b_R=round(float(b.R.sum()),1),match=sum(x['ok'] for x in rows),same=sum(x['same'] for x in rows),
                miss=sum(not x['ok'] for x in rows),ex_n=len(exl),ex_R=round(float(ex.R.sum()),1)))
    s=OUT[nm]['st']; print(nm,s)
    print('  kun dig',[ (x['dato'],x['min'],x['r']) for x in rows if not x['ok']]); print('  diff',[(x['dato'],x['min'],x['r'],x['res'],x['R'],x['be']) for x in rows if x['ok'] and not x['same']])
json.dump(OUT,open('cmpall_tid2.json','w'),ensure_ascii=False)
