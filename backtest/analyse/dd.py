import json,os,pandas as pd,sys
def load(v):
    parts=[]
    for y in ('2023','2024','2025','2026'):
        f=f'res_{y}_{v}.json'
        if not os.path.exists(f): return None
        d=pd.DataFrame(json.load(open(f))); d=d[d.status=='OK'].copy(); d['R']=d.R.fillna(0); parts.append(d)
    return pd.concat(parts).sort_values(['dato','tid'])
def stats(d,lim=10):
    eq=d.R.cumsum(); dd=(eq-eq.cummax()).min()
    # blow: -lim fra toppen -> ny konto (start forfra)
    peak=cur=0; blows=[]; 
    for x in d.itertuples():
        cur+=x.R; peak=max(peak,cur)
        if cur<=peak-lim: blows.append(x.dato); peak=cur=0
    # loengste periode under top (dage)
    return dict(trades=len(d),R=round(d.R.sum(),1),maxDD=round(dd,1),blows=len(blows),blow_datoer=', '.join(b[:7] for b in blows))
for v in sys.argv[1:]:
    d=load(v)
    if d is None: print(v,'mangler'); continue
    s=stats(d); print(v, {k:s[k] for k in ('trades','R','maxDD','blows')}); print('   blows:',s['blow_datoer'])
    for y in ('2023','2024','2025','2026'):
        dy=d[d.dato.str.startswith(y)]; sy=stats(dy); print('  ',y,{k:sy[k] for k in ('trades','R','maxDD','blows')})
