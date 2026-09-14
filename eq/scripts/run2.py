"""Dual-asset EQ backtest. Pure-python hot loop over int epoch seconds."""
import pandas as pd, numpy as np, sys, os, json
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = "Europe/Copenhagen"
OPEN_MIN, CLOSE_MIN = 15*60+30, 22*60          # CPH: 15:30 open, 22:00 RTH close
R_UNIT = {"ES": 2.0, "NQ": 10.0}
TP_PTS = {"ES": 15.0, "NQ": 75.0}
SYMS = ("ES", "NQ")

ARM_TIMEOUT = int(os.environ.get("ARM_TIMEOUT", 30)) * 60
CONF_SEC    = int(os.environ.get("CONF_SEC", 60))       # confirmation candle length
ONE_AT_A_TIME = os.environ.get("ONE_AT_A_TIME", "1") == "1"
TAG = os.environ.get("TAG", f"conf{CONF_SEC}")

def prep(sym):
    df = pd.read_parquet(f"{BASE}/{sym}.parquet")
    t = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    secs = t.dt.tz_convert("UTC").dt.tz_localize(None).astype("datetime64[s]").astype("int64")
    df = df.assign(ts=secs, tod=t.dt.hour*60+t.dt.minute, day=t.dt.strftime("%Y-%m-%d"))
    df = df.sort_values("ts").reset_index(drop=True)
    return df

def buckets(df, sec):
    """-> dict bucket_start_ts -> (o,h,l,c)"""
    b = (df["ts"] // sec) * sec
    g = df.groupby(b)
    out = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(),
                        "l": g["low"].min(), "c": g["close"].last()})
    return {int(k): (float(o), float(h), float(l), float(c))
            for k, o, h, l, c in zip(out.index, out.o, out.h, out.l, out.c)}

DF  = {k: prep(k) for k in SYMS}
BAR = {k: {int(ts): (float(o), float(h), float(l), float(c))
           for ts, o, h, l, c in zip(DF[k].ts, DF[k].open, DF[k].high, DF[k].low, DF[k].close)}
       for k in SYMS}
M1   = {k: buckets(DF[k], 60)  for k in SYMS}
M5   = {k: buckets(DF[k], 300) for k in SYMS}
CONF = {k: buckets(DF[k], CONF_SEC) for k in SYMS}
TOD  = {}; DAY = {}
for k in SYMS:
    for ts, td, d in zip(DF[k].ts, DF[k].tod, DF[k].day):
        TOD[int(ts)] = int(td); DAY[int(ts)] = d
TL = sorted(set(map(int, DF["ES"].ts)) | set(map(int, DF["NQ"].ts)))

def fmt(ts):
    return pd.Timestamp(ts, unit="s", tz="UTC").tz_convert(TZ).strftime("%Y-%m-%d %H:%M:%S")

# ---------------- state ----------------
bear = {k: None for k in SYMS}   # (anchor, running_ext)
bull = {k: None for k in SYMS}
day  = {k: None for k in SYMS}
pmin = {k: None for k in SYMS}; pconf = {k: None for k in SYMS}; pm5 = {k: None for k in SYMS}
trades, log = [], []
armed = None; open_trade = None
skipped = both_hit = 0
n_eq = {"ES_bear":0,"ES_bull":0,"NQ_bear":0,"NQ_bull":0}
n_hit = {"clean":0,"closed_over":0}
n_armed = 0

for ts in TL:
    tod = TOD[ts]; d = DAY[ts]
    mb, cb, m5b = ts//60*60, ts//CONF_SEC*CONF_SEC, ts//300*300
    bars = {k: BAR[k].get(ts) for k in SYMS}

    newmin = {}
    for k in SYMS:
        if bars[k] is None: newmin[k] = None; continue
        newmin[k] = M1[k].get(pmin[k]) if (pmin[k] is not None and mb != pmin[k]) else None
        pmin[k] = mb

    pre_bear = dict(bear); pre_bull = dict(bull)
    hits = []
    reset = False
    for k in SYMS:
        b = bars[k]
        if b is None: continue
        o, h, l, c = b
        if tod >= OPEN_MIN and day[k] != d:
            day[k] = d; bear[k] = bull[k] = None; reset = True
        if bear[k]:
            a, e = bear[k]; e = min(e, l); lvl = (a+e)/2.0
            if h >= lvl:
                hits.append((k, "bear", lvl, a, c > lvl)); bear[k] = None
            else: bear[k] = (a, e)
        if bull[k]:
            a, e = bull[k]; e = max(e, h); lvl = (a+e)/2.0
            if l <= lvl:
                hits.append((k, "bull", lvl, a, c < lvl)); bull[k] = None
            else: bull[k] = (a, e)
        pm = newmin[k]
        if pm is not None and tod >= OPEN_MIN:
            po, ph, pl, pc = pm; eq1 = (ph+pl)/2.0
            if pc < po and pc < eq1 and bear[k] is None:
                bear[k] = (ph, min(pl, l)); n_eq[k+"_bear"] += 1
            if pc > po and pc > eq1 and bull[k] is None:
                bull[k] = (pl, max(ph, h)); n_eq[k+"_bull"] += 1
    if reset: armed = None

    # ---------- manage open trade ----------
    if open_trade is not None:
        for k in SYMS:
            lg = open_trade["legs"][k]
            if lg["exit"] is not None: continue
            b = bars[k]
            if pm5[k] is not None and m5b != pm5[k] and not lg["be"]:
                c5 = M5[k].get(pm5[k])
                if c5: lg["ref"] = c5[2] if open_trade["side"] == "bear" else c5[1]
            if b is None: continue
            o, h, l, c = b
            short = open_trade["side"] == "bear"
            sl = (h >= lg["stop"]) if short else (l <= lg["stop"])
            tp = (l <= lg["tp"])   if short else (h >= lg["tp"])
            if sl and tp: both_hit += 1
            if sl:   lg.update(exit=lg["stop"], exit_t=ts, reason="BE" if lg["be"] else "SL")
            elif tp: lg.update(exit=lg["tp"],   exit_t=ts, reason="TP")
            else:
                if not lg["be"] and lg["ref"] is not None:
                    if (l < lg["ref"]) if short else (h > lg["ref"]):
                        lg["be"] = True; lg["stop"] = lg["entry"]; lg["be_t"] = ts
                if tod >= CLOSE_MIN: lg.update(exit=c, exit_t=ts, reason="EOD")
        if all(open_trade["legs"][k]["exit"] is not None for k in SYMS):
            trades.append(open_trade); open_trade = None
    for k in SYMS:
        if bars[k] is not None: pm5[k] = m5b

    # ---------- arming ----------
    for (k, side, lvl, anch, closed_over) in hits:
        n_hit["closed_over" if closed_over else "clean"] += 1
        if closed_over: continue
        other = "NQ" if k == "ES" else "ES"
        pre = pre_bear if side == "bear" else pre_bull
        if pre[k] is None or pre[other] is None: continue
        armed = dict(side=side, ts=ts, hit=k, lvl=lvl,
                     anchors={k: anch, other: pre[other][0]})
        n_armed += 1

    # ---------- entry ----------
    conf = {}
    for k in SYMS:
        if bars[k] is None: conf[k] = None; continue
        conf[k] = CONF[k].get(pconf[k]) if (pconf[k] is not None and cb != pconf[k]) else None
        pconf[k] = cb

    if armed and conf["ES"] is not None and conf["NQ"] is not None:
        side = armed["side"]
        if ts - armed["ts"] > ARM_TIMEOUT or tod >= CLOSE_MIN:
            armed = None
        else:
            ch = conf[armed["hit"]]
            dead = (ch[3] > armed["lvl"]) if side == "bear" else (ch[3] < armed["lvl"])
            ok = all(conf[k][3] < conf[k][0] for k in SYMS) if side == "bear" \
                 else all(conf[k][3] > conf[k][0] for k in SYMS)
            if dead: armed = None
            elif ok:
                if open_trade is not None and ONE_AT_A_TIME: skipped += 1
                else:
                    legs = {}
                    for k in SYMS:
                        ent = conf[k][3]; stop = armed["anchors"][k]
                        legs[k] = dict(entry=ent, stop=stop, init_stop=stop,
                                       tp=ent-TP_PTS[k] if side=="bear" else ent+TP_PTS[k],
                                       be=False, ref=None, be_t=None,
                                       exit=None, exit_t=None, reason=None)
                    open_trade = dict(side=side, ts=ts, day=d, legs=legs,
                                      hit=armed["hit"], hit_ts=armed["ts"])
                    for k in SYMS: pm5[k] = m5b
                armed = None

if open_trade is not None:
    for k in SYMS:
        lg = open_trade["legs"][k]
        if lg["exit"] is None:
            lg.update(exit=float(DF[k]["close"].iloc[-1]), exit_t=TL[-1], reason="EOD")
    trades.append(open_trade)

recs = []
for tr in trades:
    for k in SYMS:
        lg = tr["legs"][k]; sgn = -1 if tr["side"] == "bear" else 1
        pts = sgn*(lg["exit"]-lg["entry"])
        recs.append(dict(day=tr["day"], entry_t=fmt(tr["ts"]), hit_t=fmt(tr["hit_ts"]),
                         side="SHORT" if tr["side"]=="bear" else "LONG", asset=k,
                         hit_asset=tr["hit"], entry=lg["entry"], stop=lg["init_stop"],
                         tp=lg["tp"], exit=lg["exit"], exit_t=fmt(lg["exit_t"]),
                         reason=lg["reason"], moved_be=lg["be"],
                         be_t=fmt(lg["be_t"]) if lg["be_t"] else "",
                         stop_dist=round(abs(lg["entry"]-lg["init_stop"]),2),
                         pts=round(pts,4), R=round(pts/R_UNIT[k],4)))
res = pd.DataFrame(recs)
res.to_csv(f"{BASE}/trades_{TAG}.csv", index=False)
print(f"[{TAG}] EQs created: {n_eq}")
print(f"[{TAG}] EQ hits: clean={n_hit['clean']} closed_over={n_hit['closed_over']} | armed setups={n_armed}")
print(f"[{TAG}] trade pairs={len(trades)} skipped(overlap)={skipped} SL+TP same 15s bar={both_hit}")
if len(res):
    for k in SYMS:
        s = res[res.asset==k]
        print(f"   {k}: n={len(s):3d} TP={sum(s.reason=='TP'):3d} SL={sum(s.reason=='SL'):3d} "
              f"BE={sum(s.reason=='BE'):3d} EOD={sum(s.reason=='EOD'):3d} | "
              f"totR={s.R.sum():+8.2f} avgR={s.R.mean():+.3f} | avgStop={s.stop_dist.mean():.2f}pts "
              f"(={s.stop_dist.mean()/R_UNIT[k]:.2f}R)")
    print(f"   COMBINED totR={res.R.sum():+.2f} over {len(trades)} pairs")
