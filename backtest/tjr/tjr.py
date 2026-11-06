"""TJR-modellen, 4-step vejen, paa NQ 15s-data.

Step 1 (5m-liq): en 1m-candle handler under et uberoert liq-low (long) / over et liq-high (short).
    Liq = dagens Asia (20:00-02:00), London (02:00-08:00) og NY PRE (08:00-09:30) high/low,
    plus 5m swing highs/lows inde i NY PRE, som ogsaa er high/low i et 15m swing.
Step 2 (5m): en 5m-candle lukker over et 5m swing high (long), der er dannet efter sweepet.
Step 3 (1m): enten lukker en 1m-candle under et bullish 1m FVG (inversion), eller under
    det seneste 1m swing low (BOS mod tradet). Det der sker foerst.
Step 4 (1m): en 1m-candle lukker over det seneste 1m swing high -> market entry paa close.
SL: naermeste 1m swing low under entry (long). TP: naermeste uberoerte NY PRE / London /
    Asia high eller 4h high. Tradet er kun gyldigt, hvis TP er mindst 0,9R vaek.
Entry kun 09:30-12:00 NY. Setuppet doer ikke; man venter til alle steps er gennemfoert.

Swing = high/low hoejere/lavere end candlen foer og efter. Det er foerst kendt, naar candlen
efter er lukket (ingen lookahead). Short er spejlvendt.
"""
import argparse, json, os
import pandas as pd

NY = "America/New_York"
DATA = "/mnt/project-files/data/NQ_samlet_15s.parquet"
MIN_RR = 0.9
ENTRY_FRA, ENTRY_TIL = "09:30", "12:00"
STEP_FRA = "08:00"          # step 1-3 maa ske fra NY PRE start, entry kun i entry-vinduet
EXIT_SENEST = "16:59"
H4_DAGE = 10

_raw = None


def load(fra, til):
    global _raw
    d = pd.read_parquet(DATA)
    d["time"] = pd.to_datetime(d["time"], utc=True)
    d = d.set_index("time").sort_index()
    d = d[(d.index >= pd.Timestamp(fra, tz=NY) - pd.Timedelta(days=H4_DAGE + 4)) &
          (d.index <= pd.Timestamp(til, tz=NY) + pd.Timedelta(days=1))]
    d.index = d.index.tz_convert(NY)
    _raw = d
    return d


def bars(d, minutes):
    """OHLC med label = start, i NY-tid. Index er candlens starttid."""
    return d.resample(f"{minutes}min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def swings(b):
    """Liste af (pivot_start, confirm_close_time, pris, 'H'/'L'). Kraever at naboerne er i rad (ingen hul)."""
    out = []
    idx = b.index; h = b.high.values; l = b.low.values
    for i in range(1, len(b) - 1):
        conf = idx[i + 1] + _len(b)          # bekraeftet naar candlen efter er lukket
        if h[i] > h[i - 1] and h[i] > h[i + 1]:
            out.append((idx[i], conf, h[i], "H"))
        if l[i] < l[i - 1] and l[i] < l[i + 1]:
            out.append((idx[i], conf, l[i], "L"))
    return out


def _len(b):
    return b.attrs["len"]


def mk(d, minutes):
    b = bars(d, minutes)
    b.attrs["len"] = pd.Timedelta(minutes=minutes)
    return b


def session_levels(day, d):
    """Dagens Asia/London/NY PRE high+low med sluttid."""
    dd = pd.Timestamp(day.date(), tz=NY)
    prev = dd - pd.Timedelta(days=1)
    if dd.weekday() == 0:                      # mandag: Asia starter soendag aften
        prev = dd - pd.Timedelta(days=1)
    sess = {"Asia": (prev + pd.Timedelta(hours=20), dd + pd.Timedelta(hours=2)),
            "London": (dd + pd.Timedelta(hours=2), dd + pd.Timedelta(hours=8)),
            "NY PRE": (dd + pd.Timedelta(hours=8), dd + pd.Timedelta(hours=9, minutes=30))}
    out = []
    for nm, (a, b) in sess.items():
        x = d[(d.index >= a) & (d.index < b)]
        if not len(x):
            continue
        out.append(dict(navn=f"{nm} high", pris=x.high.max(), kind="H", klar=b, dannet=x.high.idxmax()))
        out.append(dict(navn=f"{nm} low", pris=x.low.min(), kind="L", klar=b, dannet=x.low.idxmin()))
    return out


def nypre_swings(day, d):
    """5m swings inde i NY PRE, som ogsaa er high/low i et 15m swing."""
    dd = pd.Timestamp(day.date(), tz=NY)
    a, b = dd + pd.Timedelta(hours=8), dd + pd.Timedelta(hours=9, minutes=30)
    x = d[(d.index >= a - pd.Timedelta(hours=1)) & (d.index < b + pd.Timedelta(minutes=30))]
    b5, b15 = mk(x, 5), mk(x, 15)
    s15 = swings(b15)
    out = []
    for t5, c5, p5, k5 in swings(b5):
        if not (a <= t5 < b):
            continue
        for t15, c15, p15, k15 in s15:
            if k15 == k5 and t15 <= t5 < t15 + pd.Timedelta(minutes=15) and p15 == p5:
                out.append(dict(navn=f"NY PRE 5m/15m swing {'high' if k5 == 'H' else 'low'} {t5:%H:%M}",
                                pris=p5, kind=k5, klar=max(c5, c15), dannet=t5))
    return out


def h4_levels(ts, d):
    """4h-candles (TradingView CME: 18,22,02,06,10,14 NY) de sidste H4_DAGE dage, der er lukket foer ts."""
    x = d[(d.index >= ts - pd.Timedelta(days=H4_DAGE)) & (d.index < ts)]
    h = x.resample("4h", origin=pd.Timestamp("2000-01-01 18:00", tz=NY), label="left", closed="left").agg(
        {"high": "max", "low": "min"}).dropna()
    out = []
    for t, q in h.iterrows():
        e = t + pd.Timedelta(hours=4)
        if e > ts:
            continue
        out.append(dict(navn=f"4h {t:%d/%m %H:%M}", H=q.high, L=q.low, klar=e))
    return out


def untaken(lvl, kind, fra, til, d):
    y = d[(d.index >= fra) & (d.index < til)]
    if not len(y):
        return True
    return y.high.max() <= lvl if kind == "H" else y.low.min() >= lvl


def find_tp(ts, entry, long, risk, d, day):
    kind = "H" if long else "L"
    cands = []
    for L in session_levels(day, d):
        if L["kind"] != kind or L["klar"] > ts:
            continue
        cands.append((L["pris"], L["navn"], L["klar"]))
    for q in h4_levels(ts, d):
        cands.append((q[kind], q["navn"], q["klar"]))
    ok = []
    for p, nm, klar in cands:
        if (p <= entry) if long else (p >= entry):
            continue
        if not untaken(p, kind, klar, ts, d):
            continue
        ok.append((abs(p - entry), p, nm))
    ok.sort()
    naermeste = ok[0] if ok else None
    min09 = next((o for o in ok if o[0] >= MIN_RR * risk), None)
    return naermeste, min09


class Setup:
    def __init__(self, long):
        self.long = long
        self.reset()

    def reset(self):
        self.step = 0
        self.sweep = None       # (ts, navn, pris)
        self.t2 = self.t3 = None
        self.info = {}
        self.lv = {}


def run_day(day, d):
    dd = pd.Timestamp(day.date(), tz=NY)
    w0 = dd + pd.Timedelta(hours=int(STEP_FRA[:2]), minutes=int(STEP_FRA[3:]))
    e0 = dd + pd.Timedelta(hours=9, minutes=30)
    e1 = dd + pd.Timedelta(hours=12)
    x = d[(d.index >= dd - pd.Timedelta(hours=6)) & (d.index < dd + pd.Timedelta(hours=17))]
    if len(x[(x.index >= e0) & (x.index < e1)]) < 100:
        return []
    b1 = mk(x, 1); b5 = mk(x, 5)
    sw1 = swings(b1); sw5 = swings(b5)
    sess = session_levels(day, x)
    liq = [L for L in sess] + nypre_swings(day, x)
    taken = set()          # liq-niveauer der er taget (kan ikke sweeps igen)
    # Asia/London: tjek om de allerede er taget mellem session-slut og STEP_FRA
    for i, L in enumerate(liq):
        if L["klar"] < w0 and not untaken(L["pris"], L["kind"], L["klar"], w0, x):
            taken.add(i)
    S = {True: Setup(True), False: Setup(False)}
    trades = []
    busy_til = None
    # bullish 1m FVGs: (dannet_close_tid, bund, top)
    fvg = []
    for t in b1[(b1.index >= w0) & (b1.index < e1)].index:
        c = b1.loc[t]; close_t = t + pd.Timedelta(minutes=1)
        # FVG paa 1m med c som 3. candle
        i = b1.index.get_loc(t)
        if i >= 2 and b1.index[i - 2] == t - pd.Timedelta(minutes=2):
            a = b1.iloc[i - 2]
            if c.low > a.high:
                fvg.append((close_t, a.high, c.low, "bull"))
            if c.high < a.low:
                fvg.append((close_t, c.high, a.low, "bear"))
        # liq taget i dette minut
        nyt = []
        for k, L in enumerate(liq):
            if k in taken or L["klar"] > t:
                continue
            if (L["kind"] == "L" and c.low < L["pris"]) or (L["kind"] == "H" and c.high > L["pris"]):
                taken.add(k); nyt.append(L)
        if busy_til is not None and close_t <= busy_til:
            continue
        busy_til = None
        for long in (True, False):
            s = S[long]
            sweeps = [L for L in nyt if L["kind"] == ("L" if long else "H")]
            if s.step == 0:
                if sweeps:
                    L = sweeps[0]
                    s.step = 1; s.sweep = (t, L["navn"], L["pris"])
                    s.ext = c.low if long else c.high; s.anchor = t
                    s.info["sweep"] = f"{t:%H:%M} {L['navn']} {L['pris']}"
                    s.info["alle_sweeps"] = ", ".join(q["navn"] for q in sweeps)
                    s.lv = dict(sweep=(L["dannet"], t, L["pris"], L["navn"]))
                continue
            # nyt ekstrem efter sweepet (lavere low for long): setuppet lever, men step 2-4 skal ske efter det
            if (c.low < s.ext) if long else (c.high > s.ext):
                s.ext = c.low if long else c.high; s.anchor = t
                if s.step > 1:
                    s.info["nulstillet"] = s.info.get("nulstillet", 0) + 1
                s.step = 1
            st = s.anchor
            if s.step == 1:
                # 5m close over swing high dannet efter sweepet (kun ved 5m close)
                if close_t.minute % 5 == 0:
                    t5 = close_t - pd.Timedelta(minutes=5)
                    if t5 in b5.index:
                        c5 = b5.loc[t5]
                        piv = [q for q in sw5 if q[3] == ("H" if long else "L") and q[0] >= st.floor("5min")
                               and q[1] <= t5 + pd.Timedelta(minutes=5) and q[0] < t5]
                        # 5m-candlen der bryder skal lukke over et swing der var bekraeftet foer den lukkede
                        piv = [q for q in piv if q[1] <= close_t and q[0] + pd.Timedelta(minutes=5) < close_t]
                        hit = [q for q in piv if (c5.close > q[2] if long else c5.close < q[2])]
                        if hit:
                            q = hit[-1]
                            s.step = 2; s.t2 = close_t
                            s.lv["s2"] = (q[0], close_t, q[2])
                            s.info["step2"] = f"{close_t:%H:%M} 5m close {c5.close} over swing {q[0]:%H:%M} {q[2]}" if long else \
                                f"{close_t:%H:%M} 5m close {c5.close} under swing {q[0]:%H:%M} {q[2]}"
                continue
            if s.step == 2:
                # (a) FVG i tradets retning, dannet efter sweepet, lukkes igennem
                fk = "bull" if long else "bear"
                inv = None
                for (ft, lo, hi, k) in fvg:
                    if k != fk or ft - pd.Timedelta(minutes=3) < st:
                        continue
                    if ft >= close_t:
                        continue
                    if (c.close < lo) if long else (c.close > hi):
                        inv = (ft, lo, hi); break
                # (b) BOS mod tradet: close under seneste bekraeftede 1m swing low dannet efter sweepet
                kk = "L" if long else "H"
                piv = [q for q in sw1 if q[3] == kk and q[1] <= t and q[0] >= st]
                bos = None
                if piv:
                    q = piv[-1]
                    if (c.close < q[2]) if long else (c.close > q[2]):
                        bos = q
                if inv or bos:
                    s.step = 3; s.t3 = close_t
                    s.lv["s3"] = (inv[0] - pd.Timedelta(minutes=3), close_t, inv[1], inv[2], "fvg") if inv else (bos[0], close_t, bos[2], bos[2], "bos")
                    s.info["step3"] = (f"{close_t:%H:%M} FVG-inversion {inv[1]}-{inv[2]} (dannet {inv[0] - pd.Timedelta(minutes=1):%H:%M})"
                                       if inv else f"{close_t:%H:%M} 1m BOS mod tradet, swing {bos[0]:%H:%M} {bos[2]}")
                continue
            if s.step == 3:
                kk = "H" if long else "L"
                piv = [q for q in sw1 if q[3] == kk and q[1] <= t and q[0] >= st]
                if not piv:
                    continue
                q = piv[-1]
                if not ((c.close > q[2]) if long else (c.close < q[2])):
                    continue
                if close_t <= e0 or close_t > e1:
                    # signal uden for entry-vinduet: vent paa et nyt step 3 + 4
                    s.step = 2
                    s.info["foer_vindue"] = f"{close_t:%H:%M}"
                    continue
                entry = c.close
                lows = [p for p in sw1 if p[3] == ("L" if long else "H") and p[1] <= close_t and
                        ((p[2] < entry) if long else (p[2] > entry)) and
                        not brudt(b1, p, close_t, long)]
                if not lows:
                    continue
                slp = max(lows, key=lambda p: p[2]) if long else min(lows, key=lambda p: p[2])
                sl = slp[2]; risk = abs(entry - sl)
                if risk <= 0:
                    continue
                naer, min09 = find_tp(close_t, entry, long, risk, d, day)
                r = dict(dato=f"{dd:%Y-%m-%d}", retning="long" if long else "short", entry_tid=f"{close_t:%H:%M}",
                         entry=entry, sl=sl, sl_swing=f"{slp[0]:%H:%M}", risk=round(risk, 2), **s.info,
                         step4=f"{close_t:%H:%M} 1m close {c.close} {'over' if long else 'under'} swing {q[0]:%H:%M} {q[2]}")
                for tag, tp in (("A", naer), ("B", min09)):
                    if tp is None:
                        r[f"tp_{tag}"] = None; r[f"tp_{tag}_navn"] = "intet liq"; r[f"rr_{tag}"] = None
                        r[f"R_{tag}"] = None; r[f"exit_{tag}"] = None; continue
                    rr = tp[0] / risk
                    r[f"tp_{tag}"] = tp[1]; r[f"tp_{tag}_navn"] = tp[2]; r[f"rr_{tag}"] = round(rr, 2)
                    if rr < MIN_RR:
                        r[f"R_{tag}"] = None; r[f"exit_{tag}"] = f"skip (TP {rr:.2f}R < {MIN_RR}R)"; continue
                    R, ex, how = sim(x, close_t, entry, sl, tp[1], long, dd)
                    r[f"R_{tag}"] = round(R, 2); r[f"exit_{tag}"] = f"{ex:%H:%M} {how}"
                    r[f"_exit_ts_{tag}"] = ex
                r["_ts"] = close_t; r["_sweep_ts"] = s.sweep[0]
                r["_lv"] = dict(s.lv, s4=(q[0], close_t, q[2]), slp=(slp[0], slp[2]))
                trades.append(r)
                # en trade ad gangen (efter regel A); begge setups starter forfra
                if r.get("_exit_ts_A") is not None:
                    busy_til = r["_exit_ts_A"]
                for z in S.values():
                    z.reset()
                break
    return trades


def brudt(b1, p, til, long):
    """Er swinget handlet igennem (wick) efter pivot-candlen og foer entry?"""
    y = b1[(b1.index > p[0]) & (b1.index < til)]
    if not len(y):
        return False
    return y.low.min() < p[2] if long else y.high.max() > p[2]


def sim(x,t0, entry, sl, tp, long, dd):
    y = x[(x.index >= t0) & (x.index < dd + pd.Timedelta(hours=16, minutes=59))]
    risk = abs(entry - sl)
    for t, q in y.iterrows():
        hit_sl = q.low <= sl if long else q.high >= sl
        hit_tp = q.high >= tp if long else q.low <= tp
        if hit_sl:
            return -1.0, t, "SL"
        if hit_tp:
            return abs(tp - entry) / risk, t, "TP"
    last = y.close.iloc[-1] if len(y) else entry
    return ((last - entry) if long else (entry - last)) / risk, (y.index[-1] if len(y) else t0), "tid"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fra"); ap.add_argument("til")
    ap.add_argument("--ud", default="/mnt/project-files/backtest/tjr/jan-mar2026")
    a = ap.parse_args()
    d = load(a.fra, a.til)
    rows = []
    for day in pd.date_range(a.fra, a.til, freq="B", tz=NY):
        rows += run_day(day, d)
    os.makedirs(a.ud, exist_ok=True)
    df = pd.DataFrame(rows)
    df.drop(columns=[c for c in df.columns if c.startswith("_")]).to_csv(os.path.join(a.ud, "trades.csv"), index=False)
    df.to_pickle(os.path.join(a.ud, "trades.pkl"))
    for tag in "AB":
        z = df[f"R_{tag}"].dropna()
        print(tag, "trades", len(z), "win%", round((z > 0).mean() * 100, 1) if len(z) else 0, "sum R", round(z.sum(), 2))


if __name__ == "__main__":
    main()
