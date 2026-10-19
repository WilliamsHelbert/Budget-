"""
Swing (Hugin) og Market Open (Munin) som i NinjaTrader-strategien OdinMotor.cs, bar for bar paa 15s-data.

Brug: python odin_motor.py NQ.parquet ES.parquet fra til ud.csv

Swing  (PlanSwing):  kun formarkedets niveauer (08:00-09:00 NY), stop 40, intet TP, stop til entry ved +75,
                     ud kl. 11:00 NY (17:00 dansk). rv5 >= 2,0 eller < 1,0 -> ingen swing. Ingen handler
                     langfredag og Labor Day.
Market Open:         retning fra den oprindelige swing (London + formarked, stop 10 / TP 175): tabt -> modsat,
                     ellers samme vej. Entry ved luk af 09:29:45-baren, stop 30, ud ved luk af 09:30:45-baren.
                     rv5 >= 2,25 -> spring over.
Fyld: entry = barens close, stop/TP ramt paa en senere bar = stop-/TP-prisen, tidsudgang = barens close.
R = point / 10.
"""
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from smt_backtest import load

NLH, NLL, NPH, NPL, ELH, ELL, EPH, EPL = range(8)
T_BESLUT = 9 * 3600 + 29 * 60 + 45


def paaske(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    return date(y, (h + l - 7 * m + 114) // 31, (h + l - 7 * m + 114) % 31 + 1)


def fridag(d):
    if d.month == 9 and d.weekday() == 0 and d.day <= 7:
        return True
    return d == paaske(d.year) - timedelta(days=2)


def pt(x):
    return round(x * 4.0) / 4.0 if x else 0.0


class Motor:
    def __init__(self, sw_stop=10.0, sw_tp=175.0, sw_ud_ny=0, sw_be=0.0, mo_stop=30.0,
                 rv5_graense=2.25, rv5_min=0.0, kun_formarked=False, fridage=True):
        self.sw_stop, self.sw_tp, self.sw_ud_ny, self.sw_be = sw_stop, sw_tp, sw_ud_ny, sw_be
        self.mo_stop, self.rv5_graense, self.rv5_min = mo_stop, rv5_graense, rv5_min
        self.kun_formarked, self.fridage = kun_formarked, fridage
        self.dag = None
        self.trp, self.rth, self.forrige_luk, self.rv5 = [], None, None, None
        self.nulstil()

    def nulstil(self):
        self.niv = [None] * 8
        self.taget = [False] * 8
        self.brugt = [False] * 8
        self.sidst_h = self.sidst_l = 0
        self.fra_h = self.til_h = self.fra_l = self.til_l = 0
        self.har_sw, self.sw_status, self.mo_givet = False, None, False

    def ny_dag(self):
        if self.rth is not None and self.rth[4] > 1000:
            h, l, c = self.rth[1], self.rth[2], self.rth[3]
            if self.forrige_luk is not None:
                pc = self.forrige_luk
                self.trp.append(max(h - l, abs(h - pc), abs(l - pc)) / c * 100.0)
            self.forrige_luk = c
        self.rth = None
        self.rv5 = sum(self.trp[-5:]) / 5.0 if len(self.trp) >= 5 else None
        self.nulstil()

    def tilladt(self):
        if self.fridage and fridag(self.dag):
            return False
        return not (self.rv5_graense > 0 and self.rv5 is not None and self.rv5 >= self.rv5_graense)

    def sweep(self, h, l, har_e, eh, el, pA):
        n, t, b = self.niv, self.taget, self.brugt
        if not t[NLH] and not b[NLH] and n[NLH] is not None and h >= n[NLH]: t[NLH] = True
        if pA and not t[NPH] and n[NPH] is not None and h >= n[NPH]: t[NPH] = True
        if har_e and not t[ELH] and not b[ELH] and n[ELH] is not None and eh >= n[ELH]: t[ELH] = True
        if har_e and pA and not t[EPH] and n[EPH] is not None and eh >= n[EPH]: t[EPH] = True
        if not t[NLL] and not b[NLL] and n[NLL] is not None and l <= n[NLL]: t[NLL] = True
        if pA and not t[NPL] and n[NPL] is not None and l <= n[NPL]: t[NPL] = True
        if har_e and not t[ELL] and not b[ELL] and n[ELL] is not None and el <= n[ELL]: t[ELL] = True
        if har_e and pA and not t[EPL] and n[EPL] is not None and el <= n[EPL]: t[EPL] = True

    def paa_bar(self, t, d, ny_sek, o, h, l, c, har_e, eo, eh, el, ec):
        ny_min = ny_sek // 60
        if self.dag != d:
            self.dag = d
            self.ny_dag()
        ud = []
        if 570 <= ny_min < 960:
            if self.rth is None:
                self.rth = [o, h, l, c, 1]
            else:
                self.rth[1] = max(self.rth[1], h); self.rth[2] = min(self.rth[2], l)
                self.rth[3] = c; self.rth[4] += 1
        n = self.niv
        mx = lambda a, b: b if a is None else max(a, b)
        mn = lambda a, b: b if a is None else min(a, b)
        if 120 <= ny_min < 480:
            n[NLH] = mx(n[NLH], h); n[NLL] = mn(n[NLL], l)
            if har_e: n[ELH] = mx(n[ELH], eh); n[ELL] = mn(n[ELL], el)
        if 480 <= ny_min < 540:
            n[NPH] = mx(n[NPH], h); n[NPL] = mn(n[NPL], l)
            if har_e: n[EPH] = mx(n[EPH], eh); n[EPL] = mn(n[EPL], el)
        if 480 <= ny_min < 525:
            b = self.brugt
            if n[NLH] is not None and h >= n[NLH]: b[NLH] = True
            if n[NLL] is not None and l <= n[NLL]: b[NLL] = True
            if har_e and n[ELH] is not None and eh >= n[ELH]: b[ELH] = True
            if har_e and n[ELL] is not None and el <= n[ELL]: b[ELL] = True

        if self.har_sw and self.sw_status == "aaben" and t > self.sw_t and ny_sek < T_BESLUT:
            tp = pt(self.sw_tp)
            if self.sw_kort:
                stop_r, tp_r = h >= self.sw_e + self.sw_stop_pt, l <= self.sw_e - tp
            else:
                stop_r, tp_r = l <= self.sw_e - self.sw_stop_pt, h >= self.sw_e + tp
            if stop_r: self.sw_status = "tabt"
            elif tp_r: self.sw_status = "vundet"

        if ny_min >= 525 and ny_sek < T_BESLUT and not self.har_sw:
            self.sweep(h, l, har_e, eh, el, ny_min >= 540)
            tg = self.taget
            if self.kun_formarked:
                nH = int(tg[NPH] and tg[EPH]); nL = int(tg[NPL] and tg[EPL])
            else:
                nH = int(tg[NLH] and tg[ELH]) + int(tg[NPH] and tg[EPH])
                nL = int(tg[NLL] and tg[ELL]) + int(tg[NPL] and tg[EPL])
            min_nr = t // 60
            s15 = t % 60 == 45
            if nH > self.sidst_h: self.fra_h, self.til_h, self.sidst_h = min_nr, min_nr + 1 if s15 else min_nr, nH
            if nL > self.sidst_l: self.fra_l, self.til_l, self.sidst_l = min_nr, min_nr + 1 if s15 else min_nr, nL
            ned = har_e and c < o and ec < eo
            op = har_e and c > o and ec > eo
            kort_ok = nH > 0 and ned and self.fra_h <= min_nr <= self.til_h
            lang_ok = nL > 0 and op and self.fra_l <= min_nr <= self.til_l
            if kort_ok or lang_ok:
                self.har_sw, self.sw_kort, self.sw_e, self.sw_t = True, kort_ok, c, t
                self.sw_status, self.sw_stop_pt = "aaben", pt(self.sw_stop)
                if self.tilladt() and not (self.rv5_min > 0 and self.rv5 is not None and self.rv5 < self.rv5_min):
                    ud_t = t - ny_sek + self.sw_ud_ny if self.sw_ud_ny > 0 else t + 15 + 4 * 3600
                    ud.append(dict(navn="SWING", kort=kort_ok, stop=self.sw_stop_pt, tp=pt(self.sw_tp),
                                   ud_t=ud_t, be=self.sw_be, t=t, entry=c))

        if not self.mo_givet and ny_sek == T_BESLUT:
            self.mo_givet = True
            if self.har_sw and self.tilladt():
                kort = (not self.sw_kort) if self.sw_status == "tabt" else self.sw_kort
                ud.append(dict(navn="MO", kort=kort, stop=pt(self.mo_stop), tp=0.0, ud_t=t + 75, be=0.0, t=t, entry=c))
        return ud


def run(nq_path, es_path, start, end):
    a, b = load(nq_path), load(es_path)
    t0 = int(pd.Timestamp(start, tz="America/New_York").timestamp()) - 20 * 86400
    t1 = int(pd.Timestamp(end, tz="America/New_York").timestamp()) + 86400
    a = a[(a.t >= t0) & (a.t < t1)].reset_index(drop=True)
    b = b[(b.t >= t0) & (b.t < t1)].set_index("t")
    bb = b.reindex(a.t)
    harE = bb.close.notna().values
    lt = pd.to_datetime(a.t, unit="s", utc=True).dt.tz_convert("America/New_York")
    dage = lt.dt.date.values
    sek = (lt.dt.hour * 3600 + lt.dt.minute * 60 + lt.dt.second).values
    T, O, H, L, C = a.t.values, a.open.values, a.high.values, a.low.values, a.close.values
    EO, EH, EL, EC = bb.open.values, bb.high.values, bb.low.values, bb.close.values
    motorer = {"Swing": Motor(sw_stop=40.0, sw_tp=0.0, sw_ud_ny=11 * 3600, sw_be=75.0, rv5_graense=2.0,
                              rv5_min=1.0, kun_formarked=True),
               "Market Open": Motor(rv5_graense=2.25)}
    aabne, handler = {}, []
    start_d = pd.Timestamp(start).date()
    for i in range(len(T)):
        t, h, l, c = int(T[i]), H[i], L[i], C[i]
        for nm in list(aabne):
            p = aabne[nm]
            if t <= p["t"]:
                continue
            ex = None
            if p["kort"]:
                if h >= p["sl"]: ex = (p["sl"], "BE" if p["be_flyt"] else "SL")
                elif p["tp"] and l <= p["tp"]: ex = (p["tp"], "TP")
            else:
                if l <= p["sl"]: ex = (p["sl"], "BE" if p["be_flyt"] else "SL")
                elif p["tp"] and h >= p["tp"]: ex = (p["tp"], "TP")
            if ex is None and t + 15 >= p["ud_t"]:
                ex = (c, "TID")
            if ex is None and p["be"] > 0 and not p["be_flyt"]:
                bedst = p["entry"] - l if p["kort"] else h - p["entry"]
                if bedst >= p["be"]:
                    p["sl"], p["be_flyt"] = p["entry"], True
            if ex is not None:
                pts = (p["entry"] - ex[0]) if p["kort"] else (ex[0] - p["entry"])
                r = p["rec"]
                r.update(exit=pd.Timestamp(t + 15, unit="s", tz="UTC").tz_convert("America/New_York").strftime("%H:%M:%S"),
                         exit_pris=ex[0], resultat=ex[1], points=round(pts, 2), R=round(pts / 10, 2))
                handler.append(r)
                del aabne[nm]
        for nm, m in motorer.items():
            for od in m.paa_bar(t, dage[i], int(sek[i]), O[i], h, l, c, harE[i], EO[i], EH[i], EL[i], EC[i]):
                if od["navn"] != ("SWING" if nm == "Swing" else "MO") or dage[i] < start_d or nm in aabne:
                    continue
                e = od["entry"]
                sl = e + od["stop"] if od["kort"] else e - od["stop"]
                tp = (e - od["tp"] if od["kort"] else e + od["tp"]) if od["tp"] else 0.0
                lt_ = pd.Timestamp(t + 15, unit="s", tz="UTC").tz_convert("America/New_York")
                rec = dict(model=nm, dato=str(dage[i]), tid=lt_.strftime("%H:%M:%S"),
                           retning="SHORT" if od["kort"] else "LONG", entry=e, sl=sl, tp=tp or None,
                           rv5=None if m.rv5 is None else round(m.rv5, 2))
                aabne[nm] = dict(t=t, kort=od["kort"], entry=e, sl=sl, tp=tp, ud_t=od["ud_t"], be=od["be"],
                                 be_flyt=False, rec=rec)
    return handler


if __name__ == "__main__":
    nq, es, start, end, out = sys.argv[1:6]
    df = pd.DataFrame(run(nq, es, start, end))
    df.to_csv(out, index=False)
    pd.set_option("display.width", 250)
    print(df.tail(30).to_string(index=False))
    for nm, g in df.groupby("model"):
        print(nm, len(g), "trades", f"{g.R.sum():+.1f} R")
