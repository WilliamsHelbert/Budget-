# -*- coding: utf-8 -*-
import sys, os, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
d = pd.read_parquet(SP+"/db2024/NQ.parquet")
t = pd.to_datetime(d.time, utc=True).dt.tz_convert("America/New_York")
sec = t.dt.tz_convert("UTC").dt.tz_localize(None).astype("datetime64[s]").astype("int64")
d = d.assign(day=t.dt.strftime("%Y-%m-%d"), ts=sec)
g = d[d.day=="2024-11-04"].sort_values("ts")
CUT = int(pd.Timestamp("2024-11-04 09:51:30", tz="America/New_York").timestamp())
ENT = 20116.0
m5 = {}
for ts,o,h,l,c in zip(g.ts,g.open,g.high,g.low,g.close):
    b = ts//300*300
    if b not in m5: m5[b]=[o,h,l,c]
    else:
        m5[b][1]=max(m5[b][1],h); m5[b][2]=min(m5[b][2],l); m5[b][3]=c
lv=[]
for b in sorted(m5):
    if b+300 > CUT: break
    o,h,l,c = m5[b]
    lv.append(dict(b=b, lvl=l, hi=False)); lv.append(dict(b=b, lvl=h, hi=True))
# doed-markering bar for bar
for m in lv: m['dead']=False; m['deadt']=None
for ts,h,l in zip(g.ts,g.high,g.low):
    if ts>CUT: break
    for m in lv:
        if ts < m['b']+300 or m['dead']: continue
        if (h>=m['lvl']) if m['hi'] else (l<=m['lvl']):
            m['dead']=True; m['deadt']=ts
def hm(x): return pd.Timestamp(int(x),unit='s',tz='UTC').tz_convert('America/New_York').strftime('%H:%M:%S')
print("5m LOWS under entry %.2f, status kl. 09:51:30" % ENT)
print("%-8s %-10s %-7s %-10s %s" % ("5m-lys","niveau","afst","status","taget kl."))
for m in sorted([m for m in lv if not m['hi'] and m['lvl']<ENT], key=lambda m:-m['lvl']):
    print("%-8s %-10.2f %-7.2f %-10s %s" % (hm(m['b']), m['lvl'], ENT-m['lvl'],
          "DOED" if m['dead'] else "LEVENDE", hm(m['deadt']) if m['deadt'] else ""))
