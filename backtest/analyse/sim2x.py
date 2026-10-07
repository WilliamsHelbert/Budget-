import pandas as pd
exec(open('simlim.py').read().split('\nfor lim')[0])
s2=sf.copy(); s2['R']=s2.R*2
def st(t):
    eq=t.R.cumsum(); yr={y:round(t[t.dato.str[:4]==y].R.sum(),1) for y in ('2023','2024','2025','2026')}
    mon=t.groupby(t.dato.str[:7]).R.sum(); 
    return dict(n=len(t),R=round(t.R.sum(),1),DD=round((eq-eq.cummax()).min(),1),**yr,minus_mdr=int((mon<0).sum()),vaerste_md=round(mon.min(),1),
        **{f'blow{l}':len(blows(t,l)) for l in (10,15,20,22.5,30)})
rows={'SMT f30 1x + Vergence 1x':st(both),'SMT f30 1x alene':st(sf),'SMT f30 2x alene':st(s2),'SMT f30 2x + Vergence 1x':st(pd.concat([s2,v]).sort_values(['dato','tid']))}
print(pd.DataFrame(rows).T.to_string())
print({l:blows(s2,l) for l in (10,15,20,22.5)})
