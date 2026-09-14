# -*- coding: utf-8 -*-
import pandas as pd
d = pd.read_csv('/tmp/short55_full.csv')
MND={1:"JANUAR",2:"FEBRUAR",3:"MARTS",4:"APRIL",5:"MAJ",6:"JUNI",7:"JULI",8:"AUGUST",9:"SEPTEMBER"}
UGE=["MAN","TIR","ONS","TOR","FRE","LØR","SØN"]
import datetime
def dk(x):
    if abs(x)<0.005: return "  0,00"
    return ("%+6.2f" % x).replace('.',',')

W=88
def line(ch="═"): return "╔"+ch*(W-2)+"╗" if ch=="═" else "╠"+ch*(W-2)+"╣"
def pad(s,w): return s + " "*(w-len(s)) if len(s)<w else s[:w]

out=[]
out.append("╔"+"═"*(W-2)+"╗")
out.append("║"+pad("  EQ-KONFLUENS · KUN SHORTS · NQ-BENET · HELE 2026 (1. jan – 11. sep)",W-2)+"║")
out.append("║"+pad("  Vindue 15:30–16:30 dansk tid · longs spærrer pladsen men handles ikke",W-2)+"║")
out.append("╚"+"═"*(W-2)+"╝")

tot=0
for m in range(1,10):
    g=d[pd.to_datetime(d.dag).dt.month==m]
    if not len(g): continue
    mR=g.R.sum(); tot+=mR
    out.append("")
    out.append(" "+MND[m]+"  ·  %d handler  ·  %s R" % (len(g), dk(mR).strip()))
    out.append(" "+"─"*(W-4))
    for r in g.itertuples():
        dd=datetime.date.fromisoformat(r.dag)
        flag="!" if r.stop_dist>40 else " "
        out.append("  %s %s  %s→%s  entry %9.2f  stop %9.2f (%5.1fp)%s  %-2s  %s R"
                    % (UGE[dd.weekday()], dd.strftime('%d/%m'), r.t, r.x,
                       r.entry, r.stop, r.stop_dist, flag, r.reason, dk(r.R)))
out.append("")
out.append("╔"+"═"*(W-2)+"╗")
out.append("║"+pad("  I ALT: %d handler over %d handelsdage          NETTO %s R"
                    % (len(d), d.dag.nunique(), dk(tot).strip()), W-2)+"║")
out.append("╚"+"═"*(W-2)+"╝")
print("\n".join(out))
open('/tmp/short55_box.txt','w').write("\n".join(out))
