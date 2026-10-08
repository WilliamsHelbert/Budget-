import json,sys,pandas as pd
exec(open('simlim.py').read().split('\nfor lim')[0].split("s=maxday")[0])
def st(t):
    eq=t.R.cumsum(); return dict(R=round(t.R.sum(),1),DD=round((eq-eq.cummax()).min(),1),blow10=len(blows(t,10)),blow20=len(blows(t,20)),**{y:round(t[t.dato.str[:4]==y].R.sum(),1) for y in ('2023','2024','2025','2026')})
src=open('cmpfinal.py').read().split('# Vergence 2025')[0]
rows=[]
for k in sys.argv[1].split(','):
    s=maxday(stopwin(load('s_'+k,'SMT')),2); v=maxday(stopwin(load('v_'+k,'VRG')),2); sf=eqfilter(s,30)
    both=pd.concat([sf,v],ignore_index=True).sort_values(['dato','tid'])
    import io,contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        import os; os.environ['SV']='s_'+k; os.environ['VV']='v_'+k
        g={}; exec(src,g)
    O=g['OUT']
    for m,t in (('SMT f30',sf),('Vergence',v),('Begge',both)):
        r=dict(var=k,model=m,**st(t))
        if m!='Begge':
            o=O['SMT' if m=='SMT f30' else 'Vergence']['st']; r.update(match=f"{o['match']}/{o['u_n']}",same=o['same'],ekstra=f"{o['ex_n']} ({o['ex_R']:+})")
        rows.append(r)
print(pd.DataFrame(rows).to_string(index=False))
