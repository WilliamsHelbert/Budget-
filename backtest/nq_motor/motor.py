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
PARTIAL = True       # 25% ud paa high/low af en 4h-candle der lukker mens tradet er aabent
OLD_SESS = True      # intet nyt liq -> naermeste gamle session, der ikke er taget, uanset hvor langt tilbage
EXIT = "16:55"       # alt lukkes 16:55 NY = 22:55 DK

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


def configure():
    f.levels = levels
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
    return out


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


def resultat(r):
    short = r["retning"] == "SHORT"; risk = r["risk"]; entry = r["entry"]
    # 1) naermeste uberoerte Asia/London/PDH/PDL (i dag og i gaar) mindst 1R vaek
    c = [q for q in tp_levels(d, r["dag"], r["ts"], entry, short) if abs(q[0] - entry) >= risk]
    tp, tpn = min(c, key=lambda q: abs(q[0] - entry)) if c else (None, "")
    # 2) gamle sessions, 3) 4h, 4) 4R
    if not tp and OLD_SESS:
        o = old_sess(r["ts"], entry, short, risk)
        if o:
            tp, tpn = o
    if not tp:
        tp, tpn = h4(r["ts"], entry, short, risk)
    if not tp:
        tp, tpn = entry + (-4 if short else 4) * risk, "4R (intet liq)"
    end = pd.Timestamp(f"{r['dag']} {EXIT}").tz_localize(TZ, nonexistent="shift_forward", ambiguous=False)
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
    R, how, tx, part = None, "", None, None
    for ts, b in d[r["ts"]:end].iterrows():
        if sess and ts >= sess[0][0]:
            e, nm, a = sess.pop(0); x = d[a:e - pd.Timedelta(seconds=1)]
            v = x.low.min() if short else x.high.max()
            if ((v < entry) and v > tp) if short else ((v > entry) and v < tp):
                tp, tpn = v, f"{nm} (lavet i tradet)"
        if (b.high >= r["sl"]) if short else (b.low <= r["sl"]):
            R, how, tx = -1.0, "SL", ts; break
        if (b.low <= tp) if short else (b.high >= tp):
            R, how, tx = abs(tp - entry) / risk, "TP", ts; break
        if PARTIAL and part is None:
            for e, v in c4:
                if ts >= e and ((v < entry) if short else (v > entry)) and ((b.low <= v) if short else (b.high >= v)):
                    part = (v, ts, abs(v - entry) / risk); break
    if R is None:
        x = d[r["ts"]:end]; cl = x.close.iloc[-1]; tx = x.index[-1]
        R = ((entry - cl) if short else (cl - entry)) / risk; how = "Lukket 22:55"
    r["R_uden"] = round(R, 2)
    if part:
        R = 0.25 * part[2] + 0.75 * R
        r["partial"] = (part[0], f"{part[1] + DK:%H:%M}", round(part[2], 2))
    else:
        r["partial"] = None
    r.update(tp=tp, tp_navn=tpn.replace("i gaar", "i går").replace("PDH/PDL", "PDL" if short else "PDH"),
             R=round(R, 2), udfald=how, exit_dk=f"{tx + DK:%H:%M}", exit_ts=tx)
    return r


def _dag(day):
    return [resultat(r) for r in setups(day)]


def koer(fra, til, procs=None):
    from multiprocessing import Pool
    days = [f"{x.date()}" for x in pd.bdate_range(fra, til)]
    _sessions()                      # en gang foer fork
    with Pool(procs or os.cpu_count()) as p:
        res = p.map(_dag, days)
    return sorted([r for x in res for r in x], key=lambda r: r["ts"])


def tabel(rows):
    return pd.DataFrame([dict(
        dato=f"{r['ts'] + DK:%Y-%m-%d}", entry_dk=f"{r['ts'] + DK:%H:%M}", sweep_dk=f"{r['sweep_ts'] + DK:%H:%M}", retning=r["retning"],
        sweep=r["sweep"].replace("i gaar", "i går"), tf=r["fvg_tf"], entry=r["entry"], sl=r["sl"], risk=round(r["risk"], 2), tp=r["tp"], tp_navn=r["tp_navn"],
        udfald=r["udfald"], exit_dk=r["exit_dk"], partial_25=(r["partial"][0] if r["partial"] else None), R_uden_partial=r["R_uden"], R=r["R"]) for r in rows])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NQ FVG-motoren")
    ap.add_argument("fra"); ap.add_argument("til")
    ap.add_argument("--ud", default=os.path.join(os.getcwd(), "nq_motor_ud"))
    ap.add_argument("--titel", default=None)
    ap.add_argument("--data", nargs="+", default=DATA, help="parquet-filer (time, open, high, low, close; 15s); senere filer vinder")
    ap.add_argument("--procs", type=int, default=None)
    ap.add_argument("--ingen-rapport", action="store_true")
    ap.add_argument("--tf", type=int, nargs="+", default=[5, 4, 3, 2, 1], help="timeframes (min) der maa give entry, fx --tf 5")
    a = ap.parse_args()
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
        open(os.path.join(a.ud, "rapport.html"), "w").write(rapport.html_rapport(rows, a.titel or f"NQ {a.fra} – {a.til}", a.fra, a.til))
        print("rapport:", os.path.join(a.ud, "rapport.html"))
