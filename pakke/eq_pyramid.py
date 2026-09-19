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


R_PR_DAG = 7.5          # dagens slutmaal i R
DAGSSTOP = -5.0         # naaes den, handles der ikke mere den dag


def _maal(k, dagR):
    """Samlet P/L-maal i point for DENNE handel.
    Normalt 75 NQ / 15 ES. Har man tabt tidligere paa dagen, forlaenges
    maalet med tabet, saa dagen stadig kan lukke paa +7,5 R:
        -2,5 R i bogen  ->  maal 7,5 + 2,5 = 10 R = 100 NQ-point
    Maalet bliver aldrig mindre end de normale 75/15."""
    return max(R_PR_DAG - dagR, R_PR_DAG) * EM.R_UNIT[k]


def _tp_price(entries, k, side, dagR=0.0):
    n = len(entries); s = sum(entries); m = _maal(k, dagR)
    return (s - m) / n if side == "bear" else (s + m) / n


def _line(g, side, lo, hi):
    """Opdater EQ'ens ekstrem med denne bars low/high og returner linjen."""
    g["e"] = min(g["e"], lo) if side == "bear" else max(g["e"], hi)
    return (g["a"] + g["e"]) / 2.0


def run(conf_sec=15, entry_from=15*60+30, entry_to=16*60, sides=("bear", "bull"),
        max_conf_bars=4,
        max_stop=None,            # 8/40 er UDE - stammer fra den gamle model.
                                  # EQ'en er saa stor som den er.
        max_contracts=5,          # traderen: "4-5, det vender vi tilbage til"
        hard_stop=True,           # haardt SL i bunden/toppen af EQ'en (ankeret)
        dagsstop=DAGSSTOP,        # None slaar dagsgraensen fra
        dyn_tp=True,              # forlaeng maalet med dagens tab
        add_needs_conf=True,      # tilfoejelse kraever ogsaa faelles 15s-luk
        use_be=False,             # BE er UDE - stammer ogsaa fra den gamle model
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
    # Entry-vinduet er i DANSK tid, ikke NY-tid. Bevist paa 27-03-2026, hvor
    # USA er paa sommertid og EU ikke er: journalens 15:39 og 15:57 svarer der
    # til 10:39 og 10:58 NY, og setuppene ligger praecis der.
    _t = pd.to_datetime(pd.Series(C["tl"]), unit="s", utc=True).dt.tz_convert("Europe/Copenhagen")
    CPH = dict(zip(C["tl"], (_t.dt.hour * 60 + _t.dt.minute).tolist()))
    TOD, DAY, TL = C["tod"], C["day"], C["tl"]
    OPEN_MIN, CLOSE_MIN = EM.OPEN_MIN, EM.CLOSE_MIN

    eqs  = {k: {"bear": None, "bull": None} for k in SYMS}
    day  = {k: None for k in SYMS}
    pmin = {k: None for k in SYMS}
    pos = armed = addarm = None
    trades, log = [], []
    dagR = {}

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
        # Der handles KUN NQ-kontrakten. ES er reference.
        # Den der sweepede sin EQ ("styrer") bestemmer exit; sweeper begge
        # samtidig, er det NQ. NQ bestemmer altid TP.
        if pos is not None:
            side = pos["side"]; short = side == "bear"
            st = pos["styrer"]
            add_hit = False

            for k in SYMS:
                bb = bars[k]
                if bb is None: continue
                o, h, l, c = bb
                # kandidat-EQ forlaenges / raides (raid paa styreren = tilfoejelse)
                if eqs[k][side] is not None:
                    a_, e0 = eqs[k][side]
                    e1 = min(e0, l) if short else max(e0, h)
                    lvl = (a_ + e1) / 2.0
                    if (h > lvl) if short else (l < lvl):
                        eqs[k][side] = None
                        if k == st and not ((c > lvl) if short else (c < lvl)):
                            add_hit = True
                    else:
                        eqs[k][side] = (a_, e1)
                # ny EQ foedes -> den nyeste overtager styringen
                pm = newmin[k]
                if pm is not None and tod >= OPEN_MIN and eqs[k][side] is None:
                    po, ph, pl, pc = pm; mid = (ph + pl) / 2.0
                    if (pc < po and pc < mid) if short else (pc > po and pc > mid):
                        a_, e_ = (ph, min(pl, l)) if short else (pl, max(ph, h))
                        lvl = (a_ + e_) / 2.0
                        if (h > lvl) if short else (l < lvl):
                            if k == st and not ((c > lvl) if short else (c < lvl)):
                                add_hit = True
                        else:
                            eqs[k][side] = (a_, e_)
                        if k == st:
                            pos["gov"] = dict(a=a_, e=e_)
                        if k == "NQ":
                            pos["nqgov"] = dict(a=a_, e=e_)

            # styrerens EQ-linje opdateres med denne bars ekstrem
            gb = bars[st]
            linje = _line(pos["gov"], side, gb[2], gb[1]) if gb is not None else None

            # A1. HAARDT SL. Paa NQ ligger det altid i NQ's EGEN EQ - toppen
            #     ved short, bunden ved long. Styrer ES, kan ES' anker ogsaa
            #     udloese, og saa lukkes NQ til markedspris.
            if hard_stop and pos["exit"] is None:
                nb = bars["NQ"]
                if nb is not None and ((nb[1] >= pos["nqgov"]["a"]) if short
                                       else (nb[2] <= pos["nqgov"]["a"])):
                    pos["exit"] = (pos["nqgov"]["a"], "SL", ts)
                elif (st == "ES" and gb is not None and nb is not None
                      and ((gb[1] >= pos["gov"]["a"]) if short
                           else (gb[2] <= pos["gov"]["a"]))):
                    pos["exit"] = (nb[3], "SL-ES", ts)

            # A2. samlet TP paa NQ
            if pos["exit"] is None and bars["NQ"] is not None:
                tp = _tp_price(pos["entries"], "NQ", side, pos["dagR0"] if dyn_tp else 0.0)
                if (bars["NQ"][2] <= tp) if short else (bars["NQ"][1] >= tp):
                    pos["exit"] = (tp, "TP", ts)

            # A3. 15s-luk IGENNEM styrerens EQ -> ud af NQ
            if pos["exit"] is None and gb is not None and linje is not None:
                if (gb[3] > linje) if short else (gb[3] < linje):
                    pos["exit"] = (bars["NQ"][3], "EQ-luk", ts)

            # A4. rent raid paa styrerens EQ -> arm en tilfoejelse
            if pos["exit"] is None and addarm is None and add_hit:
                addarm = dict(seen=0)

            # A5. tilfoejelsen kraever faelles 15s-luk samme vej
            if (pos["exit"] is None and addarm is not None
                    and all(bars[k] is not None for k in SYMS)):
                if addarm["seen"] >= max_conf_bars:
                    addarm = None
                else:
                    addarm["seen"] += 1
                    ok = all((bars[k][3] < bars[k][0]) if short else
                             (bars[k][3] > bars[k][0]) for k in SYMS)
                    if ok or not add_needs_conf:
                        if len(pos["entries"]) < max_contracts:
                            pos["entries"].append(bars["NQ"][3])
                            pos["adds"].append(dict(ts=EM.fmt(ts), n=len(pos["entries"]),
                                                    pris=bars["NQ"][3]))
                        addarm = None

            if pos["exit"] is None and tod >= CLOSE_MIN and bars["NQ"] is not None:
                pos["exit"] = (bars["NQ"][3], "EOD", ts)

            if pos["exit"] is not None:
                p, grund, xt = pos["exit"]
                sgn = -1 if short else 1
                pts = sum(sgn * (p - e) for e in pos["entries"])
                rec = dict(dag=pos["day"], ind=pos["t0"], ud=EM.fmt(xt), retning=side,
                           styrer=st, udfald=grund, n=len(pos["entries"]),
                           snit=round(sum(pos["entries"]) / len(pos["entries"]), 4),
                           exit=round(p, 4), pts=round(pts, 4),
                           R=round(pts / EM.R_UNIT["NQ"], 4),
                           risiko=round(pos["risk0"], 4),
                           rr=(round(pts / pos["risk0"], 2) if pos["risk0"] > 1e-9 else None),
                           adds=pos["adds"], dagR_foer=round(pos["dagR0"], 2),
                           maal_pt=round(_maal("NQ", pos["dagR0"] if dyn_tp else 0.0), 2))
                dagR[pos["day"]] = dagR.get(pos["day"], 0.0) + rec["R"]
                rec["dagR_efter"] = round(dagR[pos["day"]], 2)
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
                    if h > lvl: raids.append((k, "bear", lvl, a, e, c > lvl))
                    else: eqs[k]["bear"] = (a, e)
                if pc > po and pc > mid and eqs[k]["bull"] is None:
                    a, e = pl, max(ph, h); lvl = (a + e) / 2.0
                    made["bull"][k] = (a, e)
                    if l < lvl: raids.append((k, "bull", lvl, a, e, c < lvl))
                    else: eqs[k]["bull"] = (a, e)

        can_enter = entry_from <= CPH[ts] < entry_to
        for (k, side, lvl, anch, ext, through) in raids:
            if not can_enter: break
            if side not in sides or through: continue
            other = "NQ" if k == "ES" else "ES"
            # en EQ foedt paa DENNE bar vinder over en der allerede var doed ved
            # barens start - samme raekkefoelge som Pine og som eq_model.
            oth = made[side].get(other, pre[side][other])
            if oth is None: continue
            # Sweeper BEGGE samtidig, er det NQ der styrer exit. Ellers styrer
            # den der sweepede - ogsaa naar det er ES.
            sweep = {x[0] for x in raids if x[1] == side and not x[5]}
            st = "NQ" if "NQ" in sweep else k
            g = (dict(a=anch, e=ext) if st == k else dict(a=oth[0], e=oth[1]))
            armed = dict(side=side, hit=k, styrer=st, ts=ts, seen=0,
                         anchors={k: anch, other: oth[0]},
                         levels={k: lvl, other: (oth[0] + oth[1]) / 2.0},
                         gov=g)

        if armed and all(bars[k] is not None for k in SYMS):
            side = armed["side"]
            # dagsgraensen skal ogsaa spaerre et setup der blev armeret FOER
            # graensen blev brudt - ellers slipper en handel igennem bagefter
            if dagsstop is not None and dagR.get(d, 0.0) <= dagsstop:
                armed = None
            elif armed["seen"] >= max_conf_bars or not can_enter:
                armed = None
            else:
                armed["seen"] += 1
                # "Lukker et af aktiverne igennem sin EQ-linje EFTER raidet, er
                # setuppet doedt." Raid-baren selv taeller ikke med: der er
                # sweepet, og en luk taet paa linjen er netop hvad et rent raid
                # ser ud som. Uden det her doer 01-04 15:42 paa 0,25 point.
                dead = (armed["ts"] != ts) and any(
                    (bars[k][3] > armed["levels"][k]) if side == "bear"
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
                        _st = armed["styrer"]
                        pos = dict(side=side, day=d, t0=EM.fmt(ts),
                                   styrer=_st, gov=dict(armed["gov"]),
                                   nqgov=dict(a=armed["anchors"]["NQ"],
                                              e=bars["NQ"][3]), adds=[],
                                   dagR0=dagR.get(d, 0.0),
                                   risk0=abs(bars[_st][3] -
                                             (armed["gov"]["a"] + armed["gov"]["e"]) / 2.0),
                                   exit=None, entries=[bars["NQ"][3]])
                        armed = None
    return pd.DataFrame(trades), pd.DataFrame(log)
