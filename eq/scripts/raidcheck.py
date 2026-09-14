"""Klassificer hvert raid efter om det afhaenger af rakkefoelgen INDE i 15s-baren.

  lvl0 = EQ-linjen FOER denne bars egen forlaengelse af extremet
  lvl1 = EQ-linjen EFTER  (det motoren bruger)

  SIKKER   : baren rammer allerede lvl0 -> raidet er aegte uanset rakkefoelge
  FALSK    : rammer kun lvl1, og barens form siger at forlaengelsen kom SIDST
  USIKKER  : rammer kun lvl1, og formen afgoer det ikke
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M

def classify():
    C=M._data(15); BAR,M1,TL,TOD,DAY=C["bar"],C["m1"],C["tl"],C["tod"],C["day"]
    out={}
    day={}; bear={}; bull={}
    for ts in TL:
        tod=TOD[ts]; d=DAY[ts]
        if not (M.OPEN_MIN <= tod < M.CLOSE_MIN): continue
        mb=ts//60*60
        for k in ("ES","NQ"):
            b=BAR[k].get(ts)
            if b is None: continue
            o,h,l,c=b
            if day.get(k)!=d: day[k]=d; bear[k]=bull[k]=None
            def note(side, a, e0, e1):
                lvl0=(a+e0)/2.0; lvl1=(a+e1)/2.0
                if side=="bear":
                    sure = h>=lvl0
                    # bear: forlaengelsen er en ny LOW, beroeringen er barens HIGH.
                    # raidet er aegte kun hvis low kom FOER high -> op-lukkende bar
                    order = "ok" if c>o else ("nej" if c<o else "?")
                else:
                    sure = l<=lvl0
                    order = "ok" if c<o else ("nej" if c>o else "?")
                if sure:            tag="SIKKER"
                elif order=="ok":   tag="SIKKER*"
                elif order=="nej":  tag="FALSK"
                else:               tag="USIKKER"
                out[(ts,k,side)]=dict(tag=tag, lvl0=lvl0, lvl1=lvl1, o=o,h=h,l=l,c=c,
                                      flyttet=abs(lvl1-lvl0))
            if bear.get(k):
                a,e0=bear[k]; e1=min(e0,l)
                if h>=(a+e1)/2.0: note("bear",a,e0,e1); bear[k]=None
                else: bear[k]=(a,e1)
            if bull.get(k):
                a,e0=bull[k]; e1=max(e0,h)
                if l<=(a+e1)/2.0: note("bull",a,e0,e1); bull[k]=None
                else: bull[k]=(a,e1)
            pm=M1[k].get(mb-60) if ts==mb else None
            if pm:
                po,ph,pl,pc=pm; eq1=(ph+pl)/2.0
                if pc<po and pc<eq1 and bear.get(k) is None:
                    a,e0,e1=ph,pl,min(pl,l)
                    if h>=(a+e1)/2.0: note("bear",a,e0,e1)
                    else: bear[k]=(a,e1)
                if pc>po and pc>eq1 and bull.get(k) is None:
                    a,e0,e1=pl,ph,max(ph,h)
                    if l<=(a+e1)/2.0: note("bull",a,e0,e1)
                    else: bull[k]=(a,e1)
    return out

if __name__=="__main__":
    import pandas as pd, collections
    R=classify()
    print("ALLE raids i sessionen:", collections.Counter(v["tag"] for v in R.values()))
    tr=pd.read_csv(f"{M.BASE}/out/TRADES_paired.csv")
    def to_ts(s): return int(pd.Timestamp(s).tz_localize(M.TZ).tz_convert("UTC").timestamp())
    print()
    rows=[]
    for pid,g in tr.groupby("id"):
        r=g.iloc[0]; side="bear" if r.side=="SHORT" else "bull"
        key=(to_ts(r.hit_t), r.trigger_asset, side)
        info=R.get(key)
        rows.append(dict(id=pid, dag=r.day, tid=str(r.entry_t)[11:], side=r.side,
                         trig=r.trigger_asset, R=round(g.R.sum(),2),
                         tag=info["tag"] if info else "?",
                         flyttet=round(info["flyttet"],3) if info else None))
    df=pd.DataFrame(rows)
    print(df.to_string(index=False))
    print()
    for t in ("SIKKER","SIKKER*","USIKKER","FALSK"):
        s=df[df.tag==t]
        if len(s): print(f"  {t:8s} {len(s):2d} par   {s.R.sum():+7.2f} R")
