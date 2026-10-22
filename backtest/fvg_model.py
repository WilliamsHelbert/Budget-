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
TFS = [5, 4, 3, 2, 1]
FVG_NR = 2                     # hvilken 5m FVG (fra bunden af benet) retracementet skal ramme


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


def run_day(d, day, log=print):
    lv = levels(d, day)
    ws = pd.Timestamp(f"{day} {WIN[0]}").tz_localize(TZ)
    we = pd.Timestamp(f"{day} {WIN[1]}").tz_localize(TZ)
    x = d[ws - pd.Timedelta(hours=2):we + pd.Timedelta(hours=4)]
    m1 = bars(x, 1)
    tfb = {m: bars(x, m) for m in TFS}
    res = []
    for short in (True, False):
        sgn = 1 if short else -1
        # niveauer der stadig er urorte fra sessionens slut til vinduet
        lvl = {}
        for nm, (hi, lo, e) in lv.items():
            v = lo if short else hi                     # short: sweep af et LOW, reaktion op, short paa inversionen
            pre = d[e:ws - pd.Timedelta(seconds=1)]
            taken = len(pre) and ((pre.low.min() < v) if short else (pre.high.max() > v))
            if not taken:
                lvl[nm] = v
        if not lvl:
            continue
        swept = None; top = None; topT = None; low = None; lowT = None
        tapped = False; rhi = None; rhiT = None; pick = None
        for t, r in m1[ws:we].iterrows():
            tc = t + pd.Timedelta(minutes=1)            # candlen er lukket
            hi, lo = (r.high, r.low) if short else (-r.low, -r.high)
            # benets top = hoejeste punkt siden vinduet startede; ny top -> forfra
            if top is None or hi > top:
                top, topT, low, lowT = hi, t, lo, t
                swept = None; tapped = False; rhi = None; pick = None
                continue
            # benet ned: nyt low, og tager det et session-low = sweep
            if not tapped and lo < low:
                low, lowT = lo, t
                hit = [nm for nm, v in lvl.items() if lo < sgn * v and (swept is None or nm not in swept)]
                if hit:
                    swept = " + ".join(([swept] if swept else []) + hit)
                    log(f"{t:%H:%M} sweep {' + '.join(hit)} {'low' if short else 'high'} ({sgn*lo})")
                continue
            if swept is None:
                continue
            b5 = tfb[5]
            leg = fvgs(b5 if short else b5.assign(high=-b5.low, low=-b5.high), False, topT.floor("5min"), lowT.floor("5min"))
            leg = [f for f in leg if f[2] + pd.Timedelta(minutes=5) <= tc]   # kun faerdige FVG'er
            leg = sorted(leg, key=lambda f: f[0])     # fra bunden
            if not tapped:
                if len(leg) >= FVG_NR and hi >= leg[FVG_NR - 1][0]:
                    f = leg[FVG_NR - 1]
                    tapped = True; rhi, rhiT = hi, t
                    log(f"{t:%H:%M} rammer 5m FVG nr. {FVG_NR} {sgn*f[0]}-{sgn*f[1]} (benet {sgn*top} -> {sgn*low}, {len(leg)} FVG'er)")
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
            if cl < f[0]:
                entry = sgn * cl; sl = sgn * rhi; risk = abs(sl - entry)
                after = d[tc:we + pd.Timedelta(hours=4)]
                res.append(dict(dato=day, tid=f"{tc:%H:%M}", retning="SHORT" if short else "LONG", sweep=swept,
                                fvg_tf=f"{m}m", entry=entry, sl=sl, risk=risk, ben_top=sgn * top, ben_low=sgn * low,
                                **outcome(after, short, entry, sl, risk)))
                log(f"{tc:%H:%M} ENTRY {'SHORT' if short else 'LONG'} {entry} SL {sl} ({risk:.2f} p) - {m}m-candle lukkede gennem FVG")
                break
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
