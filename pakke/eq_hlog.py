import sys, pandas as pd
sys.path.insert(0,'/home/user/repo/pakke')
D="/tmp/claude-0/-home-user/4e94c4c6-1705-52b5-b57c-9875eb47d924/scratchpad/jnl"
import eq_model as EM
EM.BASE=D; EM.TZ="America/New_York"; EM.OPEN_MIN,EM.CLOSE_MIN=9*60+30,16*60
EM._CACHE.clear()
C=EM._data(15); BAR,M1,TL,TOD,DAY=C["bar"],C["m1"],C["tl"],C["tod"],C["day"]
SY=("ES","NQ")

def log(day, t_from="09:30", t_to="10:05", mark=()):
    f=lambda s:int(s[:2])*60+int(s[3:])
    lo,hi=f(t_from),f(t_to)
    eq={k:{"bear":None,"bull":None} for k in SY}
    pmin={k:None for k in SY}
    print("="*96); print("  %s   (markeret: %s)"%(day,", ".join(mark) if mark else "-")); print("="*96)
    for ts in TL:
        if DAY[ts]!=day or not (lo<=TOD[ts]<hi): continue
        hhmm=EM.fmt(ts)[11:16]; sec=EM.fmt(ts)[11:19]
        bars={k:BAR[k].get(ts) for k in SY}
        mb=ts//60*60
        nm={}
        for k in SY:
            if bars[k] is None: nm[k]=None; continue
            nm[k]=M1[k].get(pmin[k]) if (pmin[k] is not None and mb!=pmin[k]) else None
            pmin[k]=mb
        ev=[]
        for k in SY:
            b=bars[k]
            if b is None: continue
            o,h,l,c=b
            for side in ("bear","bull"):
                if eq[k][side] is None: continue
                a,e0=eq[k][side]
                e1=min(e0,l) if side=="bear" else max(e0,h)
                lvl=(a+e1)/2
                if (h>=lvl) if side=="bear" else (l<=lvl):
                    thr=(c>lvl) if side=="bear" else (c<lvl)
                    part=eq["NQ" if k=="ES" else "ES"][side]
                    ev.append("%s RAID %s linje %.2f %s | partner-EQ %s"%(
                        k,side.upper(),lvl,"LUKKEDE IGENNEM" if thr else "rent",
                        "JA" if part else "nej"))
                    eq[k][side]=None
                else: eq[k][side]=(a,e1)
            pm=nm[k]
            if pm is not None:
                po,ph,pl,pc=pm; mid=(ph+pl)/2
                if pc<po and pc<mid and eq[k]["bear"] is None:
                    eq[k]["bear"]=(ph,min(pl,l)); ev.append("%s ny BEAR-EQ anker %.2f"%(k,ph))
                if pc>po and pc>mid and eq[k]["bull"] is None:
                    eq[k]["bull"]=(pl,max(ph,h)); ev.append("%s ny BULL-EQ anker %.2f"%(k,pl))
        if bars["ES"] and bars["NQ"]:
            be=all(bars[k][3]<bars[k][0] for k in SY); bu=all(bars[k][3]>bars[k][0] for k in SY)
            if ev and (be or bu): ev.append(">>> BEGGE lukker %s"%("bearish" if be else "bullish"))
        if ev:
            m="  <<<<<" if hhmm in mark else ""
            print("%s  %s%s"%(sec,"  ||  ".join(ev),m))
