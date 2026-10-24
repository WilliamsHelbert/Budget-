"""
FVG-model (ny, 22/10-26) - foerste udkast.

Short (long spejlvendt):
 1. Benet ned fra dagens top (siden 15:30 dansk) tager et session LOW (Asia / London / NY PRE) = sweep.
 2. Benet ned: fra toppen til det laveste punkt (efter sweepet). Bearish 5m FVG'er
    i benet taelles fra BUNDEN (nr. 1 = naermest lowet).
 3. Reaktion: prisen retracer op og rammer 5m FVG nr. 2 (high >= dens bund).
 4. Retracement-benet = fra benets low op til toppen af retracementet. Her findes
    bullish FVG'er paa 1m, 2m, 3m, 4m og 5m. Det hoejeste timeframe med en FVG
    bruges (kommer der en hoejere TF-FVG foer entry, skiftes der til den).
 5. Entry: en candle paa den FVG's timeframe lukker under FVG'ens bund.
 6. SL: toppen af retracementet. TP: aaben - der maales MFE og flere R-maal.
"""
import sys
import pandas as pd

TZ = "America/New_York"
SESS = {"Asia": ("20:00", "02:00"), "London": ("02:00", "08:00"), "NY PRE": ("08:00", "09:30")}
WIN = ("09:30", "12:00")       # sweep + entry (NY-tid) = 15:30-18:00 dansk
LEG_FROM = "08:00"             # benets top kan ligge fra 14:00 dansk (fx NY PRE high kl. 15:00, 9/1-26)
TFS = [5, 4, 3, 2, 1]
EXTRA = set()                  # ekstra sweep-niveauer: "PDH" (forrige dags high/low), "4h" (4h-candles sidste 24 timer),
                               # "4h dag" (dagens 4h-candles fra 00:00 dansk, aktive naar de er lukket),
                               # "4h alle" (alle urorte 4h highs/lows de sidste 7 dage + dagens)
FVG_FALLBACK = True            # kun 1 FVG i benet -> reaktion ind i den (12/1-26)
FVG_NR = 2                     # hvilken 5m FVG (fra bunden af benet) retracementet skal ramme
MULTI = False                  # flere trades per dag: naeste setup kan starte naar forrige trade er ude (SL/TP)
TP_FUNC = None                 # MULTI: egen TP-funktion (d, day, tc, ben_ende, short, entry, risk) -> pris/None
EXIT_END = None                # MULTI: (day, tc) -> seneste exit-tid (standard 16:59:45 NY)
RECLAIM = False                # sweep kraever en 5m close tilbage over swept low (under swept high) foer entry
CONSUME = False                # et niveau er brugt, naar foerste bar krydser det (kan ikke sweepes igen i et nyt ben)
RECLAIM_ALL = False            # True: over det hoejeste low (laveste high) benet har taget, ikke kun det sidste
PRE = None                     # fx pd.Timedelta(hours=6): vinduet og benet starter saa meget foer (doegn-overlap, BTC)
MAX_SWEEP_ENTRY = None         # fx pd.Timedelta(hours=2): max tid fra sweep til entry
MIN_RR = 0.5                   # MULTI: trade under min RR til 4h TP tages ikke (setuppet springes over)


def load(path):
    d = pd.read_parquet(path).set_index("time")
    d.index = d.index.tz_convert(TZ)
    return d[["open", "high", "low", "close"]]


def levels(d, day):
    day = pd.Timestamp(day)
    prev = day - pd.Timedelta(days=1)
    # mandag: Asia starter soendag aften
    out = {}
    for nm, (a, b) in SESS.items():
        s = pd.Timestamp(f"{(prev if nm == 'Asia' else day).date()} {a}").tz_localize(TZ)
        e = pd.Timestamp(f"{day.date()} {b}").tz_localize(TZ)
        x = d[s:e - pd.Timedelta(seconds=1)]
        if len(x):
            out[nm] = (x.high.max(), x.low.min(), e)
    ws = pd.Timestamp(f"{day.date()} {WIN[0]}").tz_localize(TZ)
    if "PDH" in EXTRA:
        # forrige CME-dag: 18:00 i forgaars -> 17:00 i gaar (NY)
        y = d[pd.Timestamp(f"{(prev - pd.Timedelta(days=1)).date()} 18:00").tz_localize(TZ):pd.Timestamp(f"{prev.date()} 17:00").tz_localize(TZ) - pd.Timedelta(seconds=1)]
        if day.weekday() == 0:   # mandag: fredagens dag
            y = d[pd.Timestamp(f"{(day - pd.Timedelta(days=4)).date()} 18:00").tz_localize(TZ):pd.Timestamp(f"{(day - pd.Timedelta(days=3)).date()} 17:00").tz_localize(TZ) - pd.Timedelta(seconds=1)]
        if len(y):
            out["PDH/PDL"] = (y.high.max(), y.low.min(), y.index[-1] + pd.Timedelta(seconds=15))
    if "4h dag" in EXTRA or "4h alle" in EXTRA:
        s0 = pd.Timestamp(f"{prev.date()} 18:00").tz_localize(TZ)       # 00:00 dansk
        if day.weekday() == 0:
            s0 = pd.Timestamp(f"{(day - pd.Timedelta(days=1)).date()} 18:00").tz_localize(TZ)
        if "4h alle" in EXTRA:
            s0 = s0 - pd.Timedelta(days=7)
        we = pd.Timestamp(f"{day.date()} {WIN[1]}").tz_localize(TZ)
        x = d[s0:we - pd.Timedelta(seconds=1)]
        h4 = x.resample("4h", offset="2h").agg({"high": "max", "low": "min"}).dropna()
        for t, r in h4.iterrows():
            e = t + pd.Timedelta(hours=4)
            if t < s0 or e > we:
                continue
            nm = f"4h {(t + pd.Timedelta(hours=6)):%d/%m %H:%M}" if "4h alle" in EXTRA else f"4h {(t + pd.Timedelta(hours=6)):%H:%M}"
            out[nm] = (r.high, r.low, e)
    if "4h" in EXTRA:
        x = d[ws - pd.Timedelta(hours=28):ws - pd.Timedelta(seconds=1)]
        h4 = x.resample("4h", offset="2h").agg({"high": "max", "low": "min"}).dropna()
        for t, r in h4.iterrows():
            e = t + pd.Timedelta(hours=4)
            if ws - pd.Timedelta(hours=24) <= e <= ws:
                out[f"4h {(t + pd.Timedelta(hours=6)):%H:%M}"] = (r.high, r.low, e)
    return out


def bars(x, m):
    return x.resample(f"{m}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def fvgs(b, bull, t0, t1):
    """FVG'er hvis 3. candle lukker i [t0, t1]. bull: low[i] > high[i-2]. Returnerer (bund, top, tid for 3. candle)."""
    r = []
    H, L, T = b.high.values, b.low.values, b.index
    for i in range(2, len(b)):
        if T[i - 2] < t0 or T[i] > t1:
            continue
        if bull and L[i] > H[i - 2]:
            r.append((H[i - 2], L[i], T[i]))
        if not bull and H[i] < L[i - 2]:
            r.append((H[i], L[i - 2], T[i]))
    return r


def tp4h(d, s, ref, short):
    """4h-trappen: foerste faerdige 4h low/high forbi ref (benets ende), saa videre bagud mens det bliver lavere/hoejere."""
    h4 = d[s - pd.Timedelta(days=12):s].resample("4h", offset="2h").agg({"high": "max", "low": "min"}).dropna()
    c = h4[h4.index + pd.Timedelta(hours=4) <= s].iloc[::-1]
    v = c.low.values if short else c.high.values
    better = (lambda a, b: a < b) if short else (lambda a, b: a > b)
    i = next((k for k in range(len(v)) if better(v[k], ref)), None)
    if i is None:
        return None
    while i + 1 < len(v) and better(v[i + 1], v[i]):
        i += 1
    return v[i]


def exit_time(after, short, sl, tp):
    for t, h, l in zip(after.index, after.high.values, after.low.values):
        if ((h >= sl) if short else (l <= sl)) or (tp is not None and ((l <= tp) if short else (h >= tp))):
            return t + pd.Timedelta(seconds=15)
    return None


def run_day(d, day, log=print):
    lv = levels(d, day)
    ws = pd.Timestamp(f"{day} {WIN[0]}").tz_localize(TZ) - (PRE or pd.Timedelta(0))
    we = pd.Timestamp(f"{day} {WIN[1]}").tz_localize(TZ)
    x = d[ws - pd.Timedelta(hours=2):we + pd.Timedelta(hours=4)]
    m1 = bars(x, 1)
    tfb = {m: bars(x, m) for m in TFS}
    res = []
    for short in (True, False):
        sgn = 1 if short else -1
        # niveauer der stadig er urorte fra sessionens slut til vinduet
        lvl = {}; lvE = {}
        for nm, (hi, lo, e) in lv.items():
            v = lo if short else hi                     # short: sweep af et LOW, reaktion op, short paa inversionen
            pre = d[e:ws - pd.Timedelta(seconds=1)]
            taken = len(pre) and ((pre.low.min() < v) if short else (pre.high.max() > v))
            if not taken:
                lvl[nm] = v; lvE[nm] = e
        if not lvl:
            continue
        swept = None; top = None; topT = None; low = None; lowT = None
        tapped = False; rhi = None; rhiT = None; pick = None
        ls = pd.Timestamp(f"{day} {LEG_FROM}").tz_localize(TZ) - (PRE or pd.Timedelta(0))
        free = None                                     # MULTI: tidligst naeste setup (forrige trade ude)
        prev = None
        for t, r in m1[ls:we].iterrows():
            tc = t + pd.Timedelta(minutes=1)            # candlen er lukket
            if free is not None and t < free:
                continue
            hi, lo = (r.high, r.low) if short else (-r.low, -r.high)
            if CONSUME and prev is not None:
                pl, pt = prev
                for nm in [nm for nm, v in lvl.items() if pl < sgn * v and pt >= lvE[nm] and pt >= ws]:
                    del lvl[nm]
            prev = (lo, t)
            # benets top = hoejeste punkt siden LEG_FROM; ny top -> forfra
            if top is None or hi > top:
                top, topT, low, lowT = hi, t, lo, t
                swept = None; gone = set(); tapped = False; rhi = None; pick = None
                continue
            # benet ned: nyt low, og tager det et session-low = sweep
            if not tapped and lo < low:
                low, lowT = lo, t
                hit = [nm for nm, v in lvl.items() if lo < sgn * v and nm not in gone and t >= lvE[nm]] if t >= ws else []
                if hit:
                    # det sweep der taeller er det SIDSTE niveau der tages foer reaktionen
                    # (tidligere niveauer i samme displacement er bare en del af benet)
                    gone |= set(hit)
                    swept = " + ".join(hit); sweptT = t
                    sweptV = max(sgn * lvl[nm] for nm in gone if nm in lvl) if RECLAIM_ALL else min(sgn * lvl[nm] for nm in hit)
                    reclaimed = False
                    log(f"{t:%H:%M} sweep {' + '.join(hit)} {'low' if short else 'high'} ({sgn*lo})")
                continue
            if swept is None:
                continue
            # sweep-candlen selv taeller ikke: det skal vaere en senere 5m close
            if RECLAIM and not reclaimed and tc.minute % 5 == 0 and (tc - pd.Timedelta(minutes=5)) in tfb[5].index \
                    and tc - pd.Timedelta(minutes=5) > sweptT.floor("5min"):
                c5 = tfb[5].loc[tc - pd.Timedelta(minutes=5)].close
                if (c5 if short else -c5) > sweptV:
                    reclaimed = True
            b5 = tfb[5]
            leg = fvgs(b5 if short else b5.assign(high=-b5.low, low=-b5.high), False, topT.floor("5min"), lowT.floor("5min"))
            leg = [f for f in leg if f[2] + pd.Timedelta(minutes=5) <= tc]   # kun faerdige FVG'er
            leg = sorted(leg, key=lambda f: f[0])     # fra bunden
            if not tapped:
                nr = min(FVG_NR, len(leg)) if FVG_FALLBACK else FVG_NR
                if nr >= 1 and len(leg) >= nr and hi >= leg[nr - 1][0]:
                    f = leg[nr - 1]
                    tapped = True; rhi, rhiT = hi, t
                    log(f"{t:%H:%M} rammer 5m FVG nr. {nr} {sgn*f[0]}-{sgn*f[1]} (benet {sgn*top} -> {sgn*low}, {len(leg)} FVG'er)")
                continue
            if hi > rhi:
                rhi, rhiT = hi, t
            # 4. hoejeste TF med bullish FVG i retracement-benet
            for m in TFS:
                b = tfb[m]
                bb = b if short else b.assign(high=-b.low, low=-b.high)
                fs = fvgs(bb, True, lowT.floor(f"{m}min"), tc)
                fs = [f for f in fs if f[2] + pd.Timedelta(minutes=m) <= tc]
                if fs:
                    f = max(fs, key=lambda f: f[2])   # nyeste
                    if pick is None or m > pick[0]:
                        pick = (m, f)
                        log(f"{t:%H:%M} bruger {m}m FVG {sgn*f[0]}-{sgn*f[1]} (fra {f[2]:%H:%M})")
                    break
            if pick is None:
                continue
            m, f = pick
            if tc.minute % m or (tc - pd.Timedelta(minutes=m)) not in tfb[m].index:
                continue
            cb = tfb[m].loc[tc - pd.Timedelta(minutes=m)]
            cl = cb.close if short else -cb.close
            if cl < f[0] and RECLAIM and not reclaimed:
                continue
            if cl < f[0] and MAX_SWEEP_ENTRY is not None and tc - sweptT > MAX_SWEEP_ENTRY:
                continue
            if cl < f[0]:
                entry = sgn * cl; sl = sgn * rhi; risk = abs(sl - entry)
                after = d[tc:we + pd.Timedelta(hours=4)]
                row = dict(dato=day, tid=f"{tc:%H:%M}", retning="SHORT" if short else "LONG", sweep=swept, sweep_tid=f"{sweptT:%H:%M}", ts=tc, sweep_ts=sweptT,
                           fvg_tf=f"{m}m", entry=entry, sl=sl, risk=risk, ben_top=sgn * top, ben_low=sgn * low,
                           **outcome(after, short, entry, sl, risk))
                if not MULTI:
                    res.append(row)
                    log(f"{tc:%H:%M} ENTRY {'SHORT' if short else 'LONG'} {entry} SL {sl} ({risk:.2f} p) - {m}m-candle lukkede gennem FVG")
                    break
                tp = TP_FUNC(d, day, tc, sgn * low, short, entry, risk) if TP_FUNC else tp4h(d, tc, sgn * low, short)
                rr = abs(tp - entry) / risk if tp is not None else 0
                if rr >= MIN_RR:
                    res.append(dict(row, tp_4h=tp, rr=round(rr, 2)))
                    log(f"{tc:%H:%M} ENTRY {'SHORT' if short else 'LONG'} {entry} SL {sl} TP {tp} ({rr:.2f} RR) - {m}m-candle")
                    ex = exit_time(d[tc:EXIT_END(day, tc) if EXIT_END else pd.Timestamp(f"{day} 16:59:45").tz_localize(TZ)], short, sl, tp)
                    if ex is None:
                        break
                    free = ex
                else:
                    log(f"{tc:%H:%M} springer over: {rr:.2f} RR til 4h TP")
                    free = tc
                # niveauer der er taget frem til nu er brugt; nyt setup kraever et urort niveau
                def used(nm, v):
                    y = d[max(ws, lvE[nm]):free - pd.Timedelta(seconds=1)]
                    return len(y) and ((y.low.min() < v) if short else (y.high.max() > v))
                lvl = {nm: v for nm, v in lvl.items() if not used(nm, v)}
                if not lvl:
                    break
                top = None; swept = None; tapped = False; pick = None
    return res


def outcome(after, short, entry, sl, risk):
    """MFE i R foer SL, og om 1R/2R/3R naas foer SL (15s-oploesning)."""
    mfe = 0.0; out = {}
    hitSL = None
    for t, r in after.iterrows():
        adv = (entry - r.low) if short else (r.high - entry)
        bad = (r.high >= sl) if short else (r.low <= sl)
        mfe = max(mfe, adv / risk)
        for k in (1, 2, 3):
            if f"{k}R" not in out and mfe >= k:
                out[f"{k}R"] = f"{t:%H:%M}"
        if bad:
            hitSL = f"{t:%H:%M}"
            break
    return dict(mfe_R=round(mfe, 2), sl_ramt=hitSL, **{f"{k}R": out.get(f"{k}R", "-") for k in (1, 2, 3)})


if __name__ == "__main__":
    if "--multi" in sys.argv:
        sys.argv.remove("--multi"); MULTI = True
    path, a, b = sys.argv[1:4]
    d = load(path)
    rows = []
    for day in pd.bdate_range(a, b):
        ds = f"{day:%Y-%m-%d}"
        print(f"== {ds}")
        rows += run_day(d, ds)
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    if len(sys.argv) > 4:
        df.to_csv(sys.argv[4], index=False)
