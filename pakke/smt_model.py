# -*- coding: utf-8 -*-
"""SMT - Session Sweep, port af Pine v10 til Python. Koeres paa 15s-barer.

STATUS pr. 16-09-2026: IKKE faerdig. Bedste koersel rammer 40 handler mod
journalens 41 for jan-feb 2026, +35.08 R mod journalens +86.60 R. 16 har
samme dag+tidspunkt, 8 har identisk R. 27. april 2026 burde fjernes af
regel C men goer det ikke. Se LAESMIG.md."""
import os, sys, math
import pandas as pd, numpy as np

TZ = "Europe/Copenhagen"
ASIA=(2*60, 8*60); LON=(8*60, 14*60); NYP=(14*60, 15*60+30)
WIN_S, WIN_E = 15*60+30, 16*60
NY_FROM = 14*60
REM = 15*60+31
MAXDAY=3; TPMIN=35.0; TPMAX=75.0; MINSL=10.0
BEMIN=2.0; BEMAX=50.0; TICK=0.25
R_UNIT = 10.0          # 1 R = 10 NQ-point
TICKHALF = 0.25/2
DIAG={}

def is369(m):
    o=m%10; t=(m-o)//10; return (t+o) in (3,6,9)

def load(base):
    nq=pd.read_parquet(f"{base}/NQ.parquet"); es=pd.read_parquet(f"{base}/ES.parquet")
    for d in (nq,es):
        d['ts']=pd.to_datetime(d.time,utc=True).dt.as_unit('ns')
    m=pd.merge(nq[['ts','open','high','low','close']],
               es[['ts','open','high','low','close']],on='ts',suffixes=('','_c'))
    t=m.ts.dt.tz_convert(TZ)
    m['tod']=t.dt.hour*60+t.dt.minute
    m['mn']=t.dt.minute
    m['dag']=t.dt.strftime('%Y-%m-%d')
    m['dom']=t.dt.day
    _sek = m.ts.dt.tz_convert('UTC').dt.tz_localize(None).astype('datetime64[s]').astype('int64')
    m['minb']=(_sek//60).astype('int64')
    m['hhmm']=t.dt.strftime('%H:%M')
    return m.sort_values('ts').reset_index(drop=True)

class Sess:
    __slots__=('aHi','aLo','bHi','bLo','hiUsed','loUsed')
    def __init__(s): s.aHi=s.aLo=s.bHi=s.bLo=None; s.hiUsed=s.loUsed=False
    def build(s,start,h,l,ch,cl):
        s.aHi = h if start else max(s.aHi,h)
        s.aLo = l if start else min(s.aLo,l)
        s.bHi = ch if start else (s.bHi if ch is None else max(s.bHi,ch))
        s.bLo = cl if start else (s.bLo if cl is None else min(s.bLo,cl))
        if start: s.hiUsed=s.loUsed=False

class Lv:
    __slots__=('aLvl','bLvl','isHi','dead','used','touched','src')
    def __init__(s,a,b,hi,src): s.aLvl=a; s.bLvl=b; s.isHi=hi; s.dead=False; s.used=False; s.touched=False; s.src=src

def run(base, lo=None, hi=None, bothSideBlock=True, maxday=MAXDAY,
        entry15mOnly=True, korrCheck=True, beNoTaken=True, block15mOnly=False, sl15s=False, beStreng=True):
    d=load(base)
    if lo: d=d[(d.dag>=lo)&(d.dag<=hi)].reset_index(drop=True)
    N=len(d)
    O=d.open.values; H=d.high.values; L=d.low.values; C=d.close.values
    CO=d.open_c.values; CH=d.high_c.values; CL=d.low_c.values; CC=d.close_c.values
    TOD=d.tod.values; MN=d.mn.values; DAG=d.dag.values; DOM=d.dom.values
    MINB=d.minb.values; HHMM=d.hhmm.values; TS=d.ts.values

    asia=Sess(); lon=Sess(); ny=Sess()
    lastOpenDay=-1; tradesToday=0; hiSide=loSide=False
    m1Hi=m1Lo=None; prevMn=None
    # EQ
    bqTop=bqBot=None; bqAct=False; lqTop=lqBot=None; lqAct=False
    lastT1=None
    # 1m/5m/15m aggregering (forrige afsluttede bar)
    agg={}   # (sec) -> dict(cur_key, o,h,l,c, ch,cl, prev=(...))
    for sec in (60,300,900): agg[sec]=dict(key=None,o=None,h=None,l=None,c=None,ch=None,cl=None,prev=None)
    lvs=[]
    DIAG.update(sig=0,blok_max=0,blok_sider=0,blok_armed=0,ok=0,tid={})
    armed=False; armShort=False; armLvl=None; armMinB=None; armSrc='?'
    live=[]; trades=[]

    esHiTaken=False; esLoTaken=False
    prev_on={'a':False,'l':False,'n':False}
    prev_inNy=False

    for i in range(N):
        tod=TOD[i]; o,h,l,c=O[i],H[i],L[i],C[i]; co,ch,cl,cc=CO[i],CH[i],CL[i],CC[i]
        inWin = WIN_S<=tod<WIN_E
        canShow = inWin and is369(MN[i])

        # --- 1-minuts running high/low
        if MN[i]!=prevMn: m1Hi=h; m1Lo=l; prevMn=MN[i]
        else: m1Hi=max(m1Hi,h); m1Lo=min(m1Lo,l)

        # --- aggregering: afslut bar naar noeglen skifter
        newbar={}
        for sec in (60,300,900):
            a=agg[sec]
            k=(TS[i].astype('int64')//1_000_000_000)//sec*sec
            if a['key'] is None: a.update(key=k,o=o,h=h,l=l,c=c,ch=ch,cl=cl)
            elif k!=a['key']:
                a['prev']=dict(o=a['o'],h=a['h'],l=a['l'],c=a['c'],ch=a['ch'],cl=a['cl'],t=a['key'])
                a.update(key=k,o=o,h=h,l=l,c=c,ch=ch,cl=cl); newbar[sec]=True
            else:
                a['h']=max(a['h'],h); a['l']=min(a['l'],l); a['c']=c
                a['ch']=max(a['ch'],ch); a['cl']=min(a['cl'],cl)

        # --- dagsreset ved open
        if tod>=WIN_S and lastOpenDay!=DOM[i]:
            lastOpenDay=DOM[i]; tradesToday=0; hiSide=loSide=False; esHiTaken=False; esLoTaken=False

        # --- sessioner
        aOn=ASIA[0]<=tod<ASIA[1]; lOn=LON[0]<=tod<LON[1]; nOn=NYP[0]<=tod<NYP[1]
        if aOn: asia.build(not prev_on['a'],h,l,ch,cl)
        if lOn: lon.build(not prev_on['l'],h,l,ch,cl)
        if nOn: ny.build(not prev_on['n'],h,l,ch,cl)

        sigFired=False; sigShort=False; sigLvl=None; sigSrc=''

        def sweepHi(s,ok,nm=''):
            nonlocal sigFired,sigShort,sigLvl,hiSide
            if ok and not s.hiUsed and s.aHi is not None and s.bHi is not None:
                aT=h>=s.aHi+TICK; bT=ch>=s.bHi+TICK
                if aT or bT:
                    s.hiUsed=True
                    if canShow and aT!=bT:
                        sigFired=True; sigShort=True; sigLvl=s.aHi; hiSide=True
                        globals()['_src']=nm
        def sweepLo(s,ok,nm=''):
            nonlocal sigFired,sigShort,sigLvl,loSide
            if ok and not s.loUsed and s.aLo is not None and s.bLo is not None:
                aT=l<=s.aLo-TICK; bT=cl<=s.bLo-TICK
                if aT or bT:
                    s.loUsed=True
                    if canShow and aT!=bT:
                        sigFired=True; sigShort=False; sigLvl=s.aLo; loSide=True
                        globals()['_src']=nm
        sweepHi(asia,not aOn,'Asia'); sweepLo(asia,not aOn,'Asia')
        sweepHi(lon,not lOn,'London');  sweepLo(lon,not lOn,'London')
        sweepHi(ny,not nOn,'NYPRE');   sweepLo(ny,not nOn,'NYPRE')

        # --- EQ-model paa forrige 1m-bar
        p1=agg[60]['prev']
        if 60 in newbar and p1 and p1['t']!=lastT1:
            lastT1=p1['t']
            eq=(p1['h']+p1['l'])/2
            if p1['c']<p1['o'] and p1['c']<eq:
                if not bqAct: bqTop=p1['h']; bqBot=min(p1['l'],l); bqAct=True
            if p1['c']>p1['o'] and p1['c']>eq:
                if not lqAct: lqBot=p1['l']; lqTop=max(p1['h'],h); lqAct=True
        if bqAct:
            bqBot=min(bqBot,l)
            if h>=(bqTop+bqBot)/2: bqAct=False
        if lqAct:
            lqTop=max(lqTop,h)
            if l<=(lqBot+lqTop)/2: lqAct=False

        # --- NY PRE niveauer
        inNy = NY_FROM<=tod<WIN_S
        if inNy and not prev_inNy: lvs=[]
        for sec,src in ((900,'15m'),(300,'5m')):
            if sec in newbar:
                p=agg[sec]['prev']
                if p is not None:
                    pt=pd.Timestamp(p['t'],unit='s',tz='UTC').tz_convert(TZ)
                    pm=pt.hour*60+pt.minute
                    if NY_FROM<=pm<WIN_S:
                        lvs.append(Lv(p['h'],p['ch'],True,src))
                        lvs.append(Lv(p['l'],p['cl'],False,src))
        if inNy:
            for m in lvs:
                aHit=(h>=m.aLvl) if m.isHi else (l<=m.aLvl)
                bHit=(ch>=m.bLvl) if m.isHi else (cl<=m.bLvl)
                if not m.dead and (aHit or bHit): m.dead=True
        if tod>=WIN_S:
            for m in lvs:
                hit=(h>=m.aLvl) if m.isHi else (l<=m.aLvl)
                if not m.dead and not m.touched and hit:
                    m.touched=True
                    if m.src=='15m' or not block15mOnly:
                        if m.isHi: hiSide=True
                        else: loSide=True
        lvLive = WIN_S<=tod<REM
        if lvLive:
            for m in lvs:
                isExt = (ny.aHi is not None and abs(m.aLvl-ny.aHi)<TICKHALF) if m.isHi \
                        else (ny.aLo is not None and abs(m.aLvl-ny.aLo)<TICKHALF)
                aT=(h>=m.aLvl+TICK) if m.isHi else (l<=m.aLvl-TICK)
                bT=(ch>=m.bLvl+TICK) if m.isHi else (cl<=m.bLvl-TICK)
                go = (not m.dead) and (not m.used) and (not isExt) and (aT or bT)
                if go: m.used=True
                if go and canShow and aT!=bT and (m.src=='15m' or not entry15mOnly):
                    sigFired=True; sigShort=m.isHi; sigLvl=m.aLvl; globals()['_src']=m.src
                    if m.isHi: hiSide=True
                    else: loSide=True

        # --- ES har taget sin NY PRE high/low siden aabning?
        if tod>=WIN_S:
            if ny.bHi is not None and ch>=ny.bHi+TICK: esHiTaken=True
            if ny.bLo is not None and cl<=ny.bLo-TICK: esLoTaken=True

        # --- aabne trades
        for t in live[:]:
            if t['live'] and not t['beHit'] and t['be'] is not None:
                if (l<=t['be']) if t['short'] else (h>=t['be']):
                    t['beHit']=True; t['sl']=t['entry']
            hitSL=(h>=t['sl']) if t['short'] else (l<=t['sl'])
            hitTP=(l<=t['tp']) if t['short'] else (h>=t['tp'])
            if hitSL or hitTP:
                t['live']=False
                px = t['sl'] if hitSL else t['tp']
                t['exit']=px; t['exit_t']=HHMM[i]
                t['reason']='SL' if hitSL and not t['beHit'] else ('BE' if hitSL else 'TP')
                sgn=-1 if t['short'] else 1
                t['R']=round(sgn*(px-t['entry'])/R_UNIT,4)
                trades.append(t); live.remove(t)

        # --- arm
        roomLeft = maxday<=0 or tradesToday<maxday
        sidesOK = (not bothSideBlock) or not (hiSide and loSide)
        if sigFired and inWin:
            DIAG['sig']+=1
            if not roomLeft: DIAG['blok_max']+=1
            elif not sidesOK: DIAG['blok_sider']+=1
            elif armed: DIAG['blok_armed']+=1
            else: DIAG['ok']+=1
            DIAG['tid'][HHMM[i]]=DIAG['tid'].get(HHMM[i],0)+1
        korrOK = True
        if korrCheck and sigFired:
            korrOK = (not esLoTaken) if sigShort else (not esHiTaken)
        if sigFired and not armed and roomLeft and sidesOK and korrOK:
            armed=True; armShort=sigShort; armLvl=sigLvl; armMinB=MINB[i]; armSrc=globals().get('_src','?')

        # --- entry
        for _once in (0,):
          if armed and MINB[i]==armMinB:
              bothBear = c<o and cc<co
              bothBull = c>o and cc>co
              dirOK = bothBear if armShort else bothBull
              backOK = (c<armLvl) if armShort else (c>armLvl)
              if dirOK and backOK:
                  armed=False; tradesToday+=1
                  below=armShort
                  entry=c
                  ref_hi = h if sl15s else m1Hi
                  ref_lo = l if sl15s else m1Lo
                  sl = max(ref_hi, c+MINSL) if below else min(ref_lo, c-MINSL)
                  qLo = bqBot if below else lqBot
                  qHi = bqTop if below else lqTop
                  qMid = None if (qLo is None or qHi is None) else (qLo+qHi)/2
                  qQt  = None if (qLo is None or qHi is None) else qLo+(0.75 if below else 0.25)*(qHi-qLo)
                  def tpCand(lvl,avail,best):
                      if lvl is None or not avail: return best
                      if not ((lvl<entry) if below else (lvl>entry)): return best
                      dd=abs(entry-lvl)
                      if not (TPMIN<=dd<=TPMAX): return best
                      if best is None: return lvl
                      return lvl if ((lvl>best) if below else (lvl<best)) else best
                  tgt=None
                  tgt=tpCand(asia.aLo if below else asia.aHi, (not asia.loUsed) if below else (not asia.hiUsed), tgt)
                  tgt=tpCand(lon.aLo  if below else lon.aHi,  (not lon.loUsed)  if below else (not lon.hiUsed),  tgt)
                  tgt=tpCand(ny.aLo   if below else ny.aHi,   (not ny.loUsed)   if below else (not ny.hiUsed),   tgt)
                  tgt=tpCand(qMid, True, tgt)
                  tp = (entry-TPMAX if below else entry+TPMAX) if tgt is None else tgt
                  def beCand(lvl,avail,best):
                      if lvl is None or not avail: return best
                      if not ((lvl<entry) if below else (lvl>entry)): return best
                      dd=abs(entry-lvl)
                      if dd<BEMIN or dd>BEMAX: return best
                      if not ((lvl>tp) if below else (lvl<tp)): return best
                      if best is None: return lvl
                      return lvl if ((lvl>best) if below else (lvl<best)) else best
                  # --- BE-kandidater med kilde. Nearest vinder.
                  #  15m/5m og 25% EQ: prisen maa gerne gaa igennem
                  #  session liq og EQ(50%): MAA IKKE vaere swept - ellers ugyldig handel
                  kand=[]
                  for m in lvs:
                      if m.isHi!=below and not m.dead and not m.touched:
                          kand.append((m.aLvl, m.src, True))
                  if qMid is not None:
                      eqLevende = (bqAct if below else lqAct)
                      kand.append((qMid,'EQ',eqLevende))
                  if qQt is not None:
                      kand.append((qQt,'25EQ',True))
                  for sess,nm in ((asia,'session'),(lon,'session'),(ny,'session')):
                      lvl = sess.aLo if below else sess.aHi
                      urort = (not sess.loUsed) if below else (not sess.hiUsed)
                      if lvl is not None: kand.append((lvl,nm,urort))
                  # filtrer paa retning, afstand og foer TP
                  gyldige=[]
                  for lvl,src,urort in kand:
                      if lvl is None: continue
                      if not ((lvl<entry) if below else (lvl>entry)): continue
                      dd=abs(entry-lvl)
                      if dd<BEMIN or dd>BEMAX: continue
                      if not ((lvl>tp) if below else (lvl<tp)): continue
                      gyldige.append((dd,lvl,src,urort))
                  gyldige.sort()
                  # gaa fra naermeste og udad:
                  #   15m/5m og 25EQ taget  -> spring videre til naeste
                  #   session eller EQ taget -> handlen er ugyldig
                  be=None; beSrc=None; ugyldig=False
                  for dd,lvl,src,urort in gyldige:
                      # er niveauet swept - ogsaa af DENNE bar (regel C)?
                      ramt = (l<=lvl) if below else (h>=lvl)
                      taget = (not urort) or ramt
                      if not taget:
                          be=lvl; beSrc=src; break
                      if src in ('session','EQ'):
                          ugyldig=True; break
                      # 15m/5m eller 25EQ: spring videre
                  if beStreng and ugyldig:
                      tradesToday-=1
                      continue
                  if beNoTaken and be is None:
                      tradesToday-=1
                      continue
                  live.append(dict(src=armSrc, beSrc=beSrc, hiS=hiSide, loS=loSide, short=below, entry=entry, sl=sl, tp=tp, be=be,
                                   beHit=False, live=True, dag=DAG[i], t=HHMM[i],
                                   exit=None, exit_t=None, reason=None, R=None))
        if armed and MINB[i]!=armMinB: armed=False
        if armed and bothSideBlock and hiSide and loSide: armed=False

        prev_on={'a':aOn,'l':lOn,'n':nOn}; prev_inNy=inNy

    for t in live:
        t['reason']='AABEN'; t['R']=0.0; trades.append(t)
    return pd.DataFrame(trades)

if __name__=="__main__":
    SP=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    df=run(SP+"/vendata","2026-01-02","2026-09-11")
    df.to_csv('/tmp/smt_backtest.csv',index=False)
    print("SMT-backtest 2026: %d handler  %+.2f R" % (len(df), df.R.sum()))
    print(df.reason.value_counts().to_dict())
    print(df.groupby(df.dag.str[:7]).R.agg(['count','sum']).round(2).to_string())
