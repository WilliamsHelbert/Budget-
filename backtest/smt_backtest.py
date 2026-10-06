"""
Backtest af "Helbert's Hjaelpe Indikator (Sweep Trade)" (SMT) - v2.6.

Foelger Pine-scriptet bar for bar paa 15s-data:
  chart  = NQ  (a)
  sammenlign = ES (b)

Niveauer : Asia / London / NY PRE high+low og NY PRE 15m highs/lows
           (samme regler som Session Levels: 15m-niveauer der bliver taget
           under NY PRE er doede, 15m gaelder til 15:31).
SMT      : kun det ene indeks sweeper (mindst 1 tick), og i SAMME minut
           lukker et 15s-candle tilbage paa den anden side paa det indeks,
           begge indeks lukker i trade-retningen, og SL <= 30 points.
Ugyldig  : high-side og low-side swept i samme minut FOER/I entry-candlen -> intet trade.
           Bliver den anden side taget efter entry, staar tradet.
SL       : 1m-candlens top/bund ved entry, mindst 10 points.
TP       : naermeste af EQ / session liq (uroert af NQ) 35-75 points, ellers 75.
BE       : naermeste af EQ, 0.25/0.75, session liq, 15m, 5m (kun 15:30),
           2-50 points; aktiv foerst efter 2 lukkede 15s-candles.
R        : points / 10 (som i journalen).
"""
import sys
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import pandas as pd

# Alt regnes i New York-tid, saa market open altid er 09:30 NY - ogsaa i ugerne
# hvor USA og Europa skifter sommertid paa forskellige datoer (open = 14:30 dansk).
# Tider i output vises som "dansk normaltid" (NY + 6 t), dvs. open = 15:30.
TZ = ZoneInfo("America/New_York")
TICK = 0.25

# ── indstillinger (samme som scriptets standard) ──
ASIA = (20 * 60, 2 * 60)          # 02:00-08:00 dansk (krydser midnat i NY-tid)
LON = (2 * 60, 8 * 60)            # 08:00-14:00 dansk
NY = (8 * 60, 9 * 60 + 30)        # 14:00-15:30 dansk
WIN_S, WIN_E = 9 * 60 + 30, 10 * 60
M15_END = 9 * 60 + 31
MIN_SL, MAX_SL = 10.0, 30.0
TP_MIN, TP_MAX = 35.0, 75.0
BE_MIN, BE_MAX = 2.0, 50.0
USE_369 = True   # kun minutter med tvaersum 3/6/9
USE_PRE = True   # EQ fra foer market open som BE-kandidat
USE_TAGET = True # Taget-regel (se scriptet v3.0)
DBG = None   # saet af datoer ('YYYY-MM-DD') -> LOG faar forklaringer for de dage
SNAP = None  # dict -> niveauer ved open pr. dag (til charts)
LOG = []
EQT_MODE = 'dist'   # live EQ / session liq taget i entry-minuttet: 'all' = altid ugyldigt, 'dist' = kun hvis niveauet ligger paa BE-siden af entry, 'off' = ignoreres
MODE = 'smt'       # 'smt' = Sweep Trade, 'vrg' = Vergence (begge indeks tager samme niveau)
VRG_GAP = 5        # Vergence: max minutter mellem de to sweeps
VRG_MOVED = 'until'  # 'until' = nye yderpunkter taeller indtil siden har haft sin foerste Vergence; Vergence: taeller et nyt yderpunkt efter et taget niveau som ny liq? (nej: kun frisk liq)
TID_CLOSE = 2      # entry paa sweep-candlen eller den naeste 15s-candle (0 = fra)
TID_REF_SMT = 'first'  # SMT: taelles fra foerste candle der tager niveauet (13/1/26 ugyldig)
TID_REF = 'first'  # Vergence: samme som SMT - fra foerste candle der tager niveauet ('last' = fra sweepets yderpunkt)
VRG_ONESIDE = False # Vergence: efter en Vergence uden trade er siden lukket (indtil et trade)
VRG_ALLBACK = False # Vergence: begge indeks skal staa tilbage forbi niveauet ved entry
VRG_SAMELVL = True  # Vergence: begge indeks skal have taget samme niveau
VRG_SAMEMIN = True # Vergence: entry skal vaere i samme minut som sweepet
VRG_FIRST = 'both' # 'both' = foerste close hvor begge lukker i retningen afgoer; 'any' = foerste close hvor bare et af dem goer
PRE_INVALID = True  # EQ foer open ramt i entry-minuttet -> ugyldigt (False = test)
EQ_RESET = True    # nulstil live EQ'er ved open (som EQ-indikatoren)
USE_MBAD = True    # high- og low-side taget i samme minut -> ingen nye trades i minuttet
ONE_PER_MIN = True # kun eet trade pr. minut (det foerste)
USE_TOOK = True    # naermeste BE er en session-liq der allerede er taget i vinduet -> ugyldigt
USE_SESS_BE = True # session-liq som BE-kandidat (ogsaa i Vergence)
USE_15M_BE = True  # 15m-niveauer som BE-kandidat
USE_5M = True      # 5m-niveauer som BE-kandidat i aabningsminuttet
PRICE_REF = None   # fx 25000: SL/TP/BE og R skaleres med NQ-prisen (None = faste point)
SCALE_TP_ONLY = False  # kun TP skaleres (SL/BE/R faste)
KDAY = None        # {dato: faktor} - skaler SL/TP/BE/R pr. dag (fx efter volatilitet)
NEED_BE = False    # test: tradet kraever et BE der ligger foer TP
BE2 = True         # ingen BE i de foerste 2 15s-candles efter entry
VRG_BACK = True    # Vergence: indekset der tog frisk liq skal lukke tilbage forbi den
VRG_BOTHBACK = True  # Vergence: tog begge frisk liq i samme minut, skal begge lukke tilbage
VRG_ONESHOT = True # Vergence: foerste close hvor begge lukker i retningen afgoer (afvist = faerdigt)
CLOSE_BACK = True  # SMT: skal 15s-closet ogsaa lukke tilbage forbi niveauet? (dokumentet kraever det kun for Vergence)
DOJI_PREV = False  # test: entry-candlen skal ogsaa lukke forbi FORRIGE 15s-close (paa begge indeks)


def load(path):
    df = pd.read_parquet(path)
    if "ts" in df.columns:
        df["t"] = df["ts"].astype("int64")
        for c in ("open", "high", "low", "close"):
            df[c] = df[c] / 4.0
    else:
        df["t"] = df["time"].astype("int64") // 10**9
    return df[["t", "open", "high", "low", "close"]].sort_values("t").drop_duplicates("t")


@dataclass
class St:
    aM: int = None
    bM: int = None
    aDone: bool = False
    bDone: bool = False
    aTook: bool = False
    bTook: bool = False
    aTgT: bool = False
    bTgT: bool = False
    aPre: bool = False   # chartet tog niveauet FOER vinduet (saa er det ikke liq laengere)
    vDone: bool = False  # Vergence: tradet (eller afvist) - kraever et nyt sweep for at arme igen
    aOn: bool = False    # (ubrugt)
    bOn: bool = False
    aLv: float = None    # Vergence: niveauet efter det er taget i vinduet = NQ's yderpunkt siden
    aT: int = None       # tid (sek.) for sweepet
    bT: int = None
    aX: float = None     # sweepets yderpunkt indtil nu (til TID_REF='last')
    bX: float = None
    bLv: float = None


@dataclass
class Sess:
    aHi: float = None
    aLo: float = None
    bHi: float = None
    bLo: float = None
    hi: St = None
    lo: St = None
    aHiM: int = None
    bHiM: int = None
    aLoM: int = None
    bLoM: int = None
    aTgH: float = None
    bTgH: float = None
    aTgL: float = None
    bTgL: float = None
    maHi: bool = False  # NQ tog high i en senere session -> flyttet med (fx "NY PRE + London")
    mbHi: bool = False  # ES ditto
    maLo: bool = False
    mbLo: bool = False


@dataclass
class Lv:
    a: float
    b: float
    isHi: bool
    dead: bool = False
    st: St = field(default_factory=St)
    tm: int = None     # 15m-candlens start (epoch sek.)


@dataclass
class Hit:
    fired: bool = False
    isShort: bool = False
    lvl: float = None
    src: str = ""
    who: str = ""
    swHi: bool = False
    swLo: bool = False
    sHi: bool = False
    sLo: bool = False
    both: bool = False
    noDir: bool = False
    slBad: bool = False
    info: str = ""
    varmList: list = field(default_factory=list)   # Vergence: [(short, NQ-niveau, ES-niveau, samme minut, navn)]


def run(nq_path, es_path, start, end):
    global MIN_SL, MAX_SL, TP_MIN, TP_MAX, BE_MIN, BE_MAX
    base = (MIN_SL, MAX_SL, TP_MIN, TP_MAX, BE_MIN, BE_MAX)
    try:
        return _run(nq_path, es_path, start, end, base)
    finally:
        MIN_SL, MAX_SL, TP_MIN, TP_MAX, BE_MIN, BE_MAX = base


def _run(nq_path, es_path, start, end, base):
    global MIN_SL, MAX_SL, TP_MIN, TP_MAX, BE_MIN, BE_MAX
    scaleDay, kScale = None, 1.0
    a = load(nq_path)
    b = load(es_path)
    t0 = int(pd.Timestamp(start, tz=TZ).timestamp()) - 2 * 86400
    t1 = int(pd.Timestamp(end, tz=TZ).timestamp()) + 86400
    a = a[(a.t >= t0) & (a.t < t1)].reset_index(drop=True)
    b = b[(b.t >= t0) & (b.t < t1)]
    # ES paa NQ's bars, gaps_off = forrige ES-bar
    b = b.set_index("t").reindex(a.t).ffill()

    # 15m / 5m: forrige afsluttede candle (lookahead_on + [1])
    def agg(df_t, df, sec):
        g = df.groupby(df_t // sec * sec).agg(h=("high", "max"), l=("low", "min"))
        return g

    aa = a.set_index("t")
    g15a, g15b = agg(aa.index.to_series(), aa, 900), None
    bb_raw = load(es_path)
    bb_raw = bb_raw[(bb_raw.t >= t0) & (bb_raw.t < t1)].set_index("t")
    g15b = agg(bb_raw.index.to_series(), bb_raw, 900)
    g05a = agg(aa.index.to_series(), aa, 300)
    g05b = agg(bb_raw.index.to_series(), bb_raw, 300)

    def prev_period(g, p):
        idx = g.index.searchsorted(p) - 1
        if idx < 0:
            return None
        return g.index[idx]

    T = a.t.values
    O, H, L, C = a.open.values, a.high.values, a.low.values, a.close.values
    BO, BH, BL, BC = b.open.values, b.high.values, b.low.values, b.close.values
    PC = a.close.shift(1).values
    PBC = b.close.shift(1).values

    asia, lon, ny = Sess(), Sess(), Sess()
    lv15, lv05 = [], []
    preDead = {}
    prevOn = {"a": False, "l": False, "n": False}
    lastQt = lastFt = None
    prevMn = None
    m1Hi = m1Lo = None
    bm1Hi = bm1Lo = None
    prevQ15 = aq15Hi = aq15Lo = bq15Hi = bq15Lo = None
    # EQ (1m)
    lastMin = None
    curMinOHLC = None
    dAct = uAct = False
    dTop = dBot = uTop = uBot = None
    dLastMid = uLastMid = preD = preU = None
    pDT = pDB = pUB = pUT = None
    preDHitM = preUHitM = None
    dHitM = uHitM = sHiM = sLoM = None
    lastTradeM = None
    vArms = []
    vSide = {s_: dict(aF=[], bF=[], aE=None, bE=None, aFL=None, bFL=None, aFM=None, bFM=None, new=False, had=False, dead=False) for s_ in (True, False)}
    vDay = None
    resetDay = None
    hitsD, hitsU, hitsSH, hitsSL = [], [], [], []   # (tid, niveau) ramt i vinduet
    dHitT = uHitT = sHiT = sLoT = preDHitT = preUHitT = None
    # minut-status
    curM = None
    mHi = mLo = mBad = False
    minTrades = []
    trades = []
    stats = {"noDir": 0, "slBad": 0, "both": 0, "ugyldig": 0}
    o = None  # aabent trade

    for i in range(len(T)):
        t = int(T[i])
        lt = pd.Timestamp(t, unit="s", tz="UTC").tz_convert(TZ)
        tMin = lt.hour * 60 + lt.minute
        inWin = WIN_S <= tMin < WIN_E
        isOpenM = tMin == WIN_S
        ds = lt.minute // 10 + lt.minute % 10
        is369 = (not USE_369) or ds in (3, 6, 9)
        minB = t // 60
        dstr = lt.strftime('%Y-%m-%d')
        dk = lt + pd.Timedelta(hours=6)   # visning: dansk normaltid
        hi, lo, cl, op = H[i], L[i], C[i], O[i]
        bh, bl, bc, bo = BH[i], BL[i], BC[i], BO[i]
        pcl, pbc = PC[i], PBC[i]
        bok = not pd.isna(bc)

        newMin = lt.minute != prevMn
        prevMn = lt.minute
        m1Hi = hi if newMin or m1Hi is None else max(m1Hi, hi)
        m1Lo = lo if newMin or m1Lo is None else min(m1Lo, lo)
        if bok:
            bm1Hi = bh if newMin or bm1Hi is None else max(bm1Hi, bh)
            bm1Lo = bl if newMin or bm1Lo is None else min(bm1Lo, bl)
        q15B = t // 900
        newQ15 = q15B != prevQ15
        prevQ15 = q15B
        aq15Hi = hi if newQ15 or aq15Hi is None else max(aq15Hi, hi)
        aq15Lo = lo if newQ15 or aq15Lo is None else min(aq15Lo, lo)
        if bok:
            bq15Hi = bh if newQ15 or bq15Hi is None else max(bq15Hi, bh)
            bq15Lo = bl if newQ15 or bq15Lo is None else min(bq15Lo, bl)

        aOn = tMin >= ASIA[0] or tMin < ASIA[1]
        lOn = LON[0] <= tMin < LON[1]
        nOn = NY[0] <= tMin < NY[1]
        aStart, lStart, nStart = aOn and not prevOn["a"], lOn and not prevOn["l"], nOn and not prevOn["n"]
        prevOn.update(a=aOn, l=lOn, n=nOn)

        def build(s, isStart):
            if isStart:
                s.aHi, s.aLo = hi, lo
                s.bHi, s.bLo = (bh, bl) if bok else (None, None)
                s.hi, s.lo = St(), St()
                s.aHiM = s.bHiM = s.aLoM = s.bLoM = q15B
                s.aTgH = s.bTgH = s.aTgL = s.bTgL = None
                s.maHi = s.mbHi = s.maLo = s.mbLo = False
            else:
                if hi >= s.aHi:
                    s.aHiM = q15B
                if lo <= s.aLo:
                    s.aLoM = q15B
                if bok and (s.bHi is None or bh >= s.bHi):
                    s.bHiM = q15B
                if bok and (s.bLo is None or bl <= s.bLo):
                    s.bLoM = q15B
                s.aHi, s.aLo = max(s.aHi, hi), min(s.aLo, lo)
                if bok:
                    s.bHi = bh if s.bHi is None else max(s.bHi, bh)
                    s.bLo = bl if s.bLo is None else min(s.bLo, bl)
            if s.aHiM == q15B:
                s.bTgH = bq15Hi
            if s.bHiM == q15B:
                s.aTgH = aq15Hi
            if s.aLoM == q15B:
                s.bTgL = bq15Lo
            if s.bLoM == q15B:
                s.aTgL = aq15Lo

        def tg(s, isHi):
            if not USE_TAGET or ((s.maHi or s.mbHi) if isHi else (s.maLo or s.mbLo)):
                return None, None
            if isHi:
                return (s.aTgH, s.bTgH) if s.aHiM != s.bHiM else (None, None)
            return (s.aTgL, s.bTgL) if s.aLoM != s.bLoM else (None, None)

        # Tager et indeks en tidligere sessions high/low i en senere session (foer open),
        # er niveauet ikke brugt - det flytter med til den nye high/low (fx "NY PRE + London").
        def merge(s, on):
            if on or s.aHi is None or tMin >= WIN_S:
                return
            if hi > s.aHi:
                s.aHi, s.maHi = hi, True
            if lo < s.aLo:
                s.aLo, s.maLo = lo, True
            if bok and s.bHi is not None and bh > s.bHi:
                s.bHi, s.mbHi = bh, True
            if bok and s.bLo is not None and bl < s.bLo:
                s.bLo, s.mbLo = bl, True
        merge(asia, aOn)
        merge(lon, lOn)

        if aOn:
            build(asia, aStart)
        if lOn:
            build(lon, lStart)
        if nOn:
            build(ny, nStart)

        # 15m / 5m niveauer
        qT = prev_period(g15a, t // 900 * 900)
        fT = prev_period(g05a, t // 300 * 300)
        newM15 = qT is not None and qT != lastQt
        if newM15:
            lastQt = qT
        newM05 = fT is not None and fT != lastFt
        if newM05:
            lastFt = fT

        def inNyAt(pt):
            if pt is None:
                return False
            ll = pd.Timestamp(pt, unit="s", tz="UTC").tz_convert(TZ)
            m = ll.hour * 60 + ll.minute
            return NY[0] <= m < WIN_S

        if nStart:
            lv15, lv05 = [], []
        if newM15 and inNyAt(qT):
            eT = prev_period(g15b, t // 900 * 900)
            if eT is not None:
                qa, qb = g15a.loc[qT], g15b.loc[eT]
                lv15 += [Lv(qa.h, qb.h, True, tm=qT), Lv(qa.l, qb.l, False, tm=qT)]
        if newM05 and inNyAt(fT):
            gT = prev_period(g05b, t // 300 * 300)
            if gT is not None:
                fa, fb = g05a.loc[fT], g05b.loc[gT]
                lv05 += [Lv(fa.h, fb.h, True), Lv(fa.l, fb.l, False)]
        if nOn:
            for m in lv15 + lv05:
                aHit = hi >= m.a if m.isHi else lo <= m.a
                bHit = bok and (bh >= m.b if m.isHi else bl <= m.b)
                if aHit or bHit:
                    m.dead = True
        else:
            for m in lv05:
                if (hi >= m.a) if m.isHi else (lo <= m.a):
                    m.st.aTook = True

        # tjek niveauer
        if MODE == 'vrg' and inWin and vDay != dstr:
            vDay = dstr
            for s_ in (True, False):
                vSide[s_].update(aF=[], bF=[], aE=None, bE=None, aFL=None, bFL=None, aFM=None, bFM=None, new=False, had=False, dead=False)
        h = Hit()

        def check(st, aL, bL, isHi, nm, aTg=None, bTg=None):
            if st is None or aL is None or bL is None:
                return
            aSweep = hi >= aL + TICK if isHi else lo <= aL - TICK
            bSweep = bok and (bh >= bL + TICK if isHi else bl <= bL - TICK)
            lvlNm = nm + (" high" if isHi else " low")
            # session high/low taget i vinduet (kun foerste gang - et allerede taget niveau taeller ikke)
            if inWin and aSweep and not st.aTook and nm != "15m":
                if isHi:
                    h.sHi = True
                    hitsSH.append((t, aL))
                else:
                    h.sLo = True
                    hitsSL.append((t, aL))
            if aSweep:
                st.aTook = True
            if bSweep:
                st.bTook = True
            newTg = False
            if inWin and aTg is not None and not st.aTgT and \
                    ((aTg < aL and hi >= aTg + TICK) if isHi else (aTg > aL and lo <= aTg - TICK)):
                st.aTgT = newTg = True
            if inWin and bok and bTg is not None and not st.bTgT and \
                    ((bTg < bL and bh >= bTg + TICK) if isHi else (bTg > bL and bl <= bTg - TICK)):
                st.bTgT = newTg = True
            aTk = st.aTook or st.aTgT
            bTk = st.bTook or st.bTgT
            dbgOn = DBG is not None and dstr in DBG and WIN_S <= tMin < WIN_E
            if dbgOn and isOpenM and lt.second == 0:
                LOG.append((dstr, dk.strftime("%H:%M:%S"), f"STATUS {lvlNm}: NQ {aL} (taget foer: {st.aDone}) ES {bL} (taget foer: {st.bDone}) TagetNQ {aTg} TagetES {bTg}"))
            if dbgOn and (aSweep or bSweep or newTg):
                LOG.append((dstr, dk.strftime("%H:%M:%S"), f"SWEEP {lvlNm}: NQ={'JA' if aSweep else 'nej'} ES={'JA' if bSweep else 'nej'} | NQ taget={aTk} ES taget={bTk} doneA={st.aDone} doneB={st.bDone} 369={is369} TagetSweep={newTg}"))
            if MODE == 'vrg':
                # Vergence: et niveau taget foerste gang i vinduet = FRISK liq. Bagefter flytter
                # niveauet med til indeksets nye yderpunkt; et nyt yderpunkt = ny liq (ikke frisk).
                if not inWin:
                    return
                curA = st.aLv if st.aLv is not None else aL
                curB = st.bLv if st.bLv is not None else bL
                newA = (hi >= curA + TICK) if isHi else (lo <= curA - TICK)
                newB = bok and ((bh >= curB + TICK) if isHi else (bl <= curB - TICK))
                sd = vSide[isHi]
                ext = max if isHi else min
                if newA:
                    if st.aLv is None:      # frisk
                        sd['aF'].append([minB, aL, lvlNm, False])
                        sd['aFL'] = aL if sd.get('aFM') != minB or sd['aFL'] is None else (max if isHi else min)(sd['aFL'], aL)
                        sd['aFM'] = minB
                    if VRG_MOVED is True or curA == aL or (VRG_MOVED == 'until' and not sd['had']):
                        sd['aE'] = minB
                        sd['new'] = True
                    st.aLv = hi if isHi else lo
                if newB:
                    if st.bLv is None:
                        sd['bF'].append([minB, bL, lvlNm, False])
                        sd['bFL'] = bL if sd.get('bFM') != minB or sd['bFL'] is None else (max if isHi else min)(sd['bFL'], bL)
                        sd['bFM'] = minB
                    if VRG_MOVED is True or curB == bL or (VRG_MOVED == 'until' and not sd['had']):
                        sd['bE'] = minB
                        sd['new'] = True
                    st.bLv = bh if isHi else bl
                if newA or newB:
                    sd['xT'] = t
                    h.swHi = h.swHi or isHi
                    h.swLo = h.swLo or not isHi
                    if dbgOn:
                        LOG.append((dstr, dk.strftime("%H:%M:%S"), f"NY LIQ {lvlNm}: NQ={'FRISK' if newA and curA == aL else ('ny' if newA else '-')} ES={'FRISK' if newB and curB == bL else ('ny' if newB else '-')}"))
                return
            if not inWin:
                if aSweep:
                    st.aDone = True
                    st.aPre = True
                if bSweep:
                    st.bDone = True
                return
            newA = not st.aDone and st.aM is None and aSweep
            newB = not st.bDone and st.bM is None and bSweep
            if newA:
                st.aM, st.aT, st.aX = minB, t, (hi if isHi else lo)
            if newB:
                st.bM, st.bT, st.bX = minB, t, (bh if isHi else bl)
            if TID_REF_SMT == 'last' and not newA and st.aX is not None and not st.aDone and ((hi > st.aX) if isHi else (lo < st.aX)):
                st.aX, st.aT = (hi if isHi else lo), t
            if TID_REF_SMT == 'last' and not newB and st.bX is not None and not st.bDone and bok and ((bh > st.bX) if isHi else (bl < st.bX)):
                st.bX, st.bT = (bh if isHi else bl), t
            if newA or newB:
                h.swHi = h.swHi or isHi
                h.swLo = h.swLo or not isHi
            if (newA or newB or newTg) and aTk and bTk and not (st.aDone and st.bDone):
                h.both = True
                st.aDone = st.bDone = True
            if not is369:
                if newA:
                    st.aDone = True
                if newB:
                    st.bDone = True
            if not st.aDone and st.aM is not None and st.aM != minB:
                st.aDone = True
            if not st.bDone and st.bM is not None and st.bM != minB:
                st.bDone = True
            if not h.fired:
                dirOK = (cl < op and bok and bc < bo) if isHi else (cl > op and bok and bc > bo)
                if dirOK and DOJI_PREV:
                    dirOK = (cl < pcl and bc < pbc) if isHi else (cl > pcl and bc > pbc)
                aBack = not st.aDone and not bTk and st.aM == minB and (not CLOSE_BACK or (cl < aL if isHi else cl > aL))
                bBack = not st.bDone and not aTk and st.bM == minB and bok and (not CLOSE_BACK or (bc < bL if isHi else bc > bL))
                # Tid close: entry paa sweep-candlen eller de naeste TID_CLOSE-1 candles
                if TID_CLOSE and aBack and t - st.aT > 15 * (TID_CLOSE - 1):
                    aBack = False
                if TID_CLOSE and bBack and t - st.bT > 15 * (TID_CLOSE - 1):
                    bBack = False
                if not dirOK and (aBack or bBack):
                    h.noDir = True
                if dbgOn and (aBack or bBack):
                    LOG.append((dstr, dk.strftime("%H:%M:%S"), f"CLOSE TILBAGE {lvlNm} ({'NQ' if aBack else 'ES'}): NQ o/c {op}/{cl} ES o/c {bo}/{bc} retning OK={dirOK} SL={(m1Hi - cl) if isHi else (cl - m1Lo)}"))
                slOK = (m1Hi - cl <= MAX_SL) if isHi else (cl - m1Lo <= MAX_SL)
                if dirOK and (aBack or bBack) and not slOK:
                    h.slBad = True
                    st.aDone = st.bDone = True
                if dirOK and (aBack or bBack) and slOK:
                    h.fired, h.isShort, h.lvl, h.src = True, isHi, aL, lvlNm
                    h.who = "NQ + ES" if aBack and bBack else ("NQ" if aBack else "ES")
                    st.aDone = st.bDone = True

        if not nOn:
            check(ny.hi, ny.aHi, ny.bHi, True, "NY PRE", *tg(ny, True))
            check(ny.lo, ny.aLo, ny.bLo, False, "NY PRE", *tg(ny, False))
        # har BEGGE indeks taget niveauet i en senere session, er det samme niveau som
        # den senere sessions -> tjekkes kun dér
        if not lOn:
            if not (lon.maHi and lon.mbHi):
                check(lon.hi, lon.aHi, lon.bHi, True, "London", *tg(lon, True))
            if not (lon.maLo and lon.mbLo):
                check(lon.lo, lon.aLo, lon.bLo, False, "London", *tg(lon, False))
        if not aOn:
            if not (asia.maHi and asia.mbHi):
                check(asia.hi, asia.aHi, asia.bHi, True, "Asia", *tg(asia, True))
            if not (asia.maLo and asia.mbLo):
                check(asia.lo, asia.aLo, asia.bLo, False, "Asia", *tg(asia, False))
        if not nOn and tMin < M15_END:
            for m in lv15:
                isExt = abs(m.a - (ny.aHi or 0)) < TICK / 2 if m.isHi else abs(m.a - (ny.aLo or 0)) < TICK / 2
                if not m.dead and not isExt:
                    check(m.st, m.a, m.b, m.isHi, "15m")

        if h.sHi and sHiM != minB:
            sHiM, sHiT = minB, t
        if h.sLo and sLoM != minB:
            sLoM, sLoT = minB, t
        if inWin:
            stats["noDir"] += h.noDir
            stats["slBad"] += h.slBad
            stats["both"] += h.both

        # EQ paa 1m: vurder den netop lukkede minut-candle paa foerste bar i nyt minut
        new1m = lastMin is not None and minB != lastMin
        if new1m:
            o1, h1, l1, c1 = curMinOHLC
            own = (h1 + l1) / 2
            bearE = c1 < o1 and c1 < own
            bullE = c1 > o1 and c1 > own
            # 15:29-candlen (foer open) giver ikke en ny EQ efter open
            if EQ_RESET and inWin and tMin == WIN_S:
                bearE = bullE = False
        else:
            bearE = bullE = False
        if lastMin is None or minB != lastMin:
            curMinOHLC = [op, hi, lo, cl]
            lastMin = minB
        else:
            curMinOHLC[1] = max(curMinOHLC[1], hi)
            curMinOHLC[2] = min(curMinOHLC[2], lo)
            curMinOHLC[3] = cl
        # Market open: alle live EQ'er nulstilles (som EQ-indikatoren). EQ'en der stod
        # lige foer open er allerede gemt som "EQ foer open".
        # PRICE_REF: SL/TP/BE-graenser og R skaleres med NQ-prisen ved open (pris / PRICE_REF)
        if (PRICE_REF or KDAY) and inWin and scaleDay != dstr:
            scaleDay, kScale = dstr, (KDAY.get(dstr, 1.0) if KDAY else op / PRICE_REF)
            if SCALE_TP_ONLY:
                TP_MIN, TP_MAX = base[2] * kScale, base[3] * kScale
                kScale = 1.0
            else:
                MIN_SL, MAX_SL, TP_MIN, TP_MAX, BE_MIN, BE_MAX = (v * kScale for v in base)
        if EQ_RESET and inWin and resetDay != dstr:
            resetDay = dstr
            dAct = uAct = False
        if dAct:
            # tjek mod linjen FOER barens egen low flytter den
            if hi >= (dTop + dBot) / 2:
                dAct = False
                dLastMid = (dTop + dBot) / 2
                if dHitM != minB:
                    dHitT = t
                dHitM = minB
                hitsD.append((t, (dTop + dBot) / 2))
                if DBG is not None and dstr in DBG:
                    LOG.append((dstr, dk.strftime("%H:%M:%S"), f"BEARISH EQ RAMT: top {dTop} bund {dBot} EQ {(dTop + dBot) / 2}"))
            else:
                dBot = min(dBot, lo)
        if bearE and not dAct:
            dTop, dBot, dAct = h1, min(l1, lo), True
        if uAct:
            if lo <= (uBot + uTop) / 2:
                uAct = False
                uLastMid = (uBot + uTop) / 2
                if uHitM != minB:
                    uHitT = t
                uHitM = minB
                hitsU.append((t, (uBot + uTop) / 2))
                if DBG is not None and dstr in DBG:
                    LOG.append((dstr, dk.strftime("%H:%M:%S"), f"BULLISH EQ RAMT: bund {uBot} top {uTop} EQ {(uBot + uTop) / 2}"))
            else:
                uTop = max(uTop, hi)
        if bullE and not uAct:
            uBot, uTop, uAct = l1, max(h1, hi), True
        # EQ foer market open (til BE) - laases fra 15:30
        if tMin < WIN_S:
            preD = (dTop + dBot) / 2 if dAct else None   # kun en live EQ
            preU = (uBot + uTop) / 2 if uAct else None
            pDT, pDB = (dTop, dBot) if dAct else (None, None)
            pUB, pUT = (uBot, uTop) if uAct else (None, None)
            preDHitM = preUHitM = None
        else:
            # EQ foer open vokser videre efter open (som EQ-indikatoren), indtil den rammes.
            # Tjek mod linjen FOER barens egen low/high flytter den.
            if preDHitM is None and pDT is not None:
                if hi >= (pDT + pDB) / 2:
                    preDHitM, preDHitT = minB, t
                else:
                    pDB = min(pDB, lo)
                preD = (pDT + pDB) / 2
            if preUHitM is None and pUB is not None:
                if lo <= (pUB + pUT) / 2:
                    preUHitM, preUHitT = minB, t
                else:
                    pUT = max(pUT, hi)
                preU = (pUB + pUT) / 2

        # niveauer ved open til charts (SNAP = {} for at slaa til)
        if SNAP is not None and not inWin:
            preDead = {id(m): m.dead for m in lv15}
        if SNAP is not None and inWin and tMin == WIN_S and dstr not in SNAP:
            SNAP[dstr] = dict(
                sess={nm: [x.aHi, x.aLo, x.bHi, x.bLo] for nm, x in (("Asia", asia), ("London", lon), ("NY PRE", ny))},
                m15=[[m.a, m.b, m.isHi, preDead.get(id(m), False), m.tm] for m in lv15], preD=preD, preU=preU)
        # minut-status
        if minB != curM:
            curM, mHi, mLo, mBad = minB, False, False, False
            minTrades = []
        if inWin:
            mHi = mHi or h.swHi
            mLo = mLo or h.swLo
        justBad = USE_MBAD and mHi and mLo and not mBad
        if justBad:
            # kun trades FOER den anden side blev taget staar; ingen nye i minuttet
            mBad = True

        # aabent trade
        if o is not None:
            hitSL = hi >= o["sl"] if o["short"] else lo <= o["sl"]
            hitTP = lo <= o["tp"] if o["short"] else hi >= o["tp"]
            if hitSL or hitTP:
                tr = o["rec"]
                if hitSL:
                    pts = (o["entry"] - o["sl"]) if o["short"] else (o["sl"] - o["entry"])
                    tr["resultat"] = "BE" if o["beHit"] else "SL"
                else:
                    pts = abs(o["tp"] - o["entry"])
                    tr["resultat"] = "TP"
                tr["points"] = round(pts, 2)
                tr["R"] = round(pts / (10 * o.get("k", 1.0)), 2)
                tr["exit"] = dk.strftime("%H:%M:%S")
                o = None
            else:
                # BE: ikke i de foerste 2 15s-candles efter entry. Er BE-niveauet ramt i dem,
                # afgoeres det ved 2. close: prisen paa profit-siden af entry -> BE fra 3. candle,
                # ellers ingen BE (tradet bliver SL eller TP).
                if not o["beHit"] and o["be"] is not None and not o.get("noBE"):
                    touch = lo <= o["be"] if o["short"] else hi >= o["be"]
                    if BE2 and o["bars"] < 2:
                        if touch:
                            o["early"] = True
                        if o["bars"] == 1 and o.get("early"):
                            if (cl < o["entry"]) if o["short"] else (cl > o["entry"]):
                                o["beHit"] = True
                                o["sl"] = o["entry"]
                            else:
                                o["noBE"] = True
                    elif touch:
                        o["beHit"] = True
                        o["sl"] = o["entry"]
                o["bars"] += 1

        # nyt trade
        if DBG is not None and dstr in DBG and h.fired and mBad:
            LOG.append((dstr, dk.strftime("%H:%M:%S"), f"ENTRY BLOKERET: high- og low-side taget i samme minut ({h.src})"))
        if DBG is not None and dstr in DBG and inWin and h.both:
            LOG.append((dstr, dk.strftime("%H:%M:%S"), "BEGGE har taget niveauet -> ikke SMT"))
        # Vergence: arm naar begge har taget niveauet; FOERSTE 15s-close hvor begge lukker
        # i retningen (samme minut) afgoer: NQ skal lukke tilbage forbi niveauet (og ES ogsaa,
        # hvis begge sweepede i samme minut), og SL <= MAX_SL - ellers intet trade.
        if MODE == 'vrg':
            # Vergence pr. side: mindst et indeks har taget FRISK liq, og det andet har taget
            # liq paa samme side (frisk eller nyt yderpunkt) hoejst VRG_GAP min fra hinanden.
            for side in (True, False):
                sd = vSide[side]
                if sd['new']:
                    fa = [f for f in sd['aF'] if not f[3] and sd['bE'] is not None and abs(f[0] - sd['bE']) <= VRG_GAP]
                    fb = [f for f in sd['bF'] if not f[3] and sd['aE'] is not None and abs(f[0] - sd['aE']) <= VRG_GAP]
                    if VRG_SAMELVL:
                        # begge indeks skal have taget det samme niveau (fx begge London low)
                        nB = {x[2] for x in sd['bF']}
                        nA = {x[2] for x in sd['aF']}
                        fa = [f for f in fa if f[2] in nB]
                        fb = [f for f in fb if f[2] in nA]
                    if fa or fb:
                        ext = max if side else min
                        # kun det indeks der tager frisk liq i DETTE minut skal lukke tilbage
                        faN = [f for f in fa if f[0] == minB]
                        fbN = [f for f in fb if f[0] == minB]
                        if faN or fbN:
                            fa, fb = faN, fbN
                        if VRG_SAMELVL:
                            # close tilbage maales mod det yderste niveau indekset tog i samme minut
                            fa = [f for f in sd['aF'] if f[0] in {g[0] for g in fa}]
                            fb = [f for f in sd['bF'] if f[0] in {g[0] for g in fb}]
                        aLv = ext(f[1] for f in fa) if fa else None
                        bLv = ext(f[1] for f in fb) if fb else None
                        names = sorted({f[2] for f in fa + fb})
                        for f in fa + fb:
                            f[3] = True
                        sd['had'] = True
                        fm = lambda L: ",".join(f"{x[2]}@{x[0] % 60}" for x in L)
                        vinf = f"NQ[{fm(sd['aF'])}] e{None if sd['aE'] is None else sd['aE'] % 60} ES[{fm(sd['bF'])}] e{None if sd['bE'] is None else sd['bE'] % 60}"
                        if not (VRG_ONESIDE and sd['dead']):
                            h.varmList.append((side, aLv, bLv, vinf, " / ".join(names)))
                        elif DBG is not None and dstr in DBG:
                            LOG.append((dstr, dk.strftime("%H:%M:%S"), f"VERGENCE {' / '.join(names)} IGNORERET: siden har haft en Vergence uden trade"))
                        # en Vergence uden trade lukker siden; et trade aabner den igen
                        if VRG_ONESIDE is True:
                            sd['dead'] = True
                        if DBG is not None and dstr in DBG:
                            LOG.append((dstr, dk.strftime("%H:%M:%S"), f"VERGENCE {' / '.join(names)}: NQ frisk {aLv} ES frisk {bLv}"))
                sd['new'] = False
            # entry skal komme inden for 60 sek. efter det sweep der fuldendte Vergence.
            # Flere niveauer kan vaere armet samtidig - hvert afgoeres for sig.
            vArms = [v for v in vArms if ((v[5] // 60 == minB) if VRG_SAMEMIN else (t < v[5] + 60))]
            for vv in h.varmList:
                if not mBad:
                    vArms.append(vv + (t,))
            if vArms and not mBad:
                keep = []
                for vs, va, vb, vsame, vnm, vt in vArms:
                    tref = max(vt, vSide[vs].get('xT') or vt) if TID_REF == 'last' else vt
                    if TID_CLOSE and t - tref > 15 * (TID_CLOSE - 1):
                        continue   # Tid close: for sent efter sweepet
                    aD = (cl < op) if vs else (cl > op)
                    bD = bok and ((bc < bo) if vs else (bc > bo))
                    trig = (aD and bD) if VRG_FIRST == 'both' else ((aD or bD) if VRG_FIRST == 'any' else (aD if VRG_FIRST == 'nq' else True))
                    if not trig:
                        keep.append((vs, va, vb, vsame, vnm, vt))
                        continue
                    if not (aD and bD):
                        if DBG is not None and dstr in DBG:
                            LOG.append((dstr, dk.strftime("%H:%M:%S"), f"VERGENCE AFVIST {vnm}: ikke samme retning"))
                        continue
                    # tog begge indeks liq i samme minut, skal begge lukke tilbage forbi hver sin liq
                    sdv = vSide[vs]
                    am = vt // 60
                    if VRG_BOTHBACK and sdv.get('aFM') == am and sdv.get('bFM') == am:
                        va = va if va is not None else sdv['aFL']
                        vb = vb if vb is not None else sdv['bFL']
                    # de(t) indeks der tog FRISK liq skal lukke tilbage forbi den
                    backA = not VRG_BACK or va is None or (cl < va if vs else cl > va)
                    backB = not VRG_BACK or vb is None or (bok and (bc < vb if vs else bc > vb))
                    if VRG_ALLBACK:
                        # begge indeks skal staa tilbage forbi niveauet ved entry (ogsaa det der tog det foerst)
                        nm_ = set(vnm.split(" / ")); ext_ = max if vs else min
                        la = [f[1] for f in sdv['aF'] if f[2] in nm_]
                        lb = [f[1] for f in sdv['bF'] if f[2] in nm_]
                        if la:
                            backA = backA and (cl < ext_(la) if vs else cl > ext_(la))
                        if lb:
                            backB = backB and bok and (bc < ext_(lb) if vs else bc > ext_(lb))
                    backOK = backA and backB
                    slOK = (m1Hi - cl <= MAX_SL) if vs else (cl - m1Lo <= MAX_SL)
                    if backOK and slOK and not h.fired:
                        h.fired, h.isShort, h.lvl, h.src, h.info = True, vs, va, vnm, vsame or ""
                        h.who = "Begge" if va is not None and vb is not None else ("NQ" if va is not None else "ES")
                    elif VRG_ONESIDE == 'reject' and not (backOK and slOK) and not h.fired:
                        vSide[vs]['dead'] = True
                        if DBG is not None and dstr in DBG:
                            LOG.append((dstr, dk.strftime("%H:%M:%S"), f"VERGENCE AFVIST {vnm}: tilbage NQ={backA} ES={backB} SL ok={slOK} -> siden lukket"))
                    elif not VRG_ONESHOT and not (backOK and slOK):
                        keep.append((vs, va, vb, vsame, vnm, vt))
                    elif DBG is not None and dstr in DBG and not (backOK and slOK):
                        LOG.append((dstr, dk.strftime("%H:%M:%S"), f"VERGENCE AFVIST {vnm}: tilbage NQ={backA} ES={backB} SL ok={slOK}"))
                vArms = keep

        # kun eet trade pr. minut - et nyt signal i samme minut afloeser ikke det foerste
        if ONE_PER_MIN and h.fired and lastTradeM == minB:
            h.fired = False
        if h.fired and not mBad:
            sh, px = h.isShort, cl
            # BE
            cands = []
            elo = (uBot if uAct else None) if sh else (dBot if dAct else None)
            ehi = (uTop if uAct else None) if sh else (dTop if dAct else None)
            if elo is not None:
                cands += [((elo + ehi) / 2, "EQ", False), (elo + (0.75 if sh else 0.25) * (ehi - elo), "0.75" if sh else "0.25", False)]
            if USE_PRE:
                if preDHitM is None:
                    cands.append((preD, "EQ foer open", False))
                if preUHitM is None:
                    cands.append((preU, "EQ foer open", False))
            for nm, s in ((("Asia", asia), ("London", lon), ("NY PRE", ny)) if USE_SESS_BE else ()):
                st = s.lo if sh else s.hi
                # taget foer open -> ikke BE-kandidat. Taget i vinduet foer entry -> ugyldigt
                if st is not None and not st.aPre:
                    cands.append(((s.aLo if sh else s.aHi), nm + (" low" if sh else " high"), st.aTook))
            for m in (lv15 if USE_15M_BE else []):
                if m.isHi != sh and not m.dead and not m.st.aTook:
                    cands.append((m.a, "15m low" if sh else "15m high", False))
            if isOpenM and USE_5M:
                for m in lv05:
                    if m.isHi != sh and not m.dead and not m.st.aTook:
                        cands.append((m.a, "5m low" if sh else "5m high", False))
            be, beS, beBad = None, "-", False
            for cv, cn, tk in cands:
                if cv is None:
                    continue
                d = abs(px - cv)
                if (cv < px if sh else cv > px) and BE_MIN <= d <= BE_MAX and (be is None or d < abs(px - be)):
                    be, beS, beBad = cv, cn, tk and USE_TOOK
            # EQ fra foer open ramt i entry-minuttet -> BE-spottet er taget
            def hb(hm, ht):
                # ramt i dette minut, men FOER entry-candlen
                return hm == minB and ht is not None and ht < t

            def preTaken(eq, hm, ht):
                # EQ fra foer open: ogsaa ramt AF entry-candlen taeller (5/1)
                if eq is None or hm != minB:
                    return False
                d = (px - eq) if sh else (eq - px)
                return -BE_MIN <= d <= BE_MAX
            # kun EQ'en paa BE-siden: short -> bullish (under), long -> bearish (over)
            if USE_PRE and PRE_INVALID and ((preTaken(preU, preUHitM, preUHitT)) if sh else (preTaken(preD, preDHitM, preDHitT))):
                beBad, beS = True, "EQ foer open"
            # liq i trade-retningen taget i entry-minuttet (foer entry-candlen)
            m0 = minB * 60
            def anyHit(hits):
                for ht, hv in hits:
                    if m0 <= ht < t:
                        if EQT_MODE == 'all':
                            return True
                        d = (px - hv) if sh else (hv - px)
                        if d >= -BE_MIN:
                            return True
                return False
            if EQT_MODE == 'off':
                eqT = slT = False
            else:
                eqT = anyHit(hitsU) if sh else anyHit(hitsD)
                slT = USE_SESS_BE and (anyHit(hitsSL) if sh else anyHit(hitsSH))
            if eqT or slT:
                beBad = True
                beS = ("bullish EQ" if sh else "bearish EQ") if eqT else ("session low" if sh else "session high")
            # SL / TP
            sl = max(m1Hi, px + MIN_SL) if sh else min(m1Lo, px - MIN_SL)
            tcs = []
            if uAct:
                tcs.append(((uBot + uTop) / 2, "EQ"))
            if dAct:
                tcs.append(((dBot + dTop) / 2, "EQ"))
            for nm, s in (("Asia", asia), ("London", lon), ("NY PRE", ny)):
                st = s.lo if sh else s.hi
                if st is not None and not st.aTook:
                    tcs.append(((s.aLo if sh else s.aHi), nm + (" low" if sh else " high")))
            tp, tpS = None, "75p"
            for cv, cn in tcs:
                if cv is None:
                    continue
                d = (px - cv) if sh else (cv - px)
                if TP_MIN <= d <= TP_MAX and (tp is None or d < abs(px - tp)):
                    tp, tpS = cv, cn
            if tp is None:
                tp = px - TP_MAX if sh else px + TP_MAX
            noBE = NEED_BE and not beBad and (be is None or abs(be - px) >= abs(tp - px))
            if beBad or noBE:
                trades.append({
                    "dato": lt.strftime("%Y-%m-%d"), "tid": dk.strftime("%H:%M:%S"),
                    "retning": "SHORT" if sh else "LONG", "niveau": h.src, "swept": h.who,
                    "entry": px, "sl": None, "sl_pts": None, "tp": None, "tp_kilde": "", "be": be, "be_kilde": beS,
                    "status": "UGYLDIG (intet BE foer TP)" if noBE else "UGYLDIG (BE allerede ramt)", "resultat": "", "exit": "", "points": None, "R": None,
                })
                stats["beRamt"] = stats.get("beRamt", 0) + 1
                continue
            if o is not None:
                o["rec"]["resultat"] = "AFLOEST"
                o["rec"]["exit"] = dk.strftime("%H:%M:%S")
            rec = {
                "dato": lt.strftime("%Y-%m-%d"), "tid": dk.strftime("%H:%M:%S"),
                "retning": "SHORT" if sh else "LONG", "niveau": h.src, "swept": h.who, "vinfo": h.info,
                "entry": px, "sl": sl, "sl_pts": round(abs(px - sl), 2),
                "tp": tp, "tp_kilde": tpS, "be": be, "be_kilde": beS,
                "status": "OK", "resultat": "AABEN", "exit": "", "points": None, "R": None,
            }
            trades.append(rec)
            minTrades.append(rec)
            lastTradeM = minB
            if MODE == 'vrg':
                vSide[sh]['dead'] = False
            o = {"short": sh, "entry": px, "sl": sl, "tp": tp, "be": be, "beHit": False, "k": kScale,
                 "bars": 0, "minB": minB, "rec": rec}

    d0, d1 = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    out = [r for r in trades if d0 <= pd.Timestamp(r["dato"]).date() <= d1]
    return out, stats


if __name__ == "__main__":
    nq, es, start, end, csv_out = sys.argv[1:6]
    tr, stats = run(nq, es, start, end)
    df = pd.DataFrame(tr)
    df.to_csv(csv_out, index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    print(df.to_string(index=False))
    print(stats)
