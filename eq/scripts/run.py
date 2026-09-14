import pandas as pd, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from eq import *

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARM_TIMEOUT_MIN = int(os.environ.get("ARM_TIMEOUT", 30))
CONF_TF = os.environ.get("CONF_TF", "1min")      # confirmation-candle TF
ONE_AT_A_TIME = os.environ.get("ONE_AT_A_TIME", "1") == "1"

es = load("ES", f"{BASE}/ES.parquet")
nq = load("NQ", f"{BASE}/NQ.parquet")
D = {"ES": es, "NQ": nq}
M1 = {k: agg(v, "min") for k, v in D.items()}
M5 = {k: agg(v, "m5") for k, v in D.items()}
CONF = {k: agg(v, v["time"].dt.floor(CONF_TF)) for k, v in D.items()}

# union 15s timeline
tl = sorted(set(es["time"]) | set(nq["time"]))
rows = {k: v.set_index("time") for k, v in D.items()}
trk = {k: EQTracker(M1[k]) for k in D}

trades, signals = [], []
armed = None
open_trade = None
skipped = 0
sl_tp_same_bar = 0

prev_conf_bucket = {k: None for k in D}
prev_min_bucket = {k: None for k in D}
prev_m5_bucket = {k: None for k in D}

def eod(t):
    return t.hour * 60 + t.minute >= CLOSE_H * 60 + CLOSE_M

for t in tl:
    bars = {k: (rows[k].loc[t] if t in rows[k].index else None) for k in D}

    # ---------- 1m completion detection (per asset) ----------
    newmin = {}
    for k in D:
        b = bars[k]
        if b is None:
            newmin[k] = None; continue
        mb = t.floor("1min")
        pm = None
        if prev_min_bucket[k] is not None and mb != prev_min_bucket[k]:
            pm = M1[k].loc[prev_min_bucket[k]]
        prev_min_bucket[k] = mb
        newmin[k] = pm

    # snapshot EQ state BEFORE this bar (for the "both same direction" test)
    pre = {k: {"bear": trk[k].bear, "bull": trk[k].bull} for k in D}

    # ---------- EQ tracker ----------
    events = {}
    for k in D:
        b = bars[k]
        if b is None:
            events[k] = []; continue
        bb = b.copy(); bb["time"] = t
        events[k] = trk[k].on_bar(bb, newmin[k])

    reset_now = any(e[0] == "reset" for k in D for e in events[k])
    if reset_now:
        armed = None
        if open_trade is not None:
            pass  # positions are managed to their own exits, not wiped

    # ---------- manage the open trade ----------
    if open_trade is not None:
        for k in D:
            lg = open_trade["legs"][k]
            if lg["exit"] is not None:
                continue
            b = bars[k]
            # 5m completion -> update liquidity reference
            if b is not None:
                m5b = t.floor("5min")
                if prev_m5_bucket[k] is not None and m5b != prev_m5_bucket[k]:
                    c5 = M5[k].loc[prev_m5_bucket[k]]
                    if not lg["be"]:
                        lg["ref"] = c5["low"] if open_trade["side"] == "bear" else c5["high"]
                prev_m5_bucket[k] = m5b
            if b is None:
                continue
            short = open_trade["side"] == "bear"
            hit_sl = (b["high"] >= lg["stop"]) if short else (b["low"] <= lg["stop"])
            hit_tp = (b["low"] <= lg["tp"]) if short else (b["high"] >= lg["tp"])
            if hit_sl and hit_tp:
                globals()['sl_tp_same_bar'] += 1
            if hit_sl:
                lg["exit"] = lg["stop"]; lg["exit_t"] = t
                lg["reason"] = "BE" if lg["be"] else "SL"
            elif hit_tp:
                lg["exit"] = lg["tp"]; lg["exit_t"] = t; lg["reason"] = "TP"
            else:
                if not lg["be"] and lg["ref"] is not None:
                    swept = (b["low"] < lg["ref"]) if short else (b["high"] > lg["ref"])
                    if swept:
                        lg["be"] = True; lg["stop"] = lg["entry"]; lg["be_t"] = t
                if eod(t):
                    lg["exit"] = b["close"]; lg["exit_t"] = t; lg["reason"] = "EOD"
        if all(open_trade["legs"][k]["exit"] is not None for k in D):
            trades.append(open_trade); open_trade = None
    else:
        for k in D:
            prev_m5_bucket[k] = t.floor("5min")

    # ---------- arming: one asset hits its EQ, both had same-dir EQ ----------
    for k in D:
        for typ, info in events[k]:
            if typ != "hit" or info["closed_over"]:
                continue
            side = info["side"]
            other = "NQ" if k == "ES" else "ES"
            if pre[k][side] is None or pre[other][side] is None:
                continue
            armed = dict(side=side, t=t, hit_asset=k, hit_level=info["level"],
                         anchors={k: info["anchor"], other: pre[other][side].anchor},
                         eqlvl={k: info["level"], other: pre[other][side].eq})

    # ---------- entry check on confirmation-candle close ----------
    conf_done = {}
    for k in D:
        if bars[k] is None:
            conf_done[k] = None; continue
        cb = t.floor(CONF_TF)
        pc = None
        if prev_conf_bucket[k] is not None and cb != prev_conf_bucket[k]:
            pc = CONF[k].loc[prev_conf_bucket[k]]
        prev_conf_bucket[k] = cb
        conf_done[k] = pc

    if armed is not None and all(conf_done[k] is not None for k in D):
        side = armed["side"]
        if (t - armed["t"]).total_seconds() > ARM_TIMEOUT_MIN * 60 or eod(t):
            armed = None
        else:
            cES, cNQ = conf_done["ES"], conf_done["NQ"]
            def bearish(c): return c["close"] < c["open"]
            def bullish(c): return c["close"] > c["open"]
            ok = (bearish(cES) and bearish(cNQ)) if side == "bear" else (bullish(cES) and bullish(cNQ))
            # invalidation: confirmation candle closed through the EQ of the hit asset
            ha = armed["hit_asset"]
            ch = conf_done[ha]
            dead = (ch["close"] > armed["hit_level"]) if side == "bear" else (ch["close"] < armed["hit_level"])
            if dead:
                armed = None
            elif ok:
                if open_trade is not None and ONE_AT_A_TIME:
                    skipped += 1
                else:
                    legs = {}
                    for k in D:
                        ent = conf_done[k]["close"]
                        stop = armed["anchors"][k]
                        tp = ent - TP_PTS[k] if side == "bear" else ent + TP_PTS[k]
                        legs[k] = dict(entry=ent, stop=stop, init_stop=stop, tp=tp,
                                       be=False, ref=None, be_t=None,
                                       exit=None, exit_t=None, reason=None)
                    open_trade = dict(side=side, t=t, date=t.date(), legs=legs,
                                      hit_asset=armed["hit_asset"], hit_t=armed["t"])
                    for k in D:
                        prev_m5_bucket[k] = t.floor("5min")
                    signals.append(open_trade)
                armed = None

if open_trade is not None:
    for k in D:
        lg = open_trade["legs"][k]
        if lg["exit"] is None:
            lg["exit"] = rows[k]["close"].iloc[-1]; lg["exit_t"] = tl[-1]; lg["reason"] = "EOD"
    trades.append(open_trade)

# ---------- results ----------
recs = []
for tr in trades:
    for k in D:
        lg = tr["legs"][k]
        sgn = -1 if tr["side"] == "bear" else 1
        pts = sgn * (lg["exit"] - lg["entry"])
        recs.append(dict(date=tr["date"], entry_t=tr["t"], side=tr["side"], asset=k,
                         hit_asset=tr["hit_asset"], entry=lg["entry"], stop=lg["init_stop"],
                         tp=lg["tp"], exit=lg["exit"], exit_t=lg["exit_t"],
                         reason=lg["reason"], be=lg["be"],
                         stop_dist=abs(lg["entry"] - lg["init_stop"]),
                         pts=pts, R=pts / R_UNIT[k]))
res = pd.DataFrame(recs)
res.to_csv(f"{BASE}/trades_{CONF_TF}.csv", index=False)
print(f"CONF_TF={CONF_TF}  trades(pairs)={len(trades)}  skipped_overlap={skipped}  sl_tp_same_bar={sl_tp_same_bar}")
if len(res):
    for k in D:
        s = res[res.asset == k]
        print(f"  {k}: n={len(s)} TP={sum(s.reason=='TP')} SL={sum(s.reason=='SL')} "
              f"BE={sum(s.reason=='BE')} EOD={sum(s.reason=='EOD')} "
              f"totR={s.R.sum():+.2f} avgR={s.R.mean():+.3f}")
    print(f"  COMBINED totR={res.R.sum():+.2f}")
