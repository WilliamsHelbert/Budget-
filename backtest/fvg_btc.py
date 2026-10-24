"""
FVG-model paa BTC (Binance 1m klines), 24/10-26.

Entry og SL som fvg_model (sweep -> reaktion ind i 5m FVG nr. 2 -> inversion paa hoejeste TF 1-5m),
plus max 2 timer fra sweep til entry.

TP: naermeste uroerte session-liq (Asia, London, PDH/PDL) mindst 1R vaek. Ingen saadan -> intet trade.
Partials: 25% paa hver uroert 4h high/low mellem entry og TP (de naermeste, max 3).
Resten paa TP. SL bliver staaende. Lukkes 17:00 NY (23:00 dansk).

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


def tp_levels(d, day, s, entry, short):
    """Uroerte Asia/London/PDH-PDL (UTC-dag) paa den rigtige side af entry."""
    lv = {nm: v for nm, v in f.levels(d, day).items() if nm in ("Asia", "London")}
    u0 = s.tz_convert("UTC").normalize()
    y = d[(u0 - pd.Timedelta(days=1)).tz_convert(TZ):u0.tz_convert(TZ) - pd.Timedelta(seconds=1)]
    if len(y):
        lv["PDH/PDL"] = (y.high.max(), y.low.min(), u0.tz_convert(TZ))
    c = []
    for nm, (hi, lo, e) in lv.items():
        v = lo if short else hi
        if (v >= entry) if short else (v <= entry):
            continue
        x = d[e:s - pd.Timedelta(seconds=1)]
        if len(x) and ((x.low.min() < v) if short else (x.high.max() > v)):
            continue
        c.append((v, nm))
    return c


def h4_levels(d, s, entry, tp, short):
    """Uroerte 4h highs (long) / lows (short) mellem entry og TP, naermeste foerst."""
    x = d[s - pd.Timedelta(days=H4_DAYS):s - pd.Timedelta(seconds=1)]
    h4 = x.resample("4h", origin="epoch").agg({"high": "max", "low": "min"}).dropna()   # UTC 00/04/08...
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


def simulate(d, s, end, short, entry, sl, tp, parts):
    risk = abs(entry - sl)
    left = 1.0; R = 0.0; log = []
    todo = list(parts)
    for t, b in d[s:end].iterrows():
        if (b.high >= sl) if short else (b.low <= sl):
            R -= left; log.append(f"SL {t:%H:%M}"); left = 0; break
        while todo and ((b.low <= todo[0]) if short else (b.high >= todo[0])):
            v = todo.pop(0); R += PART * abs(v - entry) / risk; left -= PART
            log.append(f"25% {v} {t:%H:%M}")
        if (b.low <= tp) if short else (b.high >= tp):
            R += left * abs(tp - entry) / risk; log.append(f"TP {t:%H:%M}"); left = 0; break
    if left > 0:
        cl = d[s:end].close.iloc[-1]
        R += left * ((entry - cl) if short else (cl - entry)) / risk
        log.append(f"lukket {cl}")
    return R, " | ".join(log)


def run(d, days):
    f.MAX_SWEEP_ENTRY = pd.Timedelta(hours=2)
    rows = []
    for day in days:
        for r in f.run_day(d, day, log=lambda *a: None):
            short = r["retning"] == "SHORT"
            s = pd.Timestamp(f"{day} {r['tid']}").tz_localize(TZ)
            end = pd.Timestamp(f"{day} {CLOSE}").tz_localize(TZ)
            entry, sl, risk = r["entry"], r["sl"], r["risk"]
            c = [(v, nm) for v, nm in tp_levels(d, day, s, entry, short) if abs(v - entry) >= MIN_TP_R * risk]
            dk = (s + pd.Timedelta(hours=6)).strftime("%H:%M")
            base = dict(dato=day, ugedag=pd.Timestamp(day).day_name(), sweep_dk=(pd.Timestamp(f"{day} {r['sweep_tid']}") + pd.Timedelta(hours=6)).strftime("%H:%M"),
                        entry_dk=dk, retning=r["retning"], sweep=r["sweep"], fvg_tf=r["fvg_tf"],
                        entry=entry, sl=sl, risk=round(risk, 2))
            if not c:
                rows.append(dict(base, taget="nej", grund="ingen session-liq >= 1R"))
                continue
            tp, tpn = min(c, key=lambda q: abs(q[0] - entry))
            parts = h4_levels(d, s, entry, tp, short)
            R, log = simulate(d, s, end, short, entry, sl, tp, parts)
            rows.append(dict(base, taget="ja", tp=tp, tp_navn=tpn, tp_R=round(abs(tp - entry) / risk, 2),
                             partials=" / ".join(str(v) for v in parts), R=round(R, 2), forloeb=log))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out, paths = sys.argv[1], sys.argv[2:]
    d = load_binance(paths)
    days = [f"{x:%Y-%m-%d}" for x in pd.date_range(d.index[0].date() + pd.Timedelta(days=1), d.index[-1].date())]
    df = run(d, days)
    df.to_csv(out, index=False)
    t = df[df.taget == "ja"] if len(df) else df
    print(df.to_string(index=False))
    if len(t):
        print(f"\n{len(t)} trades, {t.R.sum():+.2f}R, win {(t.R > 0).mean():.0%}")
