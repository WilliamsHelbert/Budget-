# -*- coding: utf-8 -*-
import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/dbfull"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
D=model._data(15)
m5 = D["m5"]["NQ"]
CUT = int(pd.Timestamp("2024-11-04 09:51:30", tz="America/New_York").timestamp())
ENT = 20116.0
bars = D["bar"]["NQ"]
ts_sorted = sorted(t for t in bars if CUT-20*3600 <= t <= CUT)
lv=[]
for b in sorted(k for k in m5 if k+300 <= CUT and k >= CUT-20*3600):
    o,h,l,c = m5[b]
    lv.append(dict(b=b,lvl=l,hi=False,dead=False,deadt=None))
for t in ts_sorted:
    o,h,l,c = bars[t]
    for m in lv:
        if t < m['b']+300 or m['dead']: continue
        if l <= m['lvl']: m['dead']=True; m['deadt']=t
def hm(x): return pd.Timestamp(int(x),unit='s',tz='UTC').tz_convert('Europe/Copenhagen').strftime('%d/%m %H:%M')
liv = sorted([m for m in lv if not m['dead'] and m['lvl']<ENT], key=lambda m:-m['lvl'])
print("LEVENDE 5m-lows under entry %.2f kl. 15:51:30, nu med hele natten med:" % ENT)
print("%-14s %-10s %s" % ("5m-lys (CPH)","niveau","afstand"))
for m in liv[:8]:
    print("%-14s %-10.2f %.2f" % (hm(m['b']), m['lvl'], ENT-m['lvl']))
print("\ntidligste 5m-lys i data:", hm(min(k for k in m5 if k>=CUT-20*3600)))
