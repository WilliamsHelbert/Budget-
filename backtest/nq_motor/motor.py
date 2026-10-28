"""NQ FVG-motoren (sweep -> reaktion -> inversion), som William handler den.

Koer:  python3 backtest/nq_motor/motor.py 2026-10-01 2026-10-19
       python3 backtest/nq_motor/motor.py 2026-10-01 2026-10-19 --ud /mnt/project-files/backtest/nq_motor --titel "NQ oktober 2026"

Giver <ud>/trades.csv og <ud>/rapport.html. Alle regler staar i README.md ved siden af.
Tider i data og i koden er New York-tid. DK = NY + 6 timer.
"""
import argparse, os, sys
import numpy as np, pandas as pd

HER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HER))
import fvg_model as f

TZ = f.TZ
DK = pd.Timedelta(hours=6)
DATA = ["/mnt/project-files/data/NQ_samlet_15s.parquet",                 # 2022-09 -> 2026-10-19 (hul i sep/okt 2026)
        "/mnt/project-files/data/NQ_2026-09-01_2026-10-09_15s.parquet"]  # lapper hullet; senere filer vinder

# ---------------------------------------------------------------- regler (setup)
CFG = dict(
    SESS={"Asia": ("20:00", "02:00"), "London": ("02:00", "08:00")},
    EXTRA={"PDH", "4h alle"},          # liq: Asia, London, PDH/PDL, 4h-candles en uge tilbage + gaarsdagens sessions
    WIN=("00:00", "16:59"), LEG_FROM="00:00", PRE=pd.Timedelta(hours=4),
    MULTI=True, MIN_RR=0.0,
    LEG_MID=True, OLDEST=True, FVG_FALLBACK=False, SWEEP_GAPS=True, FVG_UNFILLED=False, INSIDE=False,
    RECLAIM=True, GAP_RECENT=True, MAX_SWEEP_RESET=pd.Timedelta(hours=2), GAP_NOINV=True, CONSUME=True,
    KEEP_LEG=True, KEEP_LEG_EXIT=False, OPP_SESS=True, INV_MIN=1.0,
    OWN_LEG=False, FVG_NEAR=None, NEW_EXT=False, RESET_FROM_EXT=False, MAX_SWEEP_ENTRY=None,
)
# ---------------------------------------------------------------- regler (resultat)
ENTRY_GP = None      # fx 0.705: limit-entry 0,705 af vejen fra signal-entry tilbage mod SL (None = entry paa signalet)
PARTIAL = False      # True: 25% ud paa high/low af en 4h-candle der lukker mens tradet er aabent
H4_TP = False        # True: 4h-niveauer som TP, hvis der ingen session-liq er
OLD_SESS = True      # intet nyt liq -> naermeste gamle session, der ikke er taget, uanset hvor langt tilbage
# ---------------------------------------------------------------- standard fra 28/10-26 (mindst drawdown over 2022-2026)
KUN_1_LIQ = True     # kun sweeps af eet liq-niveau (ikke fx "Asia + 4h")
FOERSTE_TRADE = True # kun dagens foerste trade (DK-dag)
FAST_TP = True       # TP saettes ved entry og flyttes ikke af en session lavet i tradet
TRAIL = (2.0, 1.0)   # ved +2R flyttes SL til +1R (None = slaaet fra)
SL_CUT = (30, 40, 50, 60)   # SL-varianter i CSV: SL skaaret med saa mange procent
EXIT = "16:55"       # alt lukkes 16:55 NY = 22:55 DK
TREND = None         # N: kun long naar NQ er steget over de seneste N afsluttede CME-dage, kun short naar den er faldet
RANGE = None         # (dage, lav, hoej): ingen short under `lav` og ingen long over `hoej` i rangen af de seneste `dage` CME-dage, fx (10, 0.25, 0.75)
RR_GR = None         # (min, max): kun trades hvor RR til start-TP ligger i intervallet; ellers springes setuppet over, og dagens naeste setup kan tages

d = None             # 15s-data, saettes af load()
_orig_levels = f.levels


def load(paths=DATA):
    out = None
    for p in paths:
        x = f.load(p)
        if out is None:
            out = x
        else:   # senere fil erstatter perioden den daekker
            out = pd.concat([out[:x.index[0] - pd.Timedelta(seconds=1)], x, out[x.index[-1] + pd.Timedelta(seconds=1):]])
    out = out.sort_index()
    return out[~out.index.duplicated()]


def prevday(day):
    p = pd.Timestamp(day) - pd.Timedelta(days=1)
    while p.weekday() >= 5:
        p -= pd.Timedelta(days=1)
    return f"{p.date()}"


def levels(d, day):
    out = _orig_levels(d, day)
    for k, v in _orig_levels(d, prevday(day)).items():
        if not k.startswith("4h") and k != "PDH/PDL":
            out[k + " i gaar"] = v
    return out


def tp_levels(d, day, s, entry, short, live=False):
    c = []
    for nm, (hi, lo, e) in levels(d, day).items():
        if nm.startswith("4h") or e > s:
            continue
        v = lo if short else hi
        if (v >= entry) if short else (v <= entry):
            continue
        x = d[e:s - pd.Timedelta(seconds=1)]
        if len(x) and ((x.low.min() < v) if short else (x.high.max() > v)):
            continue
        c.append((v, nm))
    if live:                                    # session der koerer nu (kun til modellens interne exit)
        for nm, (a, b) in f.SESS.items():
            for back in (0, 1):
                s0 = pd.Timestamp(f"{(s - pd.Timedelta(days=back)).date()} {a}").tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
                if s0 <= s < s0 + pd.Timedelta(hours=6):
                    x = d[s0:s - pd.Timedelta(seconds=1)]
                    v = x.low.min() if short else x.high.max()
                    if (v < entry) if short else (v > entry):
                        c.append((v, nm + " (live)"))
    return c


def _tp_intern(d, day, tc, ref, short, entry, risk):
    # TP modellen bruger internt til at vide, hvornaar et trade er ude, og et nyt setup kan starte
    c = tp_levels(d, day, tc, entry, short, live=True)
    return min(c, key=lambda q: abs(q[0] - entry))[0] if c else None


_rng = None


def _ranges():
    """High/low af de seneste RANGE[0] afsluttede CME-dage (18:00-17:00 NY) foer hver CME-dag."""
    global _rng
    if _rng is not None or not (RANGE or TREND):
        return
    x = d.resample("1min").agg({"high": "max", "low": "min"}).dropna()
    cme = (x.index + pd.Timedelta(hours=6)).normalize().tz_localize(None)
    dg = x.groupby(cme).agg({"high": "max", "low": "min"})
    dg = dg[dg.index.weekday < 5]
    n = RANGE[0] if RANGE else 10
    _rng = pd.DataFrame({"hi": dg.high.rolling(n).max().shift(1), "lo": dg.low.rolling(n).min().shift(1)})
    if TREND:
        cl = d.close.groupby((d.index + pd.Timedelta(hours=6)).normalize().tz_localize(None)).last()
        cl = cl[cl.index.weekday < 5]
        _rng["trend"] = np.sign(cl - cl.shift(TREND)).shift(1)


def range_pos(tc, entry):
    k = (tc + pd.Timedelta(hours=6)).tz_localize(None).normalize()
    if k not in _rng.index:
        return None
    hi, lo = _rng.hi[k], _rng.lo[k]
    return (entry - lo) / (hi - lo)


def _entry_ok(day, tc, short, entry, sweep="", risk=None):
    if KUN_1_LIQ and " + " in sweep:
        return False
    if RR_GR and risk:
        rr = abs(start_tp(day, tc, entry, short, risk)[0] - entry) / risk
        if not (RR_GR[0] <= rr <= RR_GR[1]):
            return False
    k = (tc + pd.Timedelta(hours=6)).tz_localize(None).normalize()
    if TREND and k in _rng.index and not np.isnan(_rng.trend[k]):
        if _rng.trend[k] == (1 if short else -1):
            return False
    p = range_pos(tc, entry) if RANGE else None
    if p is None or np.isnan(p):
        return True
    return p >= RANGE[1] if short else p <= RANGE[2]


def configure():
    f.levels = levels
    f.ENTRY_OK = _entry_ok if (RANGE or TREND or KUN_1_LIQ or RR_GR) else None
    f.TP_FUNC = _tp_intern
    f.EXIT_END = lambda day, tc: pd.Timestamp(f"{day} 16:59:45").tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
    for k, v in CFG.items():
        setattr(f, k, v)


def setups(day):
    """Alle entries for en dag (dagen = 00:00-23:00 DK)."""
    configure()
    out = []
    d0 = pd.Timestamp(day).tz_localize(TZ, nonexistent="shift_forward", ambiguous=False) - DK
    for r in f.run_day(d, day, log=lambda *a: None):
        if not (d0 <= r["ts"] < d0 + pd.Timedelta(hours=23)):
            continue
        short = r["retning"] == "SHORT"
        lv = levels(d, day)
        vals = [(lv[n][1] if short else lv[n][0]) for n in r["sweep"].split(" + ") if n in lv]
        out.append(dict(r, dag=day, entry_dk=f"{r['ts'] + DK:%d/%m %H:%M}", lvl=(min(vals) if short else max(vals)) if vals else r["ben_low"]))
    out.sort(key=lambda r: r["ts"])
    return out[:1] if FOERSTE_TRADE else out


# ---------------------------------------------------------------- TP og udfald
_m1 = None; _ss = None


def _sessions():
    global _m1, _ss
    if _ss is not None:
        return
    _m1 = d.resample("1min").agg({"high": "max", "low": "min"}).dropna()
    _ss = []
    for dd in pd.date_range(_m1.index[0].date(), _m1.index[-1].date()):
        for nm, a, b in (("Asia", dd - pd.Timedelta(hours=4), dd + pd.Timedelta(hours=2)), ("London", dd + pd.Timedelta(hours=2), dd + pd.Timedelta(hours=8))):
            a = a.tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
            b = b.tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
            x = _m1[a:b - pd.Timedelta(seconds=1)]
            if len(x):
                _ss.append((b, f"{nm} {dd:%d/%m/%y}", x.high.max(), x.low.min()))


def old_sess(s, entry, short, risk):
    """Naermeste gamle session high (long) / low (short), der ikke er taget siden, mindst 1R vaek."""
    _sessions()
    y = _m1[:s - pd.Timedelta(seconds=1)]
    v_ = y.low.values if short else -y.high.values
    suf = np.minimum.accumulate(v_[::-1])[::-1]          # laveste low (hoejeste high) fra i og frem til s
    best = None
    for e, nm, hi, lo in _ss:
        if e > s:
            break
        v = lo if short else hi
        if ((entry - v) if short else (v - entry)) < risk:
            continue
        i = y.index.searchsorted(e)
        if i < len(suf) and suf[i] < (v if short else -v):
            continue
        if best is None or abs(v - entry) < abs(best[0] - entry):
            best = (v, nm)
    return best


def h4(s, entry, short, risk):
    h = d[s - pd.Timedelta(days=10):s].resample("4h", offset="2h").agg({"high": "max", "low": "min"}).dropna()
    c = []
    for t, q in h.iterrows():
        e = t + pd.Timedelta(hours=4)
        if e > s:
            continue
        v = q.low if short else q.high
        if abs(v - entry) < risk or ((v >= entry) if short else (v <= entry)):
            continue
        y = d[e:s - pd.Timedelta(seconds=1)]
        if len(y) and ((y.low.min() < v) if short else (y.high.max() > v)):
            continue
        c.append((v, f"4h {(t + DK):%d/%m %H:%M}"))
    return min(c, key=lambda q: abs(q[0] - entry)) if c else (None, "")


def h4_n(s, entry, short, n):
    """n'te naermeste uberoerte 4h-liq (high for long, low for short) i profit, en uge tilbage."""
    h = d[s - pd.Timedelta(days=10):s].resample("4h", offset="2h").agg({"high": "max", "low": "min"}).dropna()
    c = set()
    for t, q in h.iterrows():
        e = t + pd.Timedelta(hours=4)
        if e > s:
            continue
        v = q.low if short else q.high
        if (v >= entry) if short else (v <= entry):
            continue
        y = d[e:s - pd.Timedelta(seconds=1)]
        if len(y) and ((y.low.min() < v) if short else (y.high.max() > v)):
            continue
        c.add(v)
    c = sorted(c, key=lambda v: abs(v - entry))
    return (c[n - 1], f"{n}. 4h") if len(c) >= n else None


def start_tp(day, ts, entry, short, risk):
    # 1) naermeste uberoerte Asia/London/PDH/PDL (i dag og i gaar) mindst 1R vaek
    c = [q for q in tp_levels(d, day, ts, entry, short) if abs(q[0] - entry) >= risk]
    tp, tpn = min(c, key=lambda q: abs(q[0] - entry)) if c else (None, "")
    # 2) gamle sessions, 3) 4h, 4) 4R
    if not tp and OLD_SESS:
        o = old_sess(ts, entry, short, risk)
        if o:
            tp, tpn = o
    if not tp and H4_TP:
        tp, tpn = h4(ts, entry, short, risk)
    if not tp:
        tp, tpn = entry + (-4 if short else 4) * risk, "4R (intet liq)"
    return tp, tpn


def resultat(r):
    short = r["retning"] == "SHORT"; risk = r["risk"]; entry = r["entry"]
    tp, tpn = start_tp(r["dag"], r["ts"], entry, short, risk)
    end = pd.Timestamp(f"{r['dag']} {EXIT}").tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
    r["signal_ts"], r["signal_entry"] = r["ts"], entry
    if ENTRY_GP:
        # limit i golden pocket; naas TP foer limit'en bliver fyldt, er der intet trade
        lim = entry + ENTRY_GP * (r["sl"] - entry)
        x = d[r["ts"]:end]
        hit = (x.high >= lim) if short else (x.low <= lim)
        if not hit.any():
            return None
        tf = hit.idxmax(); tph = (x.low <= tp) if short else (x.high >= tp)
        if tph.any() and tph.idxmax() < tf:
            return None
        entry = lim; risk = abs(r["sl"] - lim)
        r.update(ts=tf, entry=entry, risk=risk)
    # sessions der bliver faerdige under tradet: deres low/high bliver TP, hvis den er i profit og naermere
    sess = []
    for back in (1, 0):
        dd = (r["ts"] - pd.Timedelta(days=back)).date()
        for nm, a, b in (("Asia", f"{dd - pd.Timedelta(days=1)} 20:00", f"{dd} 02:00"), ("London", f"{dd} 02:00", f"{dd} 08:00")):
            a = pd.Timestamp(a).tz_localize(TZ, nonexistent="shift_forward", ambiguous=False); b = pd.Timestamp(b).tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
            if r["ts"] < b <= end:
                sess.append((b, nm, a))
    c4 = d[r["ts"] - pd.Timedelta(hours=4):end].resample("4h", offset="2h").agg({"high": "max", "low": "min"}).dropna()
    c4 = [(t + pd.Timedelta(hours=4), q.low if short else q.high) for t, q in c4.iterrows() if r["ts"] < t + pd.Timedelta(hours=4) <= end]
    r["tp_start"] = tp                          # TP ved entry (foer en session lavet i tradet kan flytte den)

    def sim(tp, tpn, partial, sl=None, trail=TRAIL):
        sl = r["sl"] if sl is None else sl; rk = abs(sl - entry)
        ss = list(sess); R, how, tx, part = None, "", None, None
        for ts, b in d[r["ts"]:end].iterrows():
            while ss and ts >= ss[0][0] and not FAST_TP:
                e, nm, a = ss.pop(0)
                if e <= r["ts"]:
                    continue
                x = d[a:e - pd.Timedelta(seconds=1)]
                v = x.low.min() if short else x.high.max()
                if ((v < entry) and v > tp) if short else ((v > entry) and v < tp):
                    tp, tpn = v, f"{nm} (lavet i tradet)"
            if (b.high >= sl) if short else (b.low <= sl):
                R = ((entry - sl) if short else (sl - entry)) / rk
                R, how, tx = R, ("SL" if R < 0 else f"SL +{R:.0f}R"), ts; break
            if (b.low <= tp) if short else (b.high >= tp):
                R, how, tx = abs(tp - entry) / rk, "TP", ts; break
            if trail and abs(sl - entry) == rk and ((entry - b.low) if short else (b.high - entry)) >= trail[0] * rk:
                sl = entry + (-1 if short else 1) * trail[1] * rk
            if partial and part is None:
                for e, v in c4:
                    if ts >= e and ((v < entry) if short else (v > entry)) and ((b.low <= v) if short else (b.high >= v)):
                        part = (v, ts, abs(v - entry) / rk); break
        if R is None:
            x = d[r["ts"]:end]; cl = x.close.iloc[-1]; tx = x.index[-1]
            R = ((entry - cl) if short else (cl - entry)) / rk; how = "Lukket 22:55"
        return R, how, tx, tp, tpn, part

    R, how, tx, tp, tpn, part = sim(tp, tpn, PARTIAL)
    # sammenligning: med/uden 25% partial, og TP = naermeste af session-TP og 3. uberoerte 4h-liq
    alt = lambda R_, p_: round(0.25 * p_[2] + 0.75 * R_ if p_ else R_, 2)
    q = sim(r["tp_start"], tpn, not PARTIAL); r["R_alt_partial"] = alt(q[0], q[5]) if not PARTIAL else round(q[0], 2)
    h3 = h4_n(r["ts"], entry, short, 3)
    tp3 = h3[0] if h3 and abs(h3[0] - entry) < abs(r["tp_start"] - entry) else r["tp_start"]
    r["tp_4h3"] = tp3
    q = sim(tp3, tpn, False); r["R_4h3"] = round(q[0], 2)
    q = sim(tp3, tpn, True); r["R_4h3_partial"] = alt(q[0], q[5])
    # SL skaaret med p: samme entry og start-TP, SL p naermere entry
    for pc in SL_CUT:
        q = sim(r["tp_start"], tpn, False, entry + (1 - pc / 100) * (r["sl"] - entry)); r[f"R_sl{pc}"] = round(q[0], 2)
    r["R_uden"] = round(R, 2)
    if part:
        R = 0.25 * part[2] + 0.75 * R
        r["partial"] = (part[0], f"{part[1] + DK:%H:%M}", round(part[2], 2))
    else:
        r["partial"] = None
    # "fuld TP": hold til start-TP eller SL, ingen ny TP undervejs og ingen tidslukning
    x = d[r["ts"]:]; tp0 = r["tp_start"]
    hs = (x.high >= r["sl"]) if short else (x.low <= r["sl"])
    ht = (x.low <= tp0) if short else (x.high >= tp0)
    ts_, tt_ = (hs.idxmax() if hs.any() else None), (ht.idxmax() if ht.any() else None)
    if tt_ is not None and (ts_ is None or tt_ < ts_):
        r["R_fuld"] = round(abs(tp0 - entry) / risk, 2)
    elif ts_ is not None:
        r["R_fuld"] = -1.0
    else:
        r["R_fuld"] = round(((entry - x.close.iloc[-1]) if short else (x.close.iloc[-1] - entry)) / risk, 2)
    r.update(tp=tp, tp_navn=tpn.replace("i gaar", "i går").replace("PDH/PDL", "PDL" if short else "PDH"),
             R=round(R, 2), udfald=how, exit_dk=f"{tx + DK:%H:%M}", exit_ts=tx)
    return r


def _dag(day):
    return [x for x in (resultat(r) for r in setups(day)) if x is not None]


def koer(fra, til, procs=None):
    from multiprocessing import Pool
    days = [f"{x.date()}" for x in pd.bdate_range(fra, til)]
    _sessions()                      # en gang foer fork
    _ranges()
    with Pool(procs or os.cpu_count()) as p:
        res = p.map(_dag, days)
    return sorted([r for x in res for r in x], key=lambda r: r["ts"])


def tabel(rows):
    return pd.DataFrame([dict(
        dato=f"{r['ts'] + DK:%Y-%m-%d}", signal_dk=f"{r['signal_ts'] + DK:%H:%M}", signal_entry=r["signal_entry"], entry_dk=f"{r['ts'] + DK:%H:%M}", sweep_dk=f"{r['sweep_ts'] + DK:%H:%M}", retning=r["retning"],
        sweep=r["sweep"].replace("i gaar", "i går"), tf=r["fvg_tf"], entry=r["entry"], sl=r["sl"], risk=round(r["risk"], 2), tp=r["tp"], tp_navn=r["tp_navn"], tp_start=r["tp_start"], rr=round(abs(r["tp_start"] - r["entry"]) / r["risk"], 2),
        udfald=r["udfald"], exit_dk=r["exit_dk"], partial_25=(r["partial"][0] if r["partial"] else None), R_uden_partial=r["R_uden"], R=r["R"], R_fuld_tp=r["R_fuld"],
        R_partial=r["R_alt_partial"], tp_4h3=r["tp_4h3"], R_4h3=r["R_4h3"], R_4h3_partial=r["R_4h3_partial"], **{f"R_sl{pc}": r[f"R_sl{pc}"] for pc in SL_CUT}) for r in rows])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NQ FVG-motoren")
    ap.add_argument("fra"); ap.add_argument("til")
    ap.add_argument("--ud", default=os.path.join(os.getcwd(), "nq_motor_ud"))
    ap.add_argument("--titel", default=None)
    ap.add_argument("--data", nargs="+", default=DATA, help="parquet-filer (time, open, high, low, close; 15s); senere filer vinder")
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--ingen-rapport", action="store_true")
    ap.add_argument("--charts", type=int, default=None, help="vis charts pr. trade op til saa mange trades (standard 150)")
    ap.add_argument("--tf", type=int, nargs="+", default=[5, 4, 3, 2, 1], help="timeframes (min) der maa give entry, fx --tf 5")
    ap.add_argument("--range", type=float, nargs=3, metavar=("DAGE", "LAV", "HOEJ"), default=None,
                    help="ingen short under LAV og ingen long over HOEJ i rangen af de seneste DAGE dage, fx --range 10 0.25 0.75")
    ap.add_argument("--gp", type=float, default=ENTRY_GP, help="limit-entry i GP (0 = entry paa signalet)")
    ap.add_argument("--partial", action="store_true", help="25%% ud paa 4h high/low")
    ap.add_argument("--h4tp", action="store_true", help="4h-niveauer som TP, hvis der ingen session-liq er")
    ap.add_argument("--nyeste", action="store_true", help="entry paa inversion af det NYESTE gap i reaktionen (foerste inversion), ikke det aeldste")
    ap.add_argument("--alle-liq", action="store_true", help="tillad sweeps af flere liq paa een gang")
    ap.add_argument("--alle-trades", action="store_true", help="flere trades om dagen (ikke kun den foerste)")
    ap.add_argument("--flyt-tp", action="store_true", help="en session lavet i tradet bliver ny TP, hvis den er naermere")
    ap.add_argument("--ingen-trail", action="store_true", help="ingen SL-flyt ved +2R")
    ap.add_argument("--trend", type=int, default=None, metavar="DAGE",
                    help="kun long naar NQ er steget over de seneste DAGE dage, kun short naar den er faldet, fx --trend 10")
    ap.add_argument("--rr", type=float, nargs=2, metavar=("MIN", "MAX"), default=None,
                    help="kun trades med RR til start-TP mellem MIN og MAX, fx --rr 1.5 10")
    a = ap.parse_args()
    RR_GR = tuple(a.rr) if a.rr else None
    TREND = a.trend
    KUN_1_LIQ = not a.alle_liq; FOERSTE_TRADE = not a.alle_trades; FAST_TP = not a.flyt_tp
    if a.ingen_trail:
        TRAIL = None
    if a.nyeste:
        CFG["OLDEST"] = False
    ENTRY_GP = a.gp or None; PARTIAL = a.partial; H4_TP = a.h4tp
    RANGE = (int(a.range[0]), a.range[1], a.range[2]) if a.range else None
    CFG["TFS"] = sorted(set(a.tf) | {5}, reverse=True)   # 5m bruges altid til ben og sweep
    d = load(a.data)
    print(f"data {d.index[0]:%Y-%m-%d} -> {d.index[-1]:%Y-%m-%d %H:%M} NY, {len(d):,} bars")
    rows = koer(a.fra, a.til, a.procs)
    os.makedirs(a.ud, exist_ok=True)
    df = tabel(rows)
    df.to_csv(os.path.join(a.ud, "trades.csv"), index=False)
    print(df.to_string(index=False))
    if len(df):
        print(f"{len(df)} trades  {df.R.sum():+.2f}R  win {(df.R > 0).mean():.0%}")
    if not a.ingen_rapport:
        import rapport
        rapport.d = d
        rapport.REGLER = dict(kun1=KUN_1_LIQ, foerste=FOERSTE_TRADE, fast_tp=FAST_TP, trail=TRAIL)
        if a.charts:
            rapport.MAX_CHARTS = a.charts
        open(os.path.join(a.ud, "rapport.html"), "w").write(rapport.html_rapport(rows, a.titel or f"NQ {a.fra} – {a.til}", a.fra, a.til, gp=ENTRY_GP, partial=PARTIAL, h4=H4_TP))
        print("rapport:", os.path.join(a.ud, "rapport.html"))
