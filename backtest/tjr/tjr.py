"""TJR-modellen paa NQ 15s-data: 4-step (reversal) og 3-step (continuation).

Liq = dagens Asia (20:00-02:00), London (02:00-08:00) og NY PRE (08:00-09:30) high/low, plus 5m swings inde i
NY PRE, som ogsaa er high/low i et 15m swing. Kun liq der ikke er taget foer 09:30 taeller.
Alt starter ved market open 09:30 NY, og entry skal ske senest 12:00.

4-step (long, short spejlvendt):
  1. 1m handler under et liq-low (sweep).
  2. 5m close over et 5m swing high dannet efter sweepet, eller 5m close over et bearish 5m FVG (iFVG).
  3. 1m close under et bullish 1m FVG (iFVG) eller under seneste 1m swing low.
  4. 1m close over seneste 1m swing high -> market entry paa close.
3-step (long):
  1. 5m close over et liq-high.
  2. og 3. som step 3 og 4 i 4-step.
SL: naermeste 1m swing low under entry, der ikke er taget. TP: naermeste uberoerte NY PRE / London / Asia
high (dagens sessions, ingen 4h). Er naermeste liq under 0,9R, bruges
naeste liq. Intet gyldigt liq: foerste uberoerte 15m swing bagud i tid >= 0,9R. Ellers 3R.
Liq lavet i 5m-candlen 09:25-09:30 (lige op ad market open) taeller ikke.
Dagsregel: maks 2 trades, og faerdig for dagen efter en vinder. Een trade ad gangen, foerst til moelle. Setups doer ikke og nulstilles ikke.
Hvert step skal ske efter det forrige: FVG/swing i step 3 dannes efter step 2, swing i step 4 efter step 3.
Swing = high/low hoejere/lavere end candlen foer og efter, kendt foerst naar candlen efter er lukket.
"""
import argparse, json, os
import pandas as pd

NY = "America/New_York"
DATA = "/mnt/project-files/data/NQ_samlet_15s.parquet"
MIN_RR = 0.9
RAEKKE = "frisk"        # "streng": FVG/swing i step 3 dannes efter step 2, swing i step 4 efter step 3
                        # "frisk": FVG/swing maa vaere fra efter sweepet, men maa ikke vaere lukket igennem foer
MAX_TRADES = 2          # maks trades pr. dag
STOP_EFTER_WIN = True   # faerdig for dagen efter en vinder
ENTRY_FRA, ENTRY_TIL = "09:30", "12:00"
EXIT_SENEST = "16:59"
H4_DAGE = 10
BRUG_4H = False         # 4h-liq bruges ikke som TP (William 7/11): session-liq, ellers 15m swing bagud
H4_KUN_DAG = False      # True: kun 4h-candles fra den aktuelle handelsdag (fra 18:00 dagen foer)

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
    fra = ts - pd.Timedelta(days=H4_DAGE)
    if H4_KUN_DAG:
        fra = ts.normalize() - pd.Timedelta(hours=6)
    x = d[(d.index >= fra) & (d.index < ts)]
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
    for q in (h4_levels(ts, d) if BRUG_4H else []):
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
    def __init__(self, long, model):
        self.long = long; self.model = model
        self.reset()

    def reset(self):
        self.step = 0
        self.anchor = None      # step 2-4 (4-step) / 2-3 (3-step) skal dannes efter dette tidspunkt
        self.info = {}
        self.lv = {}


def run_day(day, d, rule="A"):
    """rule A: TP = naermeste liq, skip hvis < 0,9R. rule B: TP = naermeste liq >= 0,9R. Intet liq: 3R."""
    dd = pd.Timestamp(day.date(), tz=NY)
    e0 = dd + pd.Timedelta(hours=9, minutes=30)
    e1 = dd + pd.Timedelta(hours=12)
    x = d[(d.index >= dd - pd.Timedelta(hours=6)) & (d.index < dd + pd.Timedelta(hours=17))]
    if len(x[(x.index >= e0) & (x.index < e1)]) < 100:
        return []
    b1 = mk(x, 1); b5 = mk(x, 5)
    sw1 = swings(b1); sw5 = swings(b5)
    liq = session_levels(day, x) + nypre_swings(day, x)
    # kun liq der ikke er taget foer market open
    liq = [L for L in liq if L["klar"] <= e0 and untaken(L["pris"], L["kind"], L["klar"], e0, x)]
    # liq lavet i 5m-candlen lige op ad market open (09:25-09:30) taeller ikke
    liq = [L for L in liq if not (e0 - pd.Timedelta(minutes=5) <= L["dannet"] < e0)]
    taken = set()          # wick igennem (4-step sweep)
    closed = set()         # 5m close igennem (3-step BOS)
    S = [Setup(True, 4), Setup(False, 4), Setup(True, 3), Setup(False, 3)]
    trades = []
    busy_til = None
    fvg = []
    # 5m FVGs (til 4-step step 2: inversion af 5m FVG): (start 1. candle, close 3. candle, bund, top, type)
    fvg5 = []
    for j in range(2, len(b5)):
        a5, c3 = b5.iloc[j - 2], b5.iloc[j]
        if b5.index[j] - b5.index[j - 2] != pd.Timedelta(minutes=10):
            continue
        if c3.low > a5.high:
            fvg5.append((b5.index[j - 2], b5.index[j] + pd.Timedelta(minutes=5), a5.high, c3.low, "bull"))
        if c3.high < a5.low:
            fvg5.append((b5.index[j - 2], b5.index[j] + pd.Timedelta(minutes=5), c3.high, a5.low, "bear"))
    for t in b1[(b1.index >= e0) & (b1.index < e1)].index:
        c = b1.loc[t]; close_t = t + pd.Timedelta(minutes=1)
        i = b1.index.get_loc(t)
        if i >= 2 and b1.index[i - 2] == t - pd.Timedelta(minutes=2):
            a = b1.iloc[i - 2]
            if c.low > a.high:
                fvg.append((close_t, a.high, c.low, "bull"))
            if c.high < a.low:
                fvg.append((close_t, c.high, a.low, "bear"))
        nyt = []
        for k, L in enumerate(liq):
            if k in taken:
                continue
            if (L["kind"] == "L" and c.low < L["pris"]) or (L["kind"] == "H" and c.high > L["pris"]):
                taken.add(k); nyt.append(L)
        bos5 = []
        c5 = None
        if close_t.minute % 5 == 0 and (close_t - pd.Timedelta(minutes=5)) in b5.index:
            t5 = close_t - pd.Timedelta(minutes=5); c5 = b5.loc[t5]
            for k, L in enumerate(liq):
                if k in closed:
                    continue
                if (L["kind"] == "H" and c5.close > L["pris"]) or (L["kind"] == "L" and c5.close < L["pris"]):
                    closed.add(k); bos5.append(L)
        busy = busy_til is not None and close_t <= busy_til
        if not busy:
            busy_til = None
        for s in S:
            long = s.long
            if s.step == 0:
                if s.model == 4:
                    sweeps = [L for L in nyt if L["kind"] == ("L" if long else "H")]
                    if sweeps:
                        L = sweeps[0]
                        s.step = 1; s.anchor = t
                        s.info["step1"] = f"{t:%H:%M} sweep af {L['navn']} {L['pris']}"
                        s.info["liq"] = L["navn"]
                        s.lv = dict(sweep=(L["dannet"], t, L["pris"], L["navn"]))
                else:
                    br = [L for L in bos5 if L["kind"] == ("H" if long else "L")]
                    if br:
                        L = br[0]; t5 = close_t - pd.Timedelta(minutes=5)
                        s.step = 2; s.anchor = t5; s.t2 = close_t
                        s.info["step1"] = f"{close_t:%H:%M} 5m close {c5.close} {'over' if long else 'under'} {L['navn']} {L['pris']}"
                        s.info["liq"] = L["navn"]
                        s.lv = dict(sweep=(L["dannet"], t5, L["pris"], L["navn"]))
                continue
            st = s.anchor
            if s.step == 1:
                if c5 is not None:
                    t5 = close_t - pd.Timedelta(minutes=5)
                    piv = [q for q in sw5 if q[3] == ("H" if long else "L") and q[0] >= st.floor("5min")
                           and q[1] <= t5 and q[0] < t5]
                    hit = [q for q in piv if (c5.close > q[2] if long else c5.close < q[2])]
                    # ... eller en 5m-candle lukker igennem et 5m FVG i modsat retning (inversion), dannet op til 1 time foer sweepet
                    ifv = [g for g in fvg5 if g[4] == ("bear" if long else "bull") and g[0] >= st - pd.Timedelta(hours=1)
                           and g[1] <= t5 and ((c5.close > g[3]) if long else (c5.close < g[2]))]
                    if not hit and ifv:
                        g = ifv[-1]
                        s.step = 2; s.t2 = close_t
                        s.lv["s2"] = (g[0], close_t, g[3] if long else g[2])
                        s.info["step2"] = f"{close_t:%H:%M} 5m close {c5.close} {'over' if long else 'under'} 5m FVG {g[2]}-{g[3]} (iFVG, dannet {g[0]:%H:%M})"
                    if hit:
                        q = hit[-1]
                        s.step = 2; s.t2 = close_t
                        s.lv["s2"] = (q[0], close_t, q[2])
                        s.info["step2"] = f"{close_t:%H:%M} 5m close {c5.close} {'over' if long else 'under'} swing {q[0]:%H:%M} {q[2]}"
                continue
            if s.step == 2:
                fk = "bull" if long else "bear"
                inv = None
                for (ft, lo, hi, k) in fvg:
                    if k != fk or ft >= close_t:
                        continue
                    if RAEKKE == "streng" and ft - pd.Timedelta(minutes=3) < s.t2:
                        continue
                    if RAEKKE == "frisk" and (ft - pd.Timedelta(minutes=3) < st or lukket(b1, ft, t, lo if long else hi, not long)):
                        continue
                    if (c.close < lo) if long else (c.close > hi):
                        inv = (ft, lo, hi); break
                kk = "L" if long else "H"
                fra2 = s.t2 if RAEKKE == "streng" else st
                piv = [q for q in sw1 if q[3] == kk and q[1] <= t and q[0] >= fra2]
                if RAEKKE == "frisk":
                    piv = [q for q in piv if not lukket(b1, q[1], t, q[2], not long)]
                bos = None
                if piv:
                    q = piv[-1]
                    if (c.close < q[2]) if long else (c.close > q[2]):
                        bos = q
                if inv or bos:
                    s.step = 3; s.t3 = close_t
                    s.lv["s3"] = (inv[0] - pd.Timedelta(minutes=3), close_t, inv[1], inv[2], "fvg") if inv else (bos[0], close_t, bos[2], bos[2], "bos")
                    s.info["pullback"] = (f"{close_t:%H:%M} iFVG {inv[1]}-{inv[2]} (dannet {inv[0] - pd.Timedelta(minutes=1):%H:%M})"
                                          if inv else f"{close_t:%H:%M} 1m BOS mod tradet, swing {bos[0]:%H:%M} {bos[2]}")
                    s.info["pullback_type"] = "iFVG" if inv else "BOS"
                continue
            if s.step == 3:
                kk = "H" if long else "L"
                fra3 = s.t3 - pd.Timedelta(minutes=1) if RAEKKE == "streng" else st
                piv = [q for q in sw1 if q[3] == kk and q[1] <= t and q[0] >= fra3]
                if RAEKKE == "frisk":
                    piv = [q for q in piv if not lukket(b1, q[1], t, q[2], long)]
                if not piv:
                    continue
                q = piv[-1]
                if not ((c.close > q[2]) if long else (c.close < q[2])):
                    continue
                if busy:                              # i et andet trade: vent paa en ny pullback + BOS
                    s.step = 2; s.t2 = close_t
                    continue
                entry = c.close
                lows = [p for p in sw1 if p[3] == ("L" if long else "H") and p[1] <= close_t and
                        ((p[2] < entry) if long else (p[2] > entry)) and not brudt(b1, p, close_t, long)]
                if not lows:
                    continue
                slp = max(lows, key=lambda p: p[2]) if long else min(lows, key=lambda p: p[2])
                sl = slp[2]; risk = abs(entry - sl)
                if risk <= 0:
                    continue
                naer, min09 = find_tp(close_t, entry, long, risk, d, day)
                tp = naer if rule == "A" else min09
                r = dict(dato=f"{dd:%Y-%m-%d}", model=f"{s.model}-step", retning="long" if long else "short",
                         entry_tid=f"{close_t:%H:%M}", entry=entry, sl=sl, sl_swing=f"{slp[0]:%H:%M}", risk=round(risk, 2), **s.info,
                         entry_bos=f"{close_t:%H:%M} 1m close {c.close} {'over' if long else 'under'} swing {q[0]:%H:%M} {q[2]}")
                if tp is None:                        # intet gyldigt liq: foerste 15m swing bagud i tid, der er >= 0,9R
                    tp = swing15(close_t, entry, long, risk, d)
                if tp is None:                        # stadig intet (fx ATH): fast 3R
                    tp = (3 * risk, entry + 3 * risk if long else entry - 3 * risk, "3R (intet liq)")
                rr = tp[0] / risk
                r.update(tp=tp[1], tp_navn=tp[2], rr=round(rr, 2))
                r["_ts"] = close_t
                r["_lv"] = dict(s.lv, s4=(q[0], close_t, q[2]), slp=(slp[0], slp[2]))
                if rr < MIN_RR - 1e-9:
                    r.update(R=None, exit=f"skip (TP {rr:.2f}R < {MIN_RR}R)", status="skip")
                    trades.append(r)
                    s.reset()
                    continue
                R, ex, how = sim(x, close_t, entry, sl, tp[1], long, dd)
                r.update(R=round(R, 2), exit=f"{ex:%H:%M} {how}", status=how)
                r["_exit_ts"] = ex
                trades.append(r)
                busy_til = ex
                if len(trades) >= MAX_TRADES or (STOP_EFTER_WIN and R > 0):
                    return trades
                s.reset()                             # kun det setup der handlede starter forfra
                break
    return trades


def swing15(ts, entry, long, risk, d):
    """Kig tilbage paa 15m: det foerste (nyeste) swing high (long) / low (short), der ikke er taget og er >= 0,9R vaek."""
    x = d[(d.index >= ts - pd.Timedelta(days=H4_DAGE)) & (d.index < ts)]
    b = mk(x, 15)
    kk = "H" if long else "L"
    for t0, conf, p, k in reversed(swings(b)):
        if k != kk or conf > ts:
            continue
        if abs(p - entry) < MIN_RR * risk or ((p <= entry) if long else (p >= entry)):
            continue
        if not untaken(p, kk, t0 + pd.Timedelta(minutes=15), ts, x):
            continue
        return (abs(p - entry), p, f"15m swing {t0:%d/%m %H:%M}")
    return None


def lukket(b1, fra, til, lvl, over):
    """Har en 1m-candle lukket over (over=True) / under lvl i [fra, til)?"""
    y = b1[(b1.index >= fra) & (b1.index < til)]
    if not len(y):
        return False
    return (y.close > lvl).any() if over else (y.close < lvl).any()


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
    ap.add_argument("--uden-dagsregel", action="store_true", help="ingen maks 2 trades / stop efter win")
    ap.add_argument("--raekke", default="frisk", choices=["streng", "frisk"])
    ap.add_argument("--h4-kun-dag", action="store_true", help="kun dagens 4h-candles som TP")
    a = ap.parse_args()
    global MAX_TRADES, STOP_EFTER_WIN, H4_KUN_DAG, RAEKKE
    H4_KUN_DAG = a.h4_kun_dag
    RAEKKE = a.raekke
    if a.uden_dagsregel:
        MAX_TRADES, STOP_EFTER_WIN = 99, False
    d = load(a.fra, a.til)
    os.makedirs(a.ud, exist_ok=True)
    alle = []
    for rule in "B":
        rows = []
        for day in pd.date_range(a.fra, a.til, freq="B", tz=NY):
            rows += run_day(day, d, rule)
        df = pd.DataFrame(rows); df.insert(0, "regel", rule)
        alle.append(df)
        z = df[df.status != "skip"]
        print(rule, "trades", len(z), "win%", round((z.R > 0).mean() * 100, 1), "sum R", round(z.R.sum(), 2),
              z.groupby("model").R.agg(["count", "sum"]).round(2).to_dict())
    df = pd.concat(alle, ignore_index=True)
    df.drop(columns=[c for c in df.columns if c.startswith("_")]).to_csv(os.path.join(a.ud, "trades.csv"), index=False)
    df.to_pickle(os.path.join(a.ud, "trades.pkl"))


if __name__ == "__main__":
    main()
