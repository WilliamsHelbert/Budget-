"""Laver JSON til TJR-artifacten: trades for regel A og B + 1m-bars 09:00-17:00 for hver handelsdag."""
import json, sys, os
import pandas as pd
import tjr

ud = sys.argv[1]
df = pd.read_pickle(os.path.join(ud, "trades.pkl"))
d = tjr.load(df.dato.min(), df.dato.max())
mins = lambda t: round((t - t.normalize()).total_seconds() / 60, 2)   # minutter efter midnat NY


def f(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else v


trades = []
for _, r in df.iterrows():
    lv = r["_lv"]
    ex = r.get("_exit_ts")
    t = dict(regel=r.regel, dato=r.dato, model=r.model, retning=r.retning, entry_tid=r.entry_tid, entry=r.entry, sl=r.sl,
             risk=r.risk, tp=f(r.tp), tp_navn=r.tp_navn, rr=f(r.rr), R=f(r.R), exit=r.exit, status=r.status,
             liq=r.liq, step1=r.step1, step2=f(r.get("step2")), pullback=r.pullback, pullback_type=r.pullback_type,
             entry_bos=r.entry_bos, sl_swing=r.sl_swing,
             t_entry=mins(r["_ts"]), t_exit=mins(ex) if isinstance(ex, pd.Timestamp) else None,
             lv=dict(liq=[mins(lv["sweep"][0]), mins(lv["sweep"][1]), lv["sweep"][2], lv["sweep"][3]],
                     s2=[mins(lv["s2"][0]), mins(lv["s2"][1]), lv["s2"][2]] if "s2" in lv else None,
                     s3=[mins(lv["s3"][0]), mins(lv["s3"][1]), lv["s3"][2], lv["s3"][3], lv["s3"][4]],
                     s4=[mins(lv["s4"][0]), mins(lv["s4"][1]), lv["s4"][2]]))
    if lv["sweep"][0].date() != r["_ts"].date():
        t["lv"]["liq"][0] = 0
    trades.append(t)
bars = {}
for dato in sorted(df.dato.unique()):
    dd = pd.Timestamp(dato, tz=tjr.NY)
    x = d[(d.index >= dd + pd.Timedelta(hours=7)) & (d.index < dd + pd.Timedelta(hours=17))]
    b = tjr.bars(x, 1)
    bars[dato] = dict(t0=mins(b.index[0]), o=b.open.round(2).tolist(), h=b.high.round(2).tolist(),
                      l=b.low.round(2).tolist(), c=b.close.round(2).tolist(),
                      m=[int(mins(t) - mins(b.index[0])) for t in b.index])
json.dump(dict(trades=trades, bars=bars), open(os.path.join(ud, "artifact_data.json"), "w"), separators=(",", ":"))
print(len(trades), "trades", len(bars), "dage", os.path.getsize(os.path.join(ud, "artifact_data.json")) // 1024, "KB")
