import sys; sys.path.insert(0, "/home/claude/Budget-/backtest")
import pandas as pd, fvg_model as f
TZ = f.TZ
d = f.load("/tmp/claude-0/-home-claude-Budget-/372a5c37-dbae-50e8-bc84-def41e700d5d/scratchpad/NQ_okt.parquet")
f.SESS = {"Asia": ("20:00", "02:00"), "London": ("02:00", "08:00")}
f.EXTRA = {"PDH", "4h alle"}
orig = f.levels

def prevday(day):
    p = pd.Timestamp(day) - pd.Timedelta(days=1)
    while p.weekday() >= 5: p -= pd.Timedelta(days=1)
    return f"{p.date()}"

def levels(d, day):
    out = orig(d, day)
    for k, v in orig(d, prevday(day)).items():
        if not k.startswith("4h") and k != "PDH/PDL":
            out[k + " i gaar"] = v
    return out

def tp_levels(d, day, s, entry, short):
    c = []
    for nm, (hi, lo, e) in levels(d, day).items():
        if nm.startswith("4h") or e > s: continue
        v = lo if short else hi
        if (v >= entry) if short else (v <= entry): continue
        x = d[e:s - pd.Timedelta(seconds=1)]
        if len(x) and ((x.low.min() < v) if short else (x.high.max() > v)): continue
        c.append((v, nm))
    for nm, (a, b) in f.SESS.items():          # session der koerer nu
        for back in (0, 1):
            s0 = pd.Timestamp(f"{(s - pd.Timedelta(days=back)).date()} {a}").tz_localize(TZ)
            if s0 <= s < s0 + pd.Timedelta(hours=6):
                x = d[s0:s - pd.Timedelta(seconds=1)]
                v = x.low.min() if short else x.high.max()
                if (v < entry) if short else (v > entry): c.append((v, nm + " (live)"))
    return c

def tp_func(d, day, tc, ref, short, entry, risk):
    c = [q for q in tp_levels(d, day, tc, entry, short) if abs(q[0] - entry) >= f.MIN_RR * risk]
    return min(c, key=lambda q: abs(q[0] - entry))[0] if c else None

def run(days, verbose=False, **kw):
    f.levels = levels
    f.WIN = ("00:00", "16:59"); f.LEG_FROM = "00:00"; f.PRE = pd.Timedelta(hours=6)
    f.MULTI = True; f.TP_FUNC = tp_func; f.MIN_RR = 0.0
    f.EXIT_END = lambda day, tc: pd.Timestamp(f"{day} 16:59:45").tz_localize(TZ)
    f.RECLAIM = False; f.CONSUME = False; f.MAX_SWEEP_ENTRY = None
    f.LEG_MID = False; f.OLDEST = False; f.INSIDE = False; f.OWN_LEG = False; f.FVG_UNFILLED = False; f.FVG_NEAR = None
    for k, v in kw.items(): setattr(f, k, v)
    rows = []
    for day in days:
        for r in f.run_day(d, day, log=(lambda *a: print(day, *a)) if verbose else (lambda *a: None)):
            d0 = pd.Timestamp(day).tz_localize(TZ) - pd.Timedelta(hours=6)
            if not (d0 <= r["ts"] < d0 + pd.Timedelta(hours=23)): continue
            short = r["retning"] == "SHORT"
            tpn = next((nm for v, nm in tp_levels(d, day, r["ts"], r["entry"], short) if v == r["tp_4h"]), "")
            rows.append(dict(dag=day, sweep_dk=f"{r['sweep_ts']+pd.Timedelta(hours=6):%d/%m %H:%M}",
                             entry_dk=f"{r['ts']+pd.Timedelta(hours=6):%d/%m %H:%M}", retning=r["retning"],
                             sweep=r["sweep"], tf=r["fvg_tf"], entry=r["entry"], sl=r["sl"], tp=r["tp_4h"], tp_navn=tpn, rr=r["rr"]))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    days = ["2026-10-01", "2026-10-02", "2026-10-05"]
    print(run(days).to_string(index=False))
