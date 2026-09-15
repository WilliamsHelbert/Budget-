"""
Dual-asset (ES + NQ) EQ-confluence backtest.

EQ engine = faithful port of "EQ - Equilibrium Tracker v10":
  bear EQ  <- 1m candle closing bearish AND below its own (H+L)/2 ; anchor = its high
  bull EQ  <- 1m candle closing bullish AND above its own (H+L)/2 ; anchor = its low
  grows on the 15s chart toward new extremes, EQ line = (anchor + extreme)/2
  freezes ("used") on the first 15s close where price reaches the EQ line
  everything wiped at 15:30 CPH (09:30 NY)

Trade model:
  1. both assets hold an ACTIVE EQ in the SAME direction
  2. one asset REACHES its EQ line without closing through it   -> setup armed
  3. wait for a confirmation close where BOTH assets close the same way
     (both bearish -> SHORT, both bullish -> LONG)
  4. enter both legs at that close; SL = own EQ anchor, TP = 15 ES / 75 NQ
  5. stop -> breakeven on the first 5m liquidity sweep after entry
"""
import pandas as pd, os

TZ = "Europe/Copenhagen"
OPEN_MIN, CLOSE_MIN = 15*60+30, 22*60
R_UNIT = {"ES": 2.0, "NQ": 10.0}     # 15 pts ES = 75 pts NQ = 7.5R
TP_PTS = {"ES": 15.0, "NQ": 75.0}
SYMS = ("ES", "NQ")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prep(sym):
    df = pd.read_parquet(f"{BASE}/{sym}.parquet")
    t = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    secs = t.dt.tz_convert("UTC").dt.tz_localize(None).astype("datetime64[s]").astype("int64")
    return df.assign(ts=secs, tod=t.dt.hour*60+t.dt.minute,
                     day=t.dt.strftime("%Y-%m-%d")).sort_values("ts").reset_index(drop=True)


def _buckets(df, sec):
    g = df.groupby((df["ts"] // sec) * sec)
    o = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(),
                      "l": g["low"].min(), "c": g["close"].last()})
    return {int(k): (float(a), float(b), float(c), float(d))
            for k, a, b, c, d in zip(o.index, o.o, o.h, o.l, o.c)}


def _fine():
    """5s-barer pr. symbol hvor de findes. Bruges til at afgoere raids praecist
    i stedet for at gaette rakkefoelgen inde i 15s-baren."""
    if "fine" in _CACHE: return _CACHE["fine"]
    out = {}
    for k in SYMS:
        f = f"{BASE}/{k}5s.parquet"
        if os.path.exists(f):
            d = pd.read_parquet(f)
            out[k] = {int(t): (float(o), float(h), float(l), float(c))
                      for t, o, h, l, c in zip(d.ts, d.open, d.high, d.low, d.close)}
        else:
            out[k] = {}
    _CACHE["fine"] = out
    return out


_CACHE = {}
def _data(conf_sec):
    if "df" not in _CACHE:
        _CACHE["df"] = {k: _prep(k) for k in SYMS}
        d = _CACHE["df"]
        _CACHE["bar"] = {k: {int(t): (float(a), float(b), float(c), float(e)) for t, a, b, c, e in
                             zip(d[k].ts, d[k].open, d[k].high, d[k].low, d[k].close)} for k in SYMS}
        _CACHE["m1"] = {k: _buckets(d[k], 60) for k in SYMS}
        _CACHE["m5"] = {k: _buckets(d[k], 300) for k in SYMS}
        _CACHE["tod"] = {}; _CACHE["day"] = {}
        for k in SYMS:
            for t, td, dd in zip(d[k].ts, d[k].tod, d[k].day):
                _CACHE["tod"][int(t)] = int(td); _CACHE["day"][int(t)] = dd
        _CACHE["tl"] = sorted(set(map(int, d["ES"].ts)) | set(map(int, d["NQ"].ts)))
    key = f"conf{conf_sec}"
    if key not in _CACHE:
        _CACHE[key] = {k: _buckets(_CACHE["df"][k], conf_sec) for k in SYMS}
    return _CACHE


def fmt(ts):
    return pd.Timestamp(int(ts), unit="s", tz="UTC").tz_convert(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _be_level(m5, bucket, short, back=8):
    """GAMMEL regel (forkert): extremet paa det senest afsluttede 5m-lys.
    Beholdt bag be_src='prev5' saa gamle koersler kan reproduceres."""
    for i in range(1, back+1):
        c = m5.get(bucket - 300*i)
        if c: return c[2] if short else c[1]
    return None


def _nearest_liq(lvls, ent, short):
    """Naermeste UROERTE 5m-likviditetsniveau i gevinstretningen paa entry-tidspunktet.
    lvls = liste af dicts {lvl, hi, dead}. Short -> lows under entry. Long -> highs over entry."""
    best = None
    for m in lvls:
        if m["dead"] or m["hi"] == short: continue
        v = m["lvl"]
        if (v >= ent) if short else (v <= ent): continue
        if best is None:
            best = v
        elif (v > best) if short else (v < best):
            best = v
    return best


def _tp(k, ent, stop, mode, r):
    return TP_PTS[k] if mode == "fixed" else abs(ent-stop)*r


def run(*a, **kw):
    r = _run(*a, **kw)
    return r[:3]


def run_full(*a, **kw):
    return _run(*a, **kw)


def _run(conf_sec=60, entry_mode="loose", be_mode="liq5", sl_mode="anchor",
        arm_timeout_min=30, max_conf_bars=4, one_at_a_time=True, oaat_leg=None, per_leg=False,
        stop_after_decisive=False,
        entry_from=15*60+30, entry_to=16*60, flat_at=None,
        tp_mode="fixed", tp_r=3.0, max_stop=None, invert=False,
        daily_stop=None, daily_target=None, daily_basis="sum",
        max_be=None, be_ref="next", be_min=None, conf_now=False,
        be_src="prev5", liq_piv=0, liq_from=None,
        tp_sess=None, tp_sess_cap=False, tp_m15=None,
        daily_tp=None, daily_tp_floor=True, birth_raid="ext", raid_ref="order", force_clean=None,
        sides=None):
    """daily_stop / daily_target: stop trading for the day once realised R for that
       session is <= daily_stop or >= daily_target. daily_basis 'sum' counts both legs
       added together; 'avg' treats the pair as one position (mean of the two legs)."""
    """entry_from/entry_to : minutes-of-day (CPH) in which a NEW entry may be taken.
       flat_at : force-flat minute-of-day; None = hold to RTH close."""
    FLAT = flat_at if flat_at is not None else CLOSE_MIN
    C = _data(conf_sec)
    SL = MC = None
    if tp_sess is not None:
        import sessions as _ss
        SL = _ss.build(conf_sec)
    if tp_m15 is not None:
        import sessions as _ss
        MC = _ss.build_m15(conf_sec)
    BAR, M1, M5, CONF = C["bar"], C["m1"], C["m5"], C[f"conf{conf_sec}"]
    TOD, DAY, TL, DF = C["tod"], C["day"], C["tl"], C["df"]
    ARM_TO = arm_timeout_min * 60

    FINE = _fine() if raid_ref in ("order", "fine") else {k: {} for k in SYMS}

    decided = {}
    def _touch(k, ts, side, a, e0, o, h, l, c):
        """Ramte baren EQ-linjen? Bruger 5s-underbarer hvis de findes, ellers
        rakkefoelge-heuristikken. Returnerer (ramt, linje ved barens slutning)."""
        e1 = min(e0, l) if side == "bear" else max(e0, h)
        lvl = (a+e1)/2.0
        sub = [FINE[k].get(ts), FINE[k].get(ts+5), FINE[k].get(ts+10)]
        if all(x is not None for x in sub):
            decided[(k, side)] = "5s"
            e = e0
            for (so, sh, sl, sc) in sub:
                if side == "bear":
                    e = min(e, sl)
                    if sh >= (a+e)/2.0: return True, lvl
                else:
                    e = max(e, sh)
                    if sl <= (a+e)/2.0: return True, lvl
            return False, lvl
        pre = (h >= (a+e0)/2.0) if side == "bear" else (l <= (a+e0)/2.0)
        ext = (h >= lvl) if side == "bear" else (l <= lvl)
        decided[(k, side)] = "15s klar" if pre or not ext else "15s formregel"
        if raid_ref == "pre": return pre, lvl
        if raid_ref == "ext": return ext, lvl
        return pre or (ext and (c > o if side == "bear" else c < o)), lvl

    bear = {k: None for k in SYMS}; bull = {k: None for k in SYMS}
    day  = {k: None for k in SYMS}
    pmin = {k: None for k in SYMS}; pconf = {k: None for k in SYMS}
    FC = force_clean or set()
    trades = []; armed = None; live = []; audit = []
    # --- 5m likviditetsniveauer (be_src='liq') ---
    LV   = {k: [] for k in SYMS}    # levende/doede niveauer for dagen
    P5   = {k: [] for k in SYMS}    # afsluttede 5m-lys for dagen (bucket,o,h,l,c)
    LVB  = {k: None for k in SYMS}  # sidst sete 5m-bucket
    LVD  = {k: None for k in SYMS}  # sidst sete dag
    LVFROM = OPEN_MIN if liq_from is None else liq_from
    dayRk = {}   # (dag, asset) -> R for det ben alene
    decided = {}  # (dag, asset) -> True naar en IKKE-BE handel er lukket for det ben den dag
    dayR = {}; siglog = []
    stat = dict(eq=0, hit_clean=0, hit_over=0, armed=0, signals=0, skipped=0,
                both_hit=0, arm_expired=0, arm_dead=0, birth_hit=0)

    for ts in TL:
        tod = TOD[ts]; d = DAY[ts]
        mb, cb, m5b = ts//60*60, ts//conf_sec*conf_sec, ts//300*300
        bars = {k: BAR[k].get(ts) for k in SYMS}

        newmin = {}
        for k in SYMS:
            if bars[k] is None: newmin[k] = None; continue
            newmin[k] = M1[k].get(pmin[k]) if (pmin[k] is not None and mb != pmin[k]) else None
            pmin[k] = mb

        if be_src == "liq":
            for k in SYMS:
                b = bars[k]
                if b is None: continue
                if LVD[k] != d:
                    LVD[k] = d; LV[k] = []; P5[k] = []; LVB[k] = None
                # nyt 5m-lys afsluttet?
                if LVB[k] is not None and m5b != LVB[k]:
                    c5 = M5[k].get(LVB[k])
                    if c5 and TOD.get(LVB[k], LVFROM) >= LVFROM:
                        P5[k].append((LVB[k],) + c5)
                        n = len(P5[k])
                        if liq_piv <= 0:
                            _, _o, _h, _l, _c = P5[k][-1]
                            LV[k].append(dict(lvl=_h, hi=True,  dead=False))
                            LV[k].append(dict(lvl=_l, hi=False, dead=False))
                        elif n >= 3:
                            a_, b_, c_ = P5[k][-3], P5[k][-2], P5[k][-1]
                            if b_[3] < a_[3] and b_[3] < c_[3]:
                                LV[k].append(dict(lvl=b_[3], hi=False, dead=False))
                            if b_[2] > a_[2] and b_[2] > c_[2]:
                                LV[k].append(dict(lvl=b_[2], hi=True,  dead=False))
                LVB[k] = m5b
                # doed hvis prisen har vaeret igennem
                o_, h_, l_, c_ = b
                for m in LV[k]:
                    if not m["dead"] and ((h_ >= m["lvl"]) if m["hi"] else (l_ <= m["lvl"])):
                        m["dead"] = True

        in_sess = OPEN_MIN <= tod < CLOSE_MIN
        can_enter = entry_from <= tod < entry_to
        pre = {"bear": dict(bear), "bull": dict(bull)}
        made = {"bear": {}, "bull": {}}
        hits = []; reset = False
        for k in SYMS:
            b = bars[k]
            if b is None or not in_sess: continue
            o, h, l, c = b
            if tod >= OPEN_MIN and day[k] != d:
                day[k] = d; bear[k] = bull[k] = None; reset = True
            # raid_ref 'ext' = linjen efter denne bars egen forlaengelse (som indikatoren)
            # raid_ref 'pre' = linjen FOER, saa baren ikke kan traekke linjen hen til sig
            #                  selv. Kausal: uafhaengig af rakkefoelgen inde i baren.
            if bear[k]:
                a, e0 = bear[k]
                got, lvl = _touch(k, ts, "bear", a, e0, o, h, l, c)
                if got: hits.append((k, "bear", lvl, a, (c > lvl) and (ts,k,"bear") not in FC)); bear[k] = None
                else: bear[k] = (a, min(e0, l))
            if bull[k]:
                a, e0 = bull[k]
                got, lvl = _touch(k, ts, "bull", a, e0, o, h, l, c)
                if got: hits.append((k, "bull", lvl, a, (c < lvl) and (ts,k,"bull") not in FC)); bull[k] = None
                else: bull[k] = (a, max(e0, h))
            pm = newmin[k]
            if pm is not None and tod >= OPEN_MIN:
                po, ph, pl, pc = pm; eq1 = (ph+pl)/2.0
                # Baren der foeder EQ'en er selv en 15s-bar og behandles som enhver
                # anden bar: den kan baade raide EQ'en rent og lukke igennem den.
                #   birth_raid 'off'    : foedselsbaren testes slet ikke (gammel adfaerd)
                #   birth_raid 'ext'    : linje = (anker + extreme inkl. denne bar)/2
                #   birth_raid 'strict' : linje = 1m-candlens egen midt, saa baren ikke
                #                         kan flytte linjen ned/op til sig selv
                if pc < po and pc < eq1 and bear[k] is None:
                    a, e = ph, min(pl, l); stat["eq"] += 1
                    made["bear"][k] = (a, e)
                    got, lvl = _touch(k, ts, "bear", a, pl, o, h, l, c)
                    if birth_raid != "off" and got:
                        stat["birth_hit"] += 1
                        hits.append((k, "bear", lvl, a, (c > lvl) and (ts,k,"bear") not in FC))
                    else: bear[k] = (a, e)
                if pc > po and pc > eq1 and bull[k] is None:
                    a, e = pl, max(ph, h); stat["eq"] += 1
                    made["bull"][k] = (a, e)
                    got, lvl = _touch(k, ts, "bull", a, ph, o, h, l, c)
                    if birth_raid != "off" and got:
                        stat["birth_hit"] += 1
                        hits.append((k, "bull", lvl, a, (c < lvl) and (ts,k,"bull") not in FC))
                    else: bull[k] = (a, e)
        if reset:
            if armed is not None and armed["rec"]["status"] == "armeret":
                armed["rec"]["status"] = "9. dagen nulstillede"
            armed = None

        # ---- manage open positions ----
        still = []
        for tr in live:
            short = tr["side"] == "bear"
            for k in tr["legs"]:
                lg = tr["legs"][k]
                if lg["exit"] is not None: continue
                b = bars[k]
                if (be_src != "liq") and lg["m5"] is not None and m5b != lg["m5"] and not lg["be"]:
                    c5 = M5[k].get(lg["m5"])
                    if c5:
                        if be_mode == "liq5":
                            cand = c5[2] if short else c5[1]
                            mind = 0.0 if be_min is None else be_min[k]
                            # afstanden skal vaere POSITIV: niveauet skal ligge i gevinstretningen.
                            # Er det allerede taget ud, er der ingen likviditet tilbage at hente.
                            dist = (lg["entry"] - cand) if short else (cand - lg["entry"])
                            if dist >= mind:
                                lg["ref"] = cand
                        elif be_mode == "close5":
                            if (c5[3] < lg["entry"]) if short else (c5[3] > lg["entry"]):
                                lg["be"] = True; lg["stop"] = lg["entry"]; lg["be_t"] = ts
                if b is not None: lg["m5"] = m5b
                if b is None: continue
                o, h, l, c = b
                sl = (h >= lg["stop"]) if short else (l <= lg["stop"])
                tp = (l <= lg["tp"])   if short else (h >= lg["tp"])
                if sl and tp: stat["both_hit"] += 1
                if sl:   lg.update(exit=lg["stop"], exit_t=ts, reason="BE" if lg["be"] else "SL")
                elif tp: lg.update(exit=lg["tp"],   exit_t=ts, reason="TP")
                else:
                    if be_mode == "liq5" and not lg["be"] and lg["ref"] is not None:
                        if (l < lg["ref"]) if short else (h > lg["ref"]):
                            lg["be"] = True; lg["stop"] = lg["entry"]; lg["be_t"] = ts
                    if tod >= FLAT: lg.update(exit=c, exit_t=ts, reason="EOD")
            if all(tr["legs"][k]["exit"] is not None for k in tr["legs"]):
                sgn = -1 if tr["side"] == "bear" else 1
                for k in tr["legs"]:
                    lg = tr["legs"][k]
                    dayRk[(tr["day"], k)] = dayRk.get((tr["day"], k), 0.0) + \
                        sgn*(lg["exit"]-lg["entry"])/R_UNIT[k]
                    if stop_after_decisive and lg["reason"] != "BE":
                        decided[(tr["day"], k)] = True
                legR = [sgn*(tr["legs"][k]["exit"]-tr["legs"][k]["entry"])/R_UNIT[k]
                        for k in tr["legs"]]
                if daily_basis in SYMS and daily_basis in tr["legs"]:
                    got = legR[list(tr["legs"]).index(daily_basis)]
                else:
                    got = sum(legR) if daily_basis == "sum" else sum(legR)/len(legR)
                dayR[tr["day"]] = dayR.get(tr["day"], 0.0) + got
                trades.append(tr)
            else: still.append(tr)
        live = still

        # ---- arm ----
        for (k, side, lvl, anch, over) in hits:
            if not can_enter: break
            if sides is not None and side not in sides: continue
            stat["hit_over" if over else "hit_clean"] += 1
            _c = bars[k][3]
            arec = dict(tid=fmt(ts), dag=d, asset=k, retning="SHORT" if side == "bear" else "LONG",
                        eq_linje=round(lvl, 4), eq_anker=anch, raid_luk=_c,
                        luk_forbi=round((_c - lvl) if side == "bear" else (lvl - _c), 4),
                        afgjort=decided.get((k, side), "-"), status="")
            audit.append(arec)
            if over:
                arec["status"] = "1. raid lukkede igennem EQ-linjen"
                continue
            other = "NQ" if k == "ES" else "ES"
            p = pre[side]
            # en EQ foedt paa DENNE bar vinder over en der allerede var doed
            # ved barens start - samme raekkefoelge som Pine
            own = made[side].get(k, p[k])
            oth = made[side].get(other, p[other])
            if own is None or oth is None:
                arec["status"] = f"2. {other} havde ingen aktiv EQ samme vej"
                continue
            sweep = bars[k][1] if side == "bear" else bars[k][2]   # raid bar's extreme
            oa, oe = oth
            if armed is not None and armed["rec"]["status"] == "armeret":
                armed["rec"]["status"] = "8. erstattet af et nyere raid"
            arec["status"] = "armeret"
            armed = dict(rec=arec, side=side, ts=ts, hit=k, lvl=lvl, seen=0,
                         anchors={k: anch, other: oa},
                         levels={k: lvl, other: (oa+oe)/2.0},
                         sweeps={k: sweep, other: oa})
            stat["armed"] += 1

        # ---- confirmation close ----
        conf = {}
        for k in SYMS:
            if bars[k] is None: conf[k] = None; continue
            if conf_now:
                conf[k] = bars[k]
            else:
                conf[k] = CONF[k].get(pconf[k]) if (pconf[k] is not None and cb != pconf[k]) else None
            pconf[k] = cb

        if armed and conf["ES"] is not None and conf["NQ"] is not None:
            side = armed["side"]
            if armed["seen"] >= max_conf_bars or not can_enter:
                armed["rec"]["status"] = ("3. ingen faelles luk inden for %d barer" % max_conf_bars
                                          if can_enter else "3. vinduet lukkede")
                armed = None; stat["arm_expired"] += 1
            else:
                armed["seen"] += 1
                dead = any((conf[k][3] > armed["levels"][k]) if side == "bear"
                           else (conf[k][3] < armed["levels"][k]) for k in SYMS)
                ok = all(conf[k][3] < conf[k][0] for k in SYMS) if side == "bear" \
                     else all(conf[k][3] > conf[k][0] for k in SYMS)
                if dead:
                    armed["rec"]["status"] = "4. en af dem lukkede igennem sin EQ efter raidet"
                    armed = None; stat["arm_dead"] += 1
                elif ok:
                    stat["signals"] += 1
                    dr = dayR.get(d, 0.0)
                    if per_leg:
                        frie = []
                        for _k in SYMS:
                            if stop_after_decisive:
                                if decided.get((d, _k)): continue
                            else:
                                _r = dayRk.get((d, _k), 0.0)
                                if daily_stop is not None and _r <= daily_stop: continue
                                if daily_target is not None and _r >= daily_target: continue
                            if one_at_a_time and any(_k in t["legs"] and
                                    t["legs"][_k]["exit"] is None for t in live): continue
                            frie.append(_k)
                        halted = not frie
                    else:
                        frie = list(SYMS)
                        halted = ((daily_stop is not None and dr <= daily_stop) or
                                  (daily_target is not None and dr >= daily_target))
                    if halted:
                        stat["halted"] = stat.get("halted", 0) + 1
                        armed["rec"]["status"] = f"6. dagsgraense naaet (dagens R = {dr:+.2f})"
                        siglog.append(dict(ts=ts, side=side, hit=armed["hit"], status="dagsgraense naaet",
                                           why=f"dagens R = {dr:+.2f}"))
                    elif (not per_leg) and one_at_a_time and (
                            [t for t in live if oaat_leg in t["legs"]
                             and t["legs"][oaat_leg]["exit"] is None]
                            if oaat_leg else live):
                        stat["skipped"] += 1
                        armed["rec"]["status"] = "7. en position var allerede aaben"
                        siglog.append(dict(ts=ts, side=side, hit=armed["hit"], status="position aaben",
                                           why="et trade koerte allerede"))
                    else:
                        short = side == "bear"
                        cand = {}
                        for k in frie:
                            ent = conf[k][3]
                            stop = (armed["anchors"][k] if sl_mode == "anchor"
                                    else armed["levels"][k] if sl_mode == "eqline"
                                    else armed["sweeps"][k])
                            ref0 = (_nearest_liq(LV[k], ent, short) if be_src == "liq"
                                    else _be_level(M5[k], m5b, short))
                            bed = None if ref0 is None else (ent - ref0 if short else ref0 - ent)
                            cand[k] = (ent, stop, ref0, bed)
                        why = []
                        if max_stop is not None:
                            for k in frie:
                                if k in max_stop and abs(cand[k][0]-cand[k][1]) > max_stop[k]:
                                    why.append(f"stop>{max_stop[k]} ({k})")
                        if max_be is not None:
                            # loftet handler om at BE ikke maa ligge for LANGT vaek. Ligger
                            # niveauet allerede paa den anden side af entry (negativ afstand),
                            # er der intet at kappe - handlen gaar igennem, og BE venter blot
                            # paa naeste 5m-candle.
                            for k in frie:
                                if k not in max_be: continue
                                bd = cand[k][3]
                                if bd is None: why.append(f"intet 5m-niveau ({k})")
                                elif bd > max_be[k]: why.append(f"BE>{max_be[k]} ({k})")
                        if why:
                            armed["rec"]["status"] = "5. kasseret af lofterne: " + "; ".join(why)
                            armed["rec"].update(
                                **{f"{k}_entry": cand[k][0] for k in frie},
                                **{f"{k}_stopafst": abs(cand[k][0]-cand[k][1]) for k in frie},
                                **{f"{k}_beafst": cand[k][3] for k in frie})
                            stat["filtered"] = stat.get("filtered", 0) + 1
                            siglog.append(dict(ts=ts, side=side, hit=armed["hit"], status="filtreret fra",
                                               why="; ".join(why), **{f"{k}_{f}": v for k in frie
                                               for f, v in zip(("entry","stop","beref","bedist"), cand[k])}))
                            armed = None; continue
                        armed["rec"]["status"] = "TAGET"
                        armed["rec"].update(entry_tid=fmt(ts), ben="+".join(frie),
                                            **{f"{k}_entry": cand[k][0] for k in frie},
                                            **{f"{k}_stopafst": abs(cand[k][0]-cand[k][1]) for k in frie},
                                            **{f"{k}_beafst": cand[k][3] for k in frie})
                        siglog.append(dict(ts=ts, side=side, hit=armed["hit"], status="TAGET", why="",
                                           **{f"{k}_{f}": v for k in frie
                                              for f, v in zip(("entry","stop","beref","bedist"), cand[k])}))
                        legs = {}
                        for k in frie:
                            ent, stop, ref0, _ = cand[k]
                            sesslvl = None
                            if tp_m15 is not None:
                                import sessions as _ss
                                sesslvl = _ss.target_m15(MC, k, d, ent, side == "bear",
                                                         tp_m15[k], TP_PTS[k])
                            if sesslvl is None and tp_sess is not None:
                                import sessions as _ss
                                sesslvl, _nm = _ss.target(SL, k, d, ts, ent, side == "bear",
                                                          tp_sess[k],
                                                          TP_PTS[k] if tp_sess_cap else None)
                            if sesslvl is not None:
                                dist = abs(ent - sesslvl)
                            elif daily_tp:
                                need = (daily_target if daily_target is not None else 7.5) - dayR.get(d, 0.0)
                                need = need if daily_tp == "leg" else need/2.0
                                if daily_tp_floor: need = max(need, TP_PTS[k]/R_UNIT[k])
                                dist = max(need, 0.25) * R_UNIT[k]
                            else:
                                dist = _tp(k, ent, stop, tp_mode, tp_r)
                            legs[k] = dict(entry=ent, stop=stop, init_stop=stop,
                                           tp=(ent-dist) if side == "bear" else (ent+dist),
                                           be=False, be_t=None, m5=m5b,
                                           ref=(ref0 if ((be_src == "liq" or be_ref == "prev")
                                                and ref0 is not None
                                                and cand[k][3] is not None
                                                and cand[k][3] >= (0.0 if be_min is None
                                                                   else be_min.get(k, 0.0)))
                                                else None),
                                           exit=None, exit_t=None, reason=None)
                        if invert:
                            for k in legs:
                                lg = legs[k]; e = lg["entry"]
                                lg["stop"] = lg["init_stop"] = 2*e - lg["init_stop"]
                                lg["tp"] = 2*e - lg["tp"]
                            side = "bull" if side == "bear" else "bear"
                        live.append(dict(side=side, ts=ts, day=d, legs=legs,
                                         hit=armed["hit"], hit_ts=armed["ts"]))
                    armed = None
                elif entry_mode == "strict" and armed["seen"] >= 1:
                    armed = None; stat["arm_dead"] += 1
                elif armed["seen"] >= max_conf_bars:
                    armed = None; stat["arm_expired"] += 1

    for tr in live:
        for k in tr["legs"]:
            lg = tr["legs"][k]
            if lg["exit"] is None:
                lg.update(exit=float(DF[k]["close"].iloc[-1]), exit_t=TL[-1], reason="EOD")
        trades.append(tr)
    trades.sort(key=lambda t: t["ts"])

    recs = []
    for i, tr in enumerate(trades, 1):
        for k in tr["legs"]:
            lg = tr["legs"][k]; sgn = -1 if tr["side"] == "bear" else 1
            pts = sgn*(lg["exit"]-lg["entry"])
            recs.append(dict(id=i, day=tr["day"], hit_t=fmt(tr["hit_ts"]), entry_t=fmt(tr["ts"]),
                             side="SHORT" if tr["side"] == "bear" else "LONG", asset=k,
                             trigger_asset=tr["hit"], entry=lg["entry"], stop=lg["init_stop"],
                             tp=lg["tp"], exit=round(lg["exit"], 4), exit_t=fmt(lg["exit_t"]),
                             reason=lg["reason"], moved_be=lg["be"],
                             be_t=fmt(lg["be_t"]) if lg["be_t"] else "",
                             stop_dist=round(abs(lg["entry"]-lg["init_stop"]), 2),
                             risk_R=round(abs(lg["entry"]-lg["init_stop"])/R_UNIT[k], 2),
                             pts=round(pts, 4), R=round(pts/R_UNIT[k], 4)))
    return pd.DataFrame(recs), stat, len(trades), pd.DataFrame(siglog), pd.DataFrame(audit)
