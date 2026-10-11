"""Opsummering pr. periode og eksekverings-symbol (R efter 1 tick slippage ind/ud + 4,50 USD kommission)."""
import pandas as pd, numpy as np, sys
PV={'ES':50,'NQ':20}
def stats(t,ex):
    risk=(t.entry-t.sl).abs()
    cost=(2*0.25*PV[ex]+4.5)/(risk*PV[ex]); Rn=t.R-cost
    cum=Rn.cumsum(); dd=(cum-cum.cummax()).min()
    m=t.day.str[:7]; mon=Rn.groupby(m).sum()
    return dict(trades=len(t),win=f"{100*(t.R>0).mean():.0f}%",sumR=round(t.R.sum(),1),netR=round(Rn.sum(),1),
                pr_trade=round(t.R.mean(),3),se=round(t.R.std()/np.sqrt(len(t)),3),net_pr_trade=round(Rn.mean(),3),
                medSL=round(risk.median(),1),cost=round(cost.mean(),2),maxDD=round(dd,1),
                pos_mdr=f"{(mon>0).sum()}/{len(mon)}",long=round(Rn[t.dir=='LONG'].sum(),1),short=round(Rn[t.dir=='SHORT'].sum(),1),
                tp4h=round(Rn[t.tp_name.fillna('').str.startswith('4h')].sum(),1))
rows=[]
for y in ['2023','2024','2025','2026']:
    for ex in ['ES','NQ']:
        d=pd.read_csv(f'results/{y}_trades_{ex}.csv'); t=d[d.status=='Handlet']
        rows.append(dict(periode=y,exec=ex,**stats(t,ex)))
for ex in ['ES','NQ']:
    t=pd.concat([pd.read_csv(f'results/{y}_trades_{ex}.csv') for y in ['2023','2024','2025','2026']]); t=t[t.status=='Handlet']
    rows.append(dict(periode='ALLE',exec=ex,**stats(t,ex)))
df=pd.DataFrame(rows); pd.set_option('display.width',250)
print(df.to_string(index=False))
if len(sys.argv)>1:
    for ex in ['ES','NQ']:
        d=pd.read_csv(f'results/{sys.argv[1]}_trades_{ex}.csv'); t=d[d.status=='Handlet']
        risk=(t.entry-t.sl).abs(); Rn=t.R-(2*0.25*PV[ex]+4.5)/(risk*PV[ex])
        print(ex,sys.argv[1],'pr måned netto:',Rn.groupby(t.day.str[:7]).sum().round(1).to_dict())
