# -*- coding: utf-8 -*-
"""
EQ-PYRAMIDE - ny variant, sep 2026.  Afklaret med traderen 18-09.

Forskel fra eq_model.py:
  GAMMEL: entry -> begge EQ'er ude af drift -> fast TP 15/75 -> haardt SL paa
          ankeret -> BE ved naermeste levende 5m-liq.
  NY:     entry -> EQ'erne KOERER VIDERE.
          * Den EQ der gav entry "bestemmer" i foerste omgang.
          * Bliver en ny EQ foedt, overtager DEN styringen. Altid den nyeste.
          * 15s-luk IGENNEM den styrende EQ  -> hele handlen ud. Der er INTET
            haardt stop paa prisen. Ankeret er kun EQ'ens udgangspunkt.
          * Rent raid paa den styrende EQ + faelles 15s-luk -> en kontrakt mere.
          * TP er samlet P/L, ikke en fast prisafstand.

Samlet TP (traderens eget eksempel, NQ):
  1 kontrakt, prisen gaar 30 pt -> 30 pt i bogen, mangler 45.
  2. entry -> 2 kontrakter -> der mangler 45/2 = 22,5 pt mere i pris.
      TP-pris = ( sum(entries) -+ TP_TOTAL ) / n

En EQ der er raidet er brugt op som TILFOEJELSES-trigger (used=True), men
bliver ved med at styre EXIT indtil en nyere EQ afloeser den. Det er den
eneste laesning der faar begge hans udsagn til at gaa op: entry-EQ'en var
selv raidet, og den bestemmer alligevel.
"""
import pandas as pd
import eq_model as EM

SYMS = EM.SYMS
TP_TOTAL = {"ES": 15.0, "NQ": 75.0}      # samlet P/L-maal i point (= 7,5 R)


def _tp_price(entries, k, side):
    n = len(entries); s = sum(entries)
    return (s - TP_TOTAL[k]) / n if side == "bear" else (s + TP_TOTAL[k]) / n


def _line(g, side, lo, hi):
    """Opdater EQ'ens ekstrem med denne bars low/high og returner linjen."""
    g["e"] = min(g["e"], lo) if side == "bear" else max(g["e"], hi)
    return (g["a"] + g["e"]) / 2.0


def run(conf_sec=15, entry_from=9*60+30, entry_to=10*60, sides=("bear",),
        max_conf_bars=4, max_stop={"ES": 8.0, "NQ": 40.0},
        max_contracts=5,          # traderen: "4-5, det vender vi tilbage til"
        add_needs_conf=True,      # tilfoejelse kraever ogsaa faelles 15s-luk
        use_be=False,             # BE er ude i denne version
        exit_scope="any",         # 'any' = luk igennem paa ET aktiv lukker begge ben
        add_scope="both",         # 'both' = tilfoejelsen laegges paa begge ben
        gov_delay="candle1m",     # hvornaar er en ny EQ "etableret"?
                                  #   'none'     = med det samme
                                  #   'candle1m' = foerst naar et 1m-lys har lukket
                                  #                i handlens retning EFTER foedslen
        gov_on="birth",           # hvornaar overtager en ny EQ styringen af exit?
                                  #   'birth' = saa snart den foedes (ordret laesning)
                                  #   'add'   = foerst naar den har givet en tilfoejelse
        ):
    C = EM._data(conf_sec)
    BAR, M1 = C["bar"], C["m1"]
    TOD, DAY, TL = C["tod"], C["day"], C["tl"]
    OPEN_MIN, CLOSE_MIN = EM.OPEN_MIN, EM.CLOSE_MIN

    eqs  = {k: {"bear": None, "bull": None} for k in SYMS}
    day  = {k: None for k in SYMS}
    pmin = {k: None for k in SYMS}
    pos = armed = addarm = None
    trades, log = [], []

    for ts in TL:
        tod, d = TOD[ts], DAY[ts]
        mb = ts // 60 * 60
        bars = {k: BAR[k].get(ts) for k in SYMS}
        newmin = {}
        for k in SYMS:
            if bars[k] is None:
                newmin[k] = None; continue
            newmin[k] = M1[k].get(pmin[k]) if (pmin[k] is not None and mb != pmin[k]) else None
            pmin[k] = mb
        in_sess = OPEN_MIN <= tod < CLOSE_MIN
        for k in SYMS:
            if bars[k] is not None and tod >= OPEN_MIN and day[k] != d:
                day[k] = d
                if pos is None:
                    eqs[k] = {"bear": None, "bull": None}; armed = None

        # =================== A. AABEN POSITION ===================
        if pos is not None:
            side = pos["side"]; short = side == "bear"
            add_hit = None
            for k in SYMS:
                bb = bars[k]
                if bb is None: continue
                o, h, l, c = bb
                # A0. en ventende EQ forfremmes naar et 1m-lys har lukket
                #     i handlens retning efter at den blev foedt
                pend = pos["pend"].get(k)
                if pend is not None:
                    pend["e"] = min(pend["e"], l) if short else max(pend["e"], h)
                    pv = newmin[k]
                    if pv is not None and ((pv[3] < pv[0]) if short else (pv[3] > pv[0])):
                        pos["gov"][k] = pend; pos["pend"][k] = None
                # A1a. kandidat-EQ forlaenges / raides (raid = trigger for tilfoejelse)
                if eqs[k][side] is not None:
                    a_, e0 = eqs[k][side]
                    e1 = min(e0, l) if short else max(e0, h)
                    lvl = (a_ + e1) / 2.0
                    if (h >= lvl) if short else (l <= lvl):
                        eqs[k][side] = None
                        rent = not ((c > lvl) if short else (c < lvl))
                        if rent and add_hit is None: add_hit = (k, a_, e1)
                    else:
                        eqs[k][side] = (a_, e1)
                # A1b. ny EQ foedes
                pm = newmin[k]
                if pm is not None and tod >= OPEN_MIN and eqs[k][side] is None:
                    po, ph, pl, pc = pm; mid = (ph + pl) / 2.0
                    if (pc < po and pc < mid) if short else (pc > po and pc > mid):
                        a_, e_ = (ph, min(pl, l)) if short else (pl, max(ph, h))
                        lvl = (a_ + e_) / 2.0
                        if (h >= lvl) if short else (l <= lvl):
                            if not ((c > lvl) if short else (c < lvl)) and add_hit is None:
                                add_hit = (k, a_, e_)
                        else:
                            eqs[k][side] = (a_, e_)
                        if gov_on == "birth":
                            if gov_delay == "none":
                                pos["gov"][k] = dict(a=a_, e=e_)
                            else:
                                pos["pend"][k] = dict(a=a_, e=e_)

            # A2. den styrende EQ's linje opdateres med denne bars ekstrem
            lines = {}
            for k in SYMS:
                if bars[k] is None: continue
                lines[k] = _line(pos["gov"][k], side, bars[k][2], bars[k][1])

            # A3. samlet TP - pr. ben
            for k in SYMS:
                if pos["exit"][k] is not None or bars[k] is None: continue
                tp = _tp_price(pos["entries"][k], k, side)
                if (bars[k][2] <= tp) if short else (bars[k][1] >= tp):
                    pos["exit"][k] = (tp, "TP", ts)

            # A4. 15s-luk IGENNEM den styrende EQ -> alle aabne ben ud
            gennem = [k for k in SYMS if k in lines and
                      ((bars[k][3] > lines[k]) if short else (bars[k][3] < lines[k]))]
            luk = (exit_scope == "any"
                   or (exit_scope in SYMS and exit_scope in gennem)
                   or (exit_scope == "hit" and pos["hit"] in gennem))
            if gennem and luk:
                for k in SYMS:
                    if pos["exit"][k] is None and bars[k] is not None:
                        pos["exit"][k] = (bars[k][3], "EQ-luk", ts)

            aabne = [k for k in SYMS if pos["exit"][k] is None]

            # A5. rent raid paa kandidat-EQ -> arm en tilfoejelse
            if aabne and addarm is None and add_hit is not None:
                addarm = dict(k=add_hit[0], a=add_hit[1], e=add_hit[2], seen=0)

            # A6. tilfoejelsen kraever faelles 15s-luk samme vej
            if aabne and addarm is not None and all(bars[k] is not None for k in SYMS):
                if addarm["seen"] >= max_conf_bars:
                    addarm = None
                else:
                    addarm["seen"] += 1
                    ok = all((bars[k][3] < bars[k][0]) if short else
                             (bars[k][3] > bars[k][0]) for k in SYMS)
                    if ok or not add_needs_conf:
                        mod = aabne if add_scope == "both" else \
                              ([addarm["k"]] if addarm["k"] in aabne else [])
                        lagt = [j for j in mod if len(pos["entries"][j]) < max_contracts]
                        for j in lagt: pos["entries"][j].append(bars[j][3])
                        if lagt:
                            pos["adds"].append(dict(ts=EM.fmt(ts), ben="+".join(lagt),
                                                    n=len(pos["entries"][lagt[0]]),
                                                    **{f"{j}_pris": bars[j][3] for j in lagt}))
                            # styringen flytter foerst NAAR tilfoejelsen er sket
                            if gov_on == "add":
                                pos["gov"][addarm["k"]] = dict(a=addarm["a"], e=addarm["e"])
                                for j in SYMS:
                                    if j != addarm["k"] and eqs[j][side] is not None:
                                        pos["gov"][j] = dict(a=eqs[j][side][0], e=eqs[j][side][1])
                        addarm = None

            if tod >= CLOSE_MIN:
                for k in SYMS:
                    if pos["exit"][k] is None and bars[k] is not None:
                        pos["exit"][k] = (bars[k][3], "EOD", ts)

            if all(pos["exit"][k] is not None for k in SYMS):
                rec = dict(dag=pos["day"], ind=pos["t0"], retning=side, trigger=pos["hit"],
                           ud=EM.fmt(max(pos["exit"][k][2] for k in SYMS)),
                           udfald="+".join(sorted({pos["exit"][k][1] for k in SYMS})))
                for k in SYMS:
                    ents = pos["entries"][k]; p, grund, _t = pos["exit"][k]
                    sgn = -1 if short else 1
                    pts = sum(sgn * (p - e) for e in ents)
                    rec[f"{k}_n"] = len(ents)
                    rec[f"{k}_snit"] = round(sum(ents) / len(ents), 4)
                    rec[f"{k}_exit"] = round(p, 4)
                    rec[f"{k}_udfald"] = grund
                    rec[f"{k}_pts"] = round(pts, 4)
                    rec[f"{k}_R"] = round(pts / EM.R_UNIT[k], 4)
                    rec[f"{k}_risiko"] = round(pos["risk0"][k], 4)
                    rec[f"{k}_rr"] = (round(pts / pos["risk0"][k], 2)
                                      if pos["risk0"][k] > 1e-9 else None)
                rec["adds"] = pos["adds"]
                trades.append(rec)
                pos = armed = addarm = None
                for k in SYMS: eqs[k] = {"bear": None, "bull": None}
            continue

        # =================== B. INGEN POSITION ===================
        raids = []
        # oejebliksbillede FOER barens raids. Uden det forsvinder konfluensen
        # naar begge aktiver raider paa samme bar: partnerens EQ er da allerede
        # sat til None naar den skal aflaeses. Samme greb som eq_model._run.
        pre = {"bear": {k: eqs[k]["bear"] for k in SYMS},
               "bull": {k: eqs[k]["bull"] for k in SYMS}}
        made = {"bear": {}, "bull": {}}
        for k in SYMS:
            b = bars[k]
            if b is None or not in_sess: continue
            o, h, l, c = b
            for side in ("bear", "bull"):
                if eqs[k][side] is None: continue
                a, e0 = eqs[k][side]
                e1 = min(e0, l) if side == "bear" else max(e0, h)
                lvl = (a + e1) / 2.0
                if (h >= lvl) if side == "bear" else (l <= lvl):
                    through = (c > lvl) if side == "bear" else (c < lvl)
                    raids.append((k, side, lvl, a, e1, through)); eqs[k][side] = None
                else:
                    eqs[k][side] = (a, e1)
            pm = newmin[k]
            if pm is not None and tod >= OPEN_MIN:
                po, ph, pl, pc = pm; mid = (ph + pl) / 2.0
                if pc < po and pc < mid and eqs[k]["bear"] is None:
                    a, e = ph, min(pl, l); lvl = (a + e) / 2.0
                    made["bear"][k] = (a, e)
                    if h >= lvl: raids.append((k, "bear", lvl, a, e, c > lvl))
                    else: eqs[k]["bear"] = (a, e)
                if pc > po and pc > mid and eqs[k]["bull"] is None:
                    a, e = pl, max(ph, h); lvl = (a + e) / 2.0
                    made["bull"][k] = (a, e)
                    if l <= lvl: raids.append((k, "bull", lvl, a, e, c < lvl))
                    else: eqs[k]["bull"] = (a, e)

        can_enter = entry_from <= tod < entry_to
        for (k, side, lvl, anch, ext, through) in raids:
            if not can_enter: break
            if side not in sides or through: continue
            other = "NQ" if k == "ES" else "ES"
            # en EQ foedt paa DENNE bar vinder over en der allerede var doed ved
            # barens start - samme raekkefoelge som Pine og som eq_model.
            oth = made[side].get(other, pre[side][other])
            if oth is None: continue
            armed = dict(side=side, hit=k, ts=ts, seen=0,
                         anchors={k: anch, other: oth[0]},
                         levels={k: lvl, other: (oth[0] + oth[1]) / 2.0},
                         gov={k: dict(a=anch, e=ext, used=True, t=EM.fmt(ts)),
                              other: dict(a=oth[0], e=oth[1], used=False, t=EM.fmt(ts))})

        if armed and all(bars[k] is not None for k in SYMS):
            side = armed["side"]
            if armed["seen"] >= max_conf_bars or not can_enter:
                armed = None
            else:
                armed["seen"] += 1
                dead = any((bars[k][3] > armed["levels"][k]) if side == "bear"
                           else (bars[k][3] < armed["levels"][k]) for k in SYMS)
                ok = all((bars[k][3] < bars[k][0]) if side == "bear"
                         else (bars[k][3] > bars[k][0]) for k in SYMS)
                if dead:
                    armed = None
                elif ok:
                    bad = [k for k in SYMS if max_stop and k in max_stop and
                           abs(bars[k][3] - armed["anchors"][k]) > max_stop[k]]
                    if bad:
                        log.append(dict(ts=EM.fmt(ts), status="8/40 kasserede", ben=",".join(bad)))
                        armed = None
                    else:
                        pos = dict(side=side, day=d, t0=EM.fmt(ts), hit=armed["hit"],
                                   gov=armed["gov"], adds=[],
                                   risk0={k: abs(bars[k][3] -
                                          (armed["gov"][k]["a"] + armed["gov"][k]["e"]) / 2.0)
                                          for k in SYMS},
                                   exit={k: None for k in SYMS},
                                   pend={k: None for k in SYMS},
                                   entries={k: [bars[k][3]] for k in SYMS})
                        armed = None
    return pd.DataFrame(trades), pd.DataFrame(log)
