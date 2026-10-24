"""
FVG-model paa BTC (Binance 1m klines), 24/10-26.

Entry og SL som fvg_model (sweep -> reaktion ind i 5m FVG nr. 2 -> inversion paa hoejeste TF 1-5m).
Hele doegnet (00:00-23:59 NY), flere trades per dag, max 2 timer fra sweep til entry.

Liq = Session Levels + Liq-indikatoren: Asia, London (i dag og i gaar), PDH/PDL og alle uroerte
4h highs/lows (10 dage). NY PRE er ikke med. Et niveau kan foerst sweepes, naar det er faerdigt.

TP: naermeste uroerte Asia / London / PDH-PDL mindst 1R vaek. Ingen -> intet trade.
Partials: 25% paa hver uroert 4h high/low mellem entry og TP (de naermeste, max 3). Resten paa TP.
SL bliver staaende. Max 24 timer i trade.

BTC: PDH/PDL og 4h-candles foelger UTC (som TradingView paa BTCUSDT).

Brug: python3 fvg_btc.py ud.csv BTCUSDT-1m-2026-09.zip [flere .zip/.csv ...]
"""
import sys, zipfile
import pandas as pd
import fvg_model as f

TZ = f.TZ
MIN_TP_R = 1.0
PART = 0.25
MAX_PART = 3
H4_DAYS = 10
CLOSE = "16:59"


def load_binance(paths):
    out = []
    for p in paths:
        if p.endswith(".csv") and open(p).readline().startswith("time,"):      # TradingView-eksport
            x = pd.read_csv(p)
            x.index = pd.DatetimeIndex(pd.to_datetime(x.time, utc=True)).tz_convert(TZ)
            out.append(x[["open", "high", "low", "close"]])
            continue
        if p.endswith(".zip"):
            z = zipfile.ZipFile(p)
            fh = z.open(z.namelist()[0])
        else:
            fh = open(p, "rb")
        d = pd.read_csv(fh, header=None)
        if not str(d.iloc[0, 0]).isdigit():          # header-linje
            d = d.iloc[1:]
        d = d.iloc[:, :5].astype(float)
        d.columns = ["t", "open", "high", "low", "close"]
        unit = "us" if d.t.max() > 1e14 else "ms"
        d.index = pd.DatetimeIndex(pd.to_datetime(d.t.astype("int64"), unit=unit, utc=True)).tz_convert(TZ)
        out.append(d[["open", "high", "low", "close"]])
    d = pd.concat(out).sort_index()
    return d[~d.index.duplicated()]


def h4_utc(x):
    """4h-candles paa UTC 00/04/08/12/16/20 (som TradingView paa BTC)."""
    h = x.tz_convert("UTC").resample("4h").agg({"high": "max", "low": "min"}).dropna()
    h.index = h.index.tz_convert(TZ)
    return h


def btc_levels(d, day):
    """Niveauer til sweep: navn -> (high, low, faerdig-tid)."""
    day = pd.Timestamp(day)
    out = {}
    for back, suf in ((0, ""), (1, " i gaar")):
        dd = day - pd.Timedelta(days=back)
        prev = dd - pd.Timedelta(days=1)
        for nm, (a, b) in (("Asia", ("20:00", "02:00")), ("London", ("02:00", "08:00"))):
            s0 = pd.Timestamp(f"{(prev if nm == 'Asia' else dd).date()} {a}").tz_localize(TZ)
            e = pd.Timestamp(f"{dd.date()} {b}").tz_localize(TZ)
            x = d[s0:e - pd.Timedelta(seconds=1)]
            if len(x):
                out[nm + suf] = (x.high.max(), x.low.min(), e)
    for k in (0, 1):                                  # UTC-dagen skifter midt paa NY-dagen
        u1 = (day + pd.Timedelta(days=k)).tz_localize("UTC")
        y = d[(u1 - pd.Timedelta(days=1)).tz_convert(TZ):u1.tz_convert(TZ) - pd.Timedelta(seconds=1)]
        if len(y):
            out["PDH/PDL" + ("" if k == 0 else " (ny dag)")] = (y.high.max(), y.low.min(), u1.tz_convert(TZ))
    s0 = day.tz_localize(TZ) - pd.Timedelta(days=H4_DAYS)
    e1 = day.tz_localize(TZ) + pd.Timedelta(days=1)
    h4 = h4_utc(d[s0:e1])
    for t, c in h4.iterrows():
        e = t + pd.Timedelta(hours=4)
        if e <= e1:
            out[f"4h {(t + pd.Timedelta(hours=6)):%d/%m %H:%M}"] = (c.high, c.low, e)
    return out


def tp_levels(d, day, s, entry, short):
    """Uroerte Asia / London / PDH-PDL paa den rigtige side af entry."""
    c = []
    for nm, (hi, lo, e) in btc_levels(d, day).items():
        if nm.startswith("4h") or e > s:
            continue
        v = lo if short else hi
        if (v >= entry) if short else (v <= entry):
            continue
        x = d[e:s - pd.Timedelta(seconds=1)]
        if len(x) and ((x.low.min() < v) if short else (x.high.max() > v)):
            continue
        c.append((v, nm.replace(" i gaar", " (i gaar)")))
    # session der koerer lige nu: dens high/low indtil nu (vises live i indikatoren)
    for nm, a, b, back in (("Asia", "20:00", "02:00", 1), ("Asia", "20:00", "02:00", 0), ("London", "02:00", "08:00", 0)):
        s0 = pd.Timestamp(f"{(s - pd.Timedelta(days=back)).date()} {a}").tz_localize(TZ)
        e = s0 + (pd.Timedelta(hours=6))
        if s0 <= s < e:
            x = d[s0:s - pd.Timedelta(seconds=1)]
            if len(x):
                v = x.low.min() if short else x.high.max()
                if (v < entry) if short else (v > entry):
                    c.append((v, nm + " (live)"))
    return c


def tp_func(d, day, tc, ref, short, entry, risk):
    c = [q for q in tp_levels(d, day, tc, entry, short) if abs(q[0] - entry) >= MIN_TP_R * risk]
    return min(c, key=lambda q: abs(q[0] - entry))[0] if c else None


def h4_levels(d, s, entry, tp, short):
    """Uroerte 4h highs (long) / lows (short) mellem entry og TP, naermeste foerst."""
    x = d[s - pd.Timedelta(days=H4_DAYS):s - pd.Timedelta(seconds=1)]
    h4 = h4_utc(x)
    r = []
    for t, c in h4.iterrows():
        e = t + pd.Timedelta(hours=4)
        if e > s:
            continue
        v = c.low if short else c.high
        if not ((tp < v < entry) if short else (entry < v < tp)):
            continue
        y = d[e:s - pd.Timedelta(seconds=1)]
        if len(y) and ((y.low.min() < v) if short else (y.high.max() > v)):
            continue
        r.append(v)
    r = sorted(set(r), key=lambda v: abs(v - entry))
    return r[:MAX_PART]


def dk(t):
    return (t + pd.Timedelta(hours=6)).strftime("%d/%m %H:%M")


def simulate(d, s, end, short, entry, sl, tp, parts):
    risk = abs(entry - sl)
    left = 1.0; R = 0.0; log = []
    todo = list(parts)
    for t, b in d[s:end].iterrows():
        if (b.high >= sl) if short else (b.low <= sl):
            R -= left; log.append(f"SL {dk(t)}"); left = 0; break
        while todo and ((b.low <= todo[0]) if short else (b.high >= todo[0])):
            v = todo.pop(0); R += PART * abs(v - entry) / risk; left -= PART
            log.append(f"25% {v} {dk(t)}")
        if (b.low <= tp) if short else (b.high >= tp):
            R += left * abs(tp - entry) / risk; log.append(f"TP {dk(t)}"); left = 0; break
    if left > 0:
        cl = d[s:end].close.iloc[-1]
        R += left * ((entry - cl) if short else (cl - entry)) / risk
        log.append(f"lukket {cl}")
    return R, " | ".join(log)


def run(d, days):
    f.levels = btc_levels
    f.WIN = ("00:00", "23:59"); f.LEG_FROM = "00:00"
    f.MULTI = True; f.MIN_RR = MIN_TP_R
    f.MAX_SWEEP_ENTRY = pd.Timedelta(hours=2)
    f.CONSUME = True                                 # et taget niveau kan ikke sweepes igen (2/9: 4h low taget 04:00)
    f.RECLAIM = True                                 # 5m close tilbage over/under liq efter sweepet
    f.TP_FUNC = tp_func
    f.EXIT_END = lambda day, tc: tc + pd.Timedelta(hours=24)
    f.PRE = pd.Timedelta(hours=6)                    # vinduet starter 18:00 NY dagen foer, saa sweeps over midnat ikke tabes
    rows = []
    for day in days:
        for r in f.run_day(d, day, log=lambda *a: None):
            short = r["retning"] == "SHORT"
            s = r["ts"]
            d0 = pd.Timestamp(day).tz_localize(TZ)
            if not (d0 <= s < d0 + pd.Timedelta(days=1)):   # hoerer til naboens doegn (overlap)
                continue
            entry, sl, risk, tp = r["entry"], r["sl"], r["risk"], r["tp_4h"]
            tpn = next(nm for v, nm in tp_levels(d, day, s, entry, short) if v == tp)
            parts = h4_levels(d, s, entry, tp, short)
            R, log = simulate(d, s, s + pd.Timedelta(hours=24), short, entry, sl, tp, parts)
            rows.append(dict(dato=day, ugedag=pd.Timestamp(day).day_name(),
                             sweep_dk=dk(r["sweep_ts"]), entry_dk=dk(s),
                             retning=r["retning"], sweep=r["sweep"], fvg_tf=r["fvg_tf"], entry=entry, sl=sl,
                             risk=round(risk, 2), tp=tp, tp_navn=tpn, tp_R=r["rr"],
                             partials=" / ".join(str(v) for v in parts), R=round(R, 2), forloeb=log))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out, paths = sys.argv[1], sys.argv[2:]
    d = load_binance(paths)
    days = [f"{x:%Y-%m-%d}" for x in pd.date_range(d.index[0].date() + pd.Timedelta(days=1), d.index[-1].date())]
    df = run(d, days)
    df.to_csv(out, index=False)
    t = df
    print(df.to_string(index=False))
    if len(t):
        print(f"\n{len(t)} trades, {t.R.sum():+.2f}R, win {(t.R > 0).mean():.0%}")
