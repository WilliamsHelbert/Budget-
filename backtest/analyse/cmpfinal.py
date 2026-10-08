import json,pandas as pd
src=open('cmpall_pm.py').read()
src=src.replace("""def bt(v):
    d=pd.DataFrame(json.load(open(f'res_2026_{v}.json'))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); d['min']=d.tid.str[:5]; return d.reset_index(drop=True)""",
"""def rules(d):
    d=d.sort_values(['dato','tid']); keep=[]; win=set(); cnt={}
    for i,r in d.iterrows():
        if r.dato in win or cnt.get(r.dato,0)>=2: continue
        keep.append(i); cnt[r.dato]=cnt.get(r.dato,0)+1
        if r.R>0: win.add(r.dato)
    return d.loc[keep]
def bt(v,y='2026'):
    d=pd.DataFrame(json.load(open(f'res_{y}_{v}.json'))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); d['min']=d.tid.str[:5]; return rules(d).reset_index(drop=True)""")
src=src.replace("cmpall_pm.json","cmpfinal.json").replace("json.dump(OUT","OUTX=OUT\n#json.dump(OUT")
exec(src)
# Vergence 2025 (2/1-7/3)
u=pd.read_pickle('vjournal2025.pkl'); b=bt('v_path','2025'); b=b[b.dato<='2025-03-07'].reset_index(drop=True)
used=set(); miss=[]; diff=[]
for r in u.itertuples():
    c=b[(b.dato==r.dato)&(~b.index.isin(used))]; c=c[c['min'].map(lambda m: m[:2]==r.min[:2] and abs(int(m[3:])-int(r.min[3:]))<=1)]
    if len(c):
        x=c.iloc[0]; used.add(x.name)
        if not ((r.r>0)==(x.R>0) and (abs(r.r)<0.05)==(x.resultat=='BE')): diff.append(dict(dato=r.dato,min=r.min,r=r.r,res=x.resultat,R=cl(x.R),be=x.be_kilde))
    else: miss.append(dict(dato=r.dato,min=r.min,r=r.r))
ex=b[~b.index.isin(used)]
OUT['V2025']=dict(extra=[{k:cl(x) for k,x in e.items()} for e in ex[['dato','tid','retning','niveau','swept','sl_pts','be_kilde','resultat','R']].to_dict('records')],miss=miss,diff=diff,u_n=len(u),u_R=round(float(u.r.sum()),1))
print('V2025',len(OUT['V2025']['extra']),miss,diff)
json.dump(OUT,open('cmpfinal.json','w'),ensure_ascii=False)
