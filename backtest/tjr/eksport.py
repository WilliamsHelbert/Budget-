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
# match mod Williams journal
import match as M
w = M.load_j()
par, used = M.match(df, w)
pm = {j: i for i, j, _ in par}
sidste = w.dato.max()
for t, (j, r) in zip(trades, df.iterrows()):
    if j in pm:
        q = w.loc[pm[j]]; t["journal"] = "enig"; t["w_tid"] = q.ny; t["w_R"] = float(q.r)
    else:
        t["journal"] = "kun_motor" if r.dato <= sidste else "ikke_tjekket"
pi = {i for i, _, _ in par}
for i, q in w.iterrows():
    if i in pi:
        continue
    mm = df[df.dato == q.dato]
    trades.append(dict(regel=df.regel.iloc[0], dato=q.dato, model="William", retning=q.retning, entry_tid=q.ny,
                       R=float(q.r), status="william", journal="kun_william", liq="", tp_navn="", pullback_type="",
                       t_entry=int(q.ny[:2]) * 60 + int(q.ny[3:]), lv=None,
                       motor_dag="; ".join(f"{a.entry_tid} {a.retning} {a.model} {a.R:+.2f}R" for _, a in mm.iterrows()) or "ingen"))
trades.sort(key=lambda t: (t["dato"], t["entry_tid"]))
bars = {}
for dato in sorted(set(t["dato"] for t in trades)):
    dd = pd.Timestamp(dato, tz=tjr.NY)
    x = d[(d.index >= dd + pd.Timedelta(hours=7)) & (d.index < dd + pd.Timedelta(hours=17))]
    b = tjr.bars(x, 1)
    bars[dato] = dict(t0=mins(b.index[0]), o=b.open.round(2).tolist(), h=b.high.round(2).tolist(),
                      l=b.low.round(2).tolist(), c=b.close.round(2).tolist(),
                      m=[int(mins(t) - mins(b.index[0])) for t in b.index])
# alle klokkeslaet i tekst -> dansk tid (chart-geometri bliver i NY-minutter, aksen faar dk-offset)
import re
def dk_off(dato):
    t = pd.Timestamp(dato + " 12:00", tz=tjr.NY)
    return int((t.tz_convert("Europe/Copenhagen").utcoffset() - t.utcoffset()).total_seconds() // 60)
def til_dk(txt, dato):
    if not isinstance(txt, str):
        return txt
    y0 = int(dato[:4]); m0 = int(dato[5:7])
    def full(m):
        dd, mm, hh, mi = map(int, m.groups()); y = y0 - 1 if (mm == 12 and m0 == 1) else y0
        t = pd.Timestamp(year=y, month=mm, day=dd, hour=hh, minute=mi, tz=tjr.NY).tz_convert("Europe/Copenhagen")
        return f"{t:%d/%m %H:%M}"
    txt = re.sub(r"(\d{2})/(\d{2}) (\d{2}):(\d{2})", lambda m: "\x00" + full(m), txt)
    def kort(m):
        hh, mi = int(m.group(1)), int(m.group(2)); tot = hh * 60 + mi + dk_off(dato)
        return f"{tot // 60 % 24:02d}:{tot % 60:02d}"
    parts = txt.split("\x00")
    out = [re.sub(r"(?<![\d/])(\d{2}):(\d{2})(?!\d)", kort, parts[0])]
    for q in parts[1:]:
        out.append(q[:11] + re.sub(r"(?<![\d/])(\d{2}):(\d{2})(?!\d)", kort, q[11:]))
    return "".join(out)
for t in trades:
    for k, v in list(t.items()):
        if k != "dato" and isinstance(v, str):
            t[k] = til_dk(v, t["dato"])
for k in bars:
    bars[k]["dk"] = dk_off(k)
json.dump(dict(trades=trades, bars=bars), open(os.path.join(ud, "artifact_data.json"), "w"), separators=(",", ":"))
print(len(trades), "trades", len(bars), "dage", os.path.getsize(os.path.join(ud, "artifact_data.json")) // 1024, "KB")
