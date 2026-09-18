import sys; sys.path.insert(0,'/home/user/repo/pakke')
D="/tmp/claude-0/-home-user/4e94c4c6-1705-52b5-b57c-9875eb47d924/scratchpad/jnl"
import eq_model as EM
EM.BASE=D; EM.TZ="America/New_York"; EM.OPEN_MIN,EM.CLOSE_MIN=9*60+30,16*60
EM._CACHE.clear()
C=EM._data(15); BAR,M1,TL,TOD,DAY=C["bar"],C["m1"],C["tl"],C["tod"],C["day"]
import pandas as _pd
_t=_pd.to_datetime(_pd.Series(TL),unit="s",utc=True).dt.tz_convert("Europe/Copenhagen")
CPH=dict(zip(TL,(_t.dt.hour*60+_t.dt.minute).tolist()))
SY=("ES","NQ")

def signals(t_from=15*60+30, t_to=16*60, max_conf=4, birth_raid=True, strict=False):
    """Alle gyldige EQ-signaler, begge retninger, uden positionsblokering."""
    eq={k:{"bear":None,"bull":None} for k in SY}
    pmin={k:None for k in SY}; day={k:None for k in SY}
    armed=None; out=[]
    for ts in TL:
        d=DAY[ts]; tod=TOD[ts]; mb=ts//60*60
        bars={k:BAR[k].get(ts) for k in SY}
        nm={}
        for k in SY:
            if bars[k] is None: nm[k]=None; continue
            nm[k]=M1[k].get(pmin[k]) if (pmin[k] is not None and mb!=pmin[k]) else None
            pmin[k]=mb
        for k in SY:
            if bars[k] is not None and tod>=EM.OPEN_MIN and day[k]!=d:
                day[k]=d; eq[k]={"bear":None,"bull":None}; armed=None
        if not (EM.OPEN_MIN<=tod<EM.CLOSE_MIN): continue
        pre={s:{k:eq[k][s] for k in SY} for s in ("bear","bull")}
        made={"bear":{},"bull":{}}
        raids=[]
        for k in SY:
            b=bars[k]
            if b is None: continue
            o,h,l,c=b
            for side in ("bear","bull"):
                if eq[k][side] is None: continue
                a,e0=eq[k][side]
                e1=min(e0,l) if side=="bear" else max(e0,h)
                lvl=(a+e1)/2
                if ((h>lvl) if strict else (h>=lvl)) if side=="bear" else ((l<lvl) if strict else (l<=lvl)):
                    raids.append((k,side,lvl,a,(c>lvl) if side=="bear" else (c<lvl)))
                    eq[k][side]=None
                else: eq[k][side]=(a,e1)
            pm=nm[k]
            if pm is not None:
                po,ph,pl,pc=pm; mid=(ph+pl)/2
                if pc<po and pc<mid and eq[k]["bear"] is None:
                    a,e=ph,min(pl,l); made["bear"][k]=(a,e); lvl=(a+e)/2
                    if birth_raid and ((h>lvl) if strict else (h>=lvl)): raids.append((k,"bear",lvl,a,c>lvl))
                    else: eq[k]["bear"]=(a,e)
                if pc>po and pc>mid and eq[k]["bull"] is None:
                    a,e=pl,max(ph,h); made["bull"][k]=(a,e); lvl=(a+e)/2
                    if birth_raid and ((l<lvl) if strict else (l<=lvl)): raids.append((k,"bull",lvl,a,c<lvl))
                    else: eq[k]["bull"]=(a,e)
        can = t_from<=CPH[ts]<t_to
        for (k,side,lvl,anch,thr) in raids:
            if not can or thr: continue
            oth="NQ" if k=="ES" else "ES"
            o2=made[side].get(oth,pre[side][oth])
            if o2 is None: continue
            armed=dict(side=side,hit=k,ts=ts,seen=0,
                       lev={k:lvl,oth:(o2[0]+o2[1])/2},anch={k:anch,oth:o2[0]})
        if armed and all(bars[k] is not None for k in SY):
            s=armed["side"]
            if armed["seen"]>=max_conf or not can: armed=None
            else:
                armed["seen"]+=1
                dead=any((bars[k][3]>armed["lev"][k]) if s=="bear" else (bars[k][3]<armed["lev"][k]) for k in SY)
                ok=all((bars[k][3]<bars[k][0]) if s=="bear" else (bars[k][3]>bars[k][0]) for k in SY)
                if dead: armed=None
                elif ok:
                    out.append(dict(dag=d,ts=ts,tid=EM.fmt(ts)[11:19],
                        dir="Short" if s=="bear" else "Long", hit=armed["hit"],
                        nq=bars["NQ"][3], es=bars["ES"][3],
                        nq_anker=armed["anch"]["NQ"], es_anker=armed["anch"]["ES"], cph=CPH[ts]))
                    armed=None
    return out
