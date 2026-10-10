"""
Continuation-model backtest (ES/NQ, 1m/5m bygget fra 15s-data).

Trin (long; short er spejlet):
 1. Session liq sweep: Asia/London/NY PRE low (dagens) tages efter sessionen er slut,
    paa ES ELLER NQ.
 2. 5m BOS / 5m IFVG: efter sweep-5m-candlen er lukket skal en 5m candle lukke
    paa/over en gyldig 5m swing high (ikke lukket over siden den blev lavet),
    eller paa/over toppen af en bearish 5m FVG.
 3. Pullback: 1m close paa/under seneste 1m swing low, eller inversion af en
    bullish 1m/5m FVG (close paa/under bunden).
 4. Entry: 1m close STRENGT over seneste 1m swing high, eller strengt over
    toppen af en bearish 1m FVG dannet efter trin 2.
 SL: laveste af (laveste 5m low siden trin 2, forrige 5m swing low).
 TP: naermeste uroerte session-niveau (Asia/London/NY PRE) i trade-retningen.
 NY PRE = 90 min foer NY open (09:30 New York), London = 08:00 DK til NY PRE.

Brug: python3 continuation_model.py DATA_DIR [2024-03-04 ...]
DATA_DIR skal indeholde *ES_2024.parquet og *NQ_2024.parquet.
"""
import sys, glob, numpy as np, pandas as pd
TZ_='Europe/Copenhagen'
def load(s):
    f=[p for p in glob.glob(f"{DATA_DIR}/*{s}_2024.parquet")][0]
    d=pd.read_parquet(f)
    d['t']=pd.to_datetime(d.ts,unit='s',utc=True).dt.tz_convert(TZ_)
    return d.set_index('t')[['open','high','low','close']]*0.25
TZ='Europe/Copenhagen'; NY='America/New_York'
T1=pd.Timedelta('1min'); T5=pd.Timedelta('5min')
WIN_END_NY='12:00'   # sidste tidspunkt for sweep/entry (NY-tid)
EXIT_NY='16:00'      # tvungen exit (NY-tid)

def bars(d,r):
    x=d.resample(r).agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
    return x

def mirror(df):
    return pd.DataFrame({'open':-df.open,'high':-df.low,'low':-df.high,'close':-df.close},index=df.index)

def sessions(day):
    ny_open=pd.Timestamp(f'{day} 09:30',tz=NY).tz_convert(TZ)
    pre=ny_open-pd.Timedelta('90min')
    d=lambda s: pd.Timestamp(f'{day} {s}',tz=TZ)
    return {'Asia':(d('02:00'),d('08:00')),'London':(d('08:00'),pre),'NY PRE':(pre,ny_open)}, ny_open

def levels(m1,S):
    """session-niveauer i (evt. spejlet) rum: (navn, side, niveau, sluttid, tid_taget)"""
    out=[]
    for n,(a,b) in S.items():
        w=m1[(m1.index>=a)&(m1.index<b)]
        if not len(w): continue
        after=m1[m1.index>=b]
        for side,lv in (('high',w.high.max()),('low',w.low.min())):
            hit=after.index[(after.high>=lv) if side=='high' else (after.low<=lv)]
            out.append(dict(name=n,side=side,lvl=lv,end=b,taken=hit[0] if len(hit) else None))
    return out

def swings(h,l):
    sh=[i for i in range(1,len(h)-1) if h[i]>h[i-1] and h[i]>h[i+1]]
    sl=[i for i in range(1,len(l)-1) if l[i]<l[i-1] and l[i]<l[i+1]]
    return sh,sl

def fvgs(h,l):
    bear=[(i,l[i-2],h[i]) for i in range(2,len(h)) if l[i-2]>h[i]]   # (c3, top, bund)
    bull=[(i,l[i],h[i-2]) for i in range(2,len(h)) if h[i-2]<l[i]]   # (c3, top, bund)
    return bear,bull

def run_dir(day,sym,oth,m1,m5,o_m1,s15,S,ny_open,direction):
    """Long-logik i (evt. spejlet) prisrum. Returnerer liste af trades."""
    win_start=S['NY PRE'][0]
    win_end=pd.Timestamp(f'{day} {WIN_END_NY}',tz=NY).tz_convert(TZ)
    exit_t=pd.Timestamp(f'{day} {EXIT_NY}',tz=NY).tz_convert(TZ)
    t1=m1.index; o,h,l,c=(m1[x].values for x in ['open','high','low','close'])
    t5=m5.index; h5,l5,c5=(m5[x].values for x in ['high','low','close'])
    day0=pd.Timestamp(f'{day} 02:00',tz=TZ)
    sh1,sl1=swings(h,l); sh5,sl5=swings(h5,l5)
    bear1,bull1=fvgs(h,l); bear5,bull5=fvgs(h5,l5)
    j_of=np.searchsorted(t5.values, t1.floor('5min').values)  # 5m-index for hver 1m
    # sweeps: lows (i spejlet rum) paa begge symboler
    lv_self=levels(m1,S); sweeps=[]
    for src,lv in ((sym,lv_self),(oth,levels(o_m1,S))):
        for x in lv:
            if x['side']=='low' and x['taken'] is not None and win_start<=x['taken']<win_end:
                sweeps.append((x['taken'],f"{src}:{x['name']}"))
    sweeps.sort()
    trades=[]; st=0; busy_until=win_start
    sw_i=0; info={}
    def last_swing(lst,k,arr,valid_cmp):
        # seneste bekraeftede swing (index<=k-2), som ikke allerede er brudt af close
        for s in reversed(lst):
            if s<=k-2: return s
        return None
    for k in range(len(t1)):
        tk=t1[k]; tend=tk+T1
        if tk<win_start: continue
        if tk>=win_end: break
        # nyt sweep -> (gen)start ved trin 1
        new=[]
        while sw_i<len(sweeps) and sweeps[sw_i][0]<=tk:
            new.append(sweeps[sw_i]); sw_i+=1
        if new and tk>=busy_until:
            st=1; js=j_of[k]; info=dict(sweep_t=tk,sweep=' + '.join(n for _,n in new),js=js,ext=l[k])
        if st==0 or tk<busy_until: continue
        info['ext']=min(info['ext'],l[k]) if st==1 else info['ext']
        # invalidering: under sweep-ekstrem efter trin 2
        if st>=2 and l[k]<info['ext']:
            st=0; continue
        j=j_of[k]; closes5 = (k+1==len(t1)) or j_of[k+1]!=j
        if st==1:
            if closes5 and j>info['js']:
                # gyldige 5m swing highs: dannet i dag, ikke closet over siden
                ok=False; why=None
                best=None
                for s in sh5:
                    if s>j-2 or t5[s]<day0: continue
                    if (c5[s+1:j]>=h5[s]).any(): continue
                    if c5[j]>=h5[s] and (best is None or h5[s]<h5[best]): best=s
                if best is not None: ok=True; why=f"5m BOS {t5[best]:%H:%M} ({h5[best]})"
                if not ok:
                    for f,top,bot in bear5:
                        if f>j-1 or t5[f]<day0: continue
                        if (c5[f+1:j]>=top).any(): continue
                        if c5[j]>=top: ok=True; why=f"5m IFVG {t5[f-2]:%H:%M} ({top})"; break
                if ok:
                    st=2; info.update(T2=t5[j]+T5,s2=why,k2=k)
            continue
        if st==2:
            if tk<info['T2']: continue
            why=None
            s=next((s for s in reversed(sl1) if s<=k-2),None)
            if s is not None and not (c[s+1:k]<=l[s]).any() and c[k]<=l[s]:
                why=f"1m BOS {t1[s]:%H:%M} ({l[s]})"
            if why is None:
                for f,top,bot in bull1:
                    if f>k-1 or t1[f]<info['sweep_t']: continue
                    if (c[f+1:k]<=bot).any(): continue
                    if c[k]<=bot: why=f"1m IFVG {t1[f-2]:%H:%M} ({bot})"; break
            if why is None and closes5:
                for f,top,bot in bull5:
                    if f>j-1 or t5[f]<info['sweep_t'].floor('5min'): continue
                    if (c5[f+1:j]<=bot).any(): continue
                    if c5[j]<=bot: why=f"5m IFVG {t5[f-2]:%H:%M} ({bot})"; break
            if why: st=3; info.update(T3=tend,s3=why)
            continue
        if st==3:
            if tk<info['T3']: continue
            why=None
            s=next((s for s in reversed(sh1) if s<=k-2),None)
            if s is not None and not (c[s+1:k]>h[s]).any() and c[k]>h[s]:
                why=f"1m BOS {t1[s]:%H:%M} ({h[s]})"
            if why is None:
                for f,top,bot in bear1:
                    if f>k-1 or t1[f-2]<info['T2']: continue
                    if (c[f+1:k]>top).any(): continue
                    if c[k]>top: why=f"1m IFVG {t1[f-2]:%H:%M} ({top})"; break
            if not why: continue
            entry=c[k]; et=tend
            # SL: laveste 5m low siden T2 vs. forrige 5m swing low
            k2=info['k2']; seg=l[k2+1:k+1]; ia=k2+1+int(np.argmin(seg)); cur=l[ia]; jc=j_of[ia]
            prev=next((l5[s] for s in reversed(sl5) if s<jc and s+1<=j_of[k]-0),None)
            sl=min(cur,prev) if prev is not None else cur
            # TP: naermeste uroerte session-niveau over entry
            cands=[x for x in lv_self if x['end']<=et and x['lvl']>entry and (x['taken'] is None or x['taken']>=et)]
            tp=min(cands,key=lambda x:x['lvl']) if cands else None
            tr=dict(day=day,sym=sym,dir=direction,sweep_t=info['sweep_t'],sweep=info['sweep'],
                    s2=info['s2'],T2=info['T2'],s3=info['s3'],T3=info['T3'],s4=why,entry_t=et,
                    entry=entry,sl=sl,tp=tp['lvl'] if tp else None,tp_name=f"{tp['name']} {tp['side']}" if tp else None)
            if tp is None:
                tr.update(result='INGEN TP',R=None,exit_t=None); trades.append(tr); st=0; continue
            w=s15[(s15.index>=et)&(s15.index<exit_t)]
            res=None
            for ts,r in w.iterrows():
                if r.low<=sl: res=('SL',sl,ts); break
                if r.high>=tp['lvl']: res=('TP',tp['lvl'],ts); break
            if res is None: res=('EOD',w.close.iloc[-1],w.index[-1])
            risk=entry-sl
            tr.update(result=res[0],exit=res[1],exit_t=res[2]+pd.Timedelta('15s'),risk=risk,R=(res[1]-entry)/risk)
            trades.append(tr); st=0; busy_until=tr['exit_t']
    return trades

def run(days=None):
    D={s:load(s).loc['2024-03-01':'2024-03-31'] for s in ['ES','NQ']}
    M1={s:bars(D[s],'1min') for s in D}
    allt=[]
    for day in sorted(set(D['ES'].index.date)):
        day=str(day)
        if days and day not in days: continue
        S,ny_open=sessions(day)
        a=pd.Timestamp(f'{day} 00:00',tz=TZ); b=a+pd.Timedelta('1D')
        for sym,oth in (('ES','NQ'),('NQ','ES')):
            m1=M1[sym][a:b-pd.Timedelta('1ns')]; om=M1[oth][a:b-pd.Timedelta('1ns')]
            s15=D[sym][a:b-pd.Timedelta('1ns')]
            for dirn,f in (('LONG',lambda x:x),('SHORT',mirror)):
                M=f(m1); m5=bars(M,'5min'); tr=run_dir(day,sym,oth,M,m5,f(om),f(s15),S,ny_open,dirn)
                if dirn=='SHORT':
                    for t in tr:
                        for kk in ('entry','sl','tp','exit'):
                            if t.get(kk) is not None: t[kk]=-t[kk]
                        for kk in ('s2','s3','s4'):
                            t[kk]=t[kk].replace('(-','(')
                        if t['tp_name']: t['tp_name']=t['tp_name'].replace('high','LOW').replace('low','high').replace('LOW','low')
                allt+=tr
    df=pd.DataFrame(allt).sort_values(['sym','entry_t']).reset_index(drop=True)
    # intet nyt trade mens et andet er aabent paa samme symbol
    keep=[]; open_until={}
    for i,r in df.iterrows():
        if r.R is not None and not pd.isna(r.R):
            if r.entry_t < open_until.get(r.sym,r.entry_t): continue
            open_until[r.sym]=r.exit_t
        keep.append(i)
    return df.loc[keep].sort_values(['day','sym','entry_t']).reset_index(drop=True)
if __name__=='__main__':
    DATA_DIR=sys.argv[1]
    df=run(sys.argv[2:] or None)
    pd.set_option('display.width',300); pd.set_option('display.max_columns',30)
    cols=['day','sym','dir','sweep_t','sweep','s2','s3','s4','entry_t','entry','sl','tp','tp_name','result','exit_t','R']
    for c_ in ['sweep_t','entry_t','exit_t']: df[c_]=pd.to_datetime(df[c_]).dt.tz_convert(TZ).dt.strftime('%H:%M')
    print(df[cols].to_string())
    df.to_csv('results/marts_2024_trades.csv',index=False)
