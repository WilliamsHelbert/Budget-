"""Session-likviditet: Asia / London / NY PRE highs og lows pr. dag pr. symbol.

Et niveau er LEVENDE indtil prisen tager det EFTER at sessionen er slut
- praecis som i Session Levels-scriptet, hvor linjen stopper der.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M

SESS = [("Asia", 2*60, 8*60), ("London", 8*60, 14*60), ("NY PRE", 14*60, 15*60+30)]


def build(conf_sec=15):
    """-> {sym: {day: [ (navn, 'hi'|'lo', niveau, doed_fra_ts) ]}}"""
    C = M._data(conf_sec)
    BAR, TL, TOD, DAY = C["bar"], C["tl"], C["tod"], C["day"]
    out = {k: {} for k in M.SYMS}
    for k in M.SYMS:
        # 1) find hvert sessions extremer pr. dag
        acc = {}
        for ts in TL:
            b = BAR[k].get(ts)
            if b is None: continue
            o, h, l, c = b; tod = TOD[ts]; d = DAY[ts]
            for name, a, z in SESS:
                if a <= tod < z:
                    key = (d, name)
                    if key not in acc: acc[key] = [h, l, z]
                    else:
                        acc[key][0] = max(acc[key][0], h)
                        acc[key][1] = min(acc[key][1], l)
        # 2) hvornaar blev niveauet taget efter sessionen sluttede?
        lev = {}
        for (d, name), (hi, lo, endmin) in acc.items():
            lev.setdefault(d, []).append([name, "hi", hi, None])
            lev.setdefault(d, []).append([name, "lo", lo, None])
        for ts in TL:
            b = BAR[k].get(ts)
            if b is None: continue
            o, h, l, c = b; tod = TOD[ts]; d = DAY[ts]
            for row in lev.get(d, []):
                name, side, level, dead = row
                endmin = dict((n, z) for n, a, z in SESS)[name]
                if tod < endmin or dead is not None: continue
                if (side == "hi" and h >= level) or (side == "lo" and l <= level):
                    row[3] = ts
        out[k] = lev
    return out


def target(levels, sym, day, ts, entry, short, min_dist, cap=None):
    """Naermeste LEVENDE session-niveau i gevinstretningen, mindst min_dist vaek.
       Returnerer (niveau, navn) eller (None, None)."""
    best = None
    for name, side, level, dead in levels[sym].get(day, []):
        if dead is not None and dead <= ts:      # allerede taget foer entry
            continue
        dist = (entry - level) if short else (level - entry)
        if dist < min_dist:                      # for taet paa - spring over
            continue
        if cap is not None and dist > cap:
            continue
        if best is None or dist < best[0]:
            best = (dist, level, f"{name} {'low' if side=='lo' else 'high'}")
    return (best[1], best[2]) if best else (None, None)


def build_m15(conf_sec=15, ny_from=14*60, ny_to=15*60+30):
    """De orange 15m-niveauer: hver 15m-candles high og low inde i NY PRE,
    som er UROERT paa BEGGE symboler naar NY PRE slutter. NY PRE's eget
    high/low springes over - de er allerede session-niveauer.
    -> {day: [(sym_levels_dict, side, doed_fra_ts)]}, niveau pr. symbol."""
    C = _C = M._data(conf_sec)
    BAR, TL, TOD, DAY = C["bar"], C["tl"], C["tod"], C["day"]
    m15 = {k: {} for k in M.SYMS}          # (day, bucket) -> [hi, lo]
    nyex = {k: {} for k in M.SYMS}         # day -> [hi, lo] for hele NY PRE
    for k in M.SYMS:
        for ts in TL:
            b = BAR[k].get(ts)
            if b is None: continue
            o, h, l, c = b; tod = TOD[ts]; d = DAY[ts]
            if not (ny_from <= tod < ny_to): continue
            key = (d, (tod - ny_from) // 15)
            if key not in m15[k]: m15[k][key] = [h, l]
            else:
                m15[k][key][0] = max(m15[k][key][0], h)
                m15[k][key][1] = min(m15[k][key][1], l)
            if d not in nyex[k]: nyex[k][d] = [h, l]
            else:
                nyex[k][d][0] = max(nyex[k][d][0], h)
                nyex[k][d][1] = min(nyex[k][d][1], l)
    # kandidater pr. dag: (bucket, side) -> niveau pr. symbol
    cand = {}
    for (d, bkt) in m15["ES"]:
        if (d, bkt) not in m15["NQ"]: continue
        for si, side in ((0, "hi"), (1, "lo")):
            lv = {k: m15[k][(d, bkt)][si] for k in M.SYMS}
            ex = {k: nyex[k][d][si] for k in M.SYMS}
            if any(abs(lv[k] - ex[k]) < 1e-9 for k in M.SYMS):   # = NY PRE-ekstremet
                continue
            cand.setdefault(d, []).append({"bkt": bkt, "side": side, "lvl": lv, "dead": None})
    # doed hvis taget paa ET af symbolerne mens NY PRE stadig koerer
    for ts in TL:
        tod = TOD[ts]; d = DAY[ts]
        if not (ny_from <= tod < ny_to): continue
        for c in cand.get(d, []):
            if c["dead"] is not None: continue
            born = ny_from + c["bkt"] * 15 + 15          # gyldig foerst naar candlen er lukket
            if tod < born: continue
            for k in M.SYMS:
                b = BAR[k].get(ts)
                if b is None: continue
                o, h, l, _c = b
                if (c["side"] == "hi" and h >= c["lvl"][k]) or (c["side"] == "lo" and l <= c["lvl"][k]):
                    c["dead"] = ts; break
    return {d: [c for c in v if c["dead"] is None] for d, v in cand.items()}


def target_m15(cand, sym, day, entry, short, min_dist, cap=None):
    best = None
    for c in cand.get(day, []):
        if (c["side"] == "lo") != short:      # shorts sigter mod lows, longs mod highs
            continue
        lvl = c["lvl"][sym]
        dist = (entry - lvl) if short else (lvl - entry)
        if dist < min_dist: continue
        if cap is not None and dist > cap: continue
        if best is None or dist < best[0]: best = (dist, lvl)
    return best[1] if best else None
