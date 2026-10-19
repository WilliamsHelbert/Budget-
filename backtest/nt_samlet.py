"""
Alle 4 modeller som NinjaTrader-strategien OdinSamlet.cs ville have handlet dem, bar for bar paa 15s-data.

Brug: python nt_samlet.py NQ.parquet ES.parquet smt.csv vrg.csv fra til ud.csv

Signalerne:  Swing og Market Open fra odin_motor.Motor; SMT og Vergence fra smt_backtest-CSV'erne (papirhandler).
Ordrer:      alt besluttes ved barens luk og fyldes paa naeste bars open (markedsordre).
             Stop/TP er bud paa NQ-barerne fra fyldbaren: stop ved stopprisen (eller open, hvis den er gappet forbi),
             TP ved TP-prisen. Rammer en bar baade stop og TP, regnes stop.
Swing:       stop 40 fra fyld, stop til fyld ved +75 (barens high/low ved luk), ud kl. 11:00 NY.
Market Open: stop 30 fra fyld, ud efter 09:30:45-baren. Begge springes over, hvis rv5 ikke kendes.
SMT/Verg.:   motorens SL/TP som faste priser; BE flytter stoppet til fyldet; lukker papiret, lukkes positionen.
             Afloest samme vej: nyt SL/TP paa samme position; modsat vej: luk og gaa ind igen.
             Kurvefilter SMT 10 / Vergence 0; papir ved modsat aabent trade i den anden model;
             Market Open lukkes, naar SMT/Vergence gaar ind den modsatte vej.
Stoerrelse:  fast: Swing 2, MO 1, SMT 5, Vergence 5 MNQ (2 USD pr. point). Ingen kommission.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit('/', 1)[0])
from smt_backtest import load
from odin_motor import Motor

ANTAL = {"Swing": 2, "Market Open": 1, "SMT": 5, "Vergence": 5}
KURVE = {"SMT": 10, "Vergence": 0}
USD_PT = 2.0
NY = "America/New_York"


def papir(df, T, idx, H, L, C):
    """Genskab motorens forloeb for hver papirhandel: hvornaar BE flyttes og hvornaar den lukker (barindeks)."""
    ok = df[df.status == "OK"].copy()
    ny = pd.to_datetime(ok.dato + " " + ok.tid) - pd.Timedelta(hours=6)
    ok["i"] = [idx.get(int(pd.Timestamp(x, tz=NY).timestamp()), -1) for x in ny]
    ok = ok[ok.i >= 0].sort_values("i").reset_index(drop=True)
    ud, afvig = [], 0
    for k, r in ok.iterrows():
        s, kort = int(r.i), r.retning == "SHORT"
        sl, tp, be, entry = r.sl, r.tp, r.be, r.entry
        nxt = int(ok.i[k + 1]) if k + 1 < len(ok) and ok.dato[k + 1] == r.dato else None
        be_i, luk_i, res = None, None, None
        hit, early, nobe, bars = False, False, False, 0
        j = s + 1
        while j < len(T):
            h, l, c = H[j], L[j], C[j]
            if (h >= sl) if kort else (l <= sl):
                luk_i, res = j, "BE" if hit else "SL"; break
            if (l <= tp) if kort else (h >= tp):
                luk_i, res = j, "TP"; break
            if nxt is not None and j == nxt:
                luk_i, res = j, "AFLOEST"; break
            if not hit and not pd.isna(be) and not nobe:
                touch = (l <= be) if kort else (h >= be)
                if bars < 2:
                    early = early or touch
                    if bars == 1 and early:
                        if (c < entry) if kort else (c > entry):
                            hit, sl, be_i = True, entry, j
                        else:
                            nobe = True
                elif touch:
                    hit, sl, be_i = True, entry, j
            bars += 1
            j += 1
        if res != r.resultat:
            afvig += 1
        ud.append(dict(i=s, kort=kort, sl=r.sl, tp=tp, be_i=be_i, luk_i=luk_i, res=res,
                       R=0.0 if res == "AFLOEST" else (r.R if not pd.isna(r.R) else 0.0),
                       noegle=f"{r.dato} {r.tid}", rec=r))
    return ud, afvig


class Ben:
    def __init__(self, navn):
        self.navn = navn
        self.pos = 0            # +antal lang, -antal kort
        self.vent = None        # ventende entry: dict(kort, antal, stop_pris, stop_afst, tp, ud_t, be_pt, x)
        self.luk = None         # ventende markedsudgang (grund)
        self.fyld = self.stop = self.tp = None
        self.ud_t, self.be_pt, self.be_flyt = None, 0.0, False
        self.rigtig = None
        self.kurve = []         # (noegle, R) for lukkede papirhandler
        self.cur = None


def kurve_ok(b, n, foer):
    if n <= 0:
        return True
    rs = [r for k, r in sorted(b.kurve) if k < foer]
    if len(rs) < n:
        return True
    kum = np.cumsum(rs)
    return kum[-1] >= kum[-n:].mean()


def run(nq, es, smt_csv, vrg_csv, start, end):
    a, e = load(nq), load(es)
    t0 = int(pd.Timestamp(start, tz=NY).timestamp()) - 20 * 86400
    t1 = int(pd.Timestamp(end, tz=NY).timestamp()) + 86400
    a = a[(a.t >= t0) & (a.t < t1)].reset_index(drop=True)
    bb = e.set_index("t").reindex(a.t)
    harE = bb.close.notna().values
    lt = pd.to_datetime(a.t, unit="s", utc=True).dt.tz_convert(NY)
    dage = lt.dt.date.values
    sek = (lt.dt.hour * 3600 + lt.dt.minute * 60 + lt.dt.second).values
    T, O, H, L, C = a.t.values.astype(np.int64), a.open.values, a.high.values, a.low.values, a.close.values
    EO, EH, EL, EC = bb.open.values, bb.high.values, bb.low.values, bb.close.values
    idx = {int(t): i for i, t in enumerate(T)}
    start_d = pd.Timestamp(start).date()

    smt, af1 = papir(pd.read_csv(smt_csv), T, idx, H, L, C)
    vrg, af2 = papir(pd.read_csv(vrg_csv), T, idx, H, L, C)
    print(f"papir genskabt: SMT {len(smt)} ({af1} afviger), Vergence {len(vrg)} ({af2} afviger)")
    begiv = {}
    for navn, lst in (("SMT", smt), ("Vergence", vrg)):
        for x in lst:
            begiv.setdefault(x["i"], []).append((navn, "ny", x))
            if x["be_i"] is not None:
                begiv.setdefault(x["be_i"], []).append((navn, "be", x))
            if x["luk_i"] is not None:
                begiv.setdefault(x["luk_i"], []).append((navn, "luk", x))
    orden = {"luk": 0, "be": 1, "ny": 2}
    for v in begiv.values():
        v.sort(key=lambda z: orden[z[1]])

    motorer = {"Swing": Motor(sw_stop=40.0, sw_tp=0.0, sw_ud_ny=11 * 3600, sw_be=75.0, rv5_graense=2.0,
                              rv5_min=1.0, kun_formarked=True),
               "Market Open": Motor(rv5_graense=2.25)}
    ben = {n: Ben(n) for n in ("Swing", "Market Open", "SMT", "Vergence")}
    handler, papirlog = [], []

    def tid(t):
        return pd.Timestamp(int(t), unit="s", tz="UTC").tz_convert(NY)

    def ud(b, pris, grund, t):
        kort = b.pos < 0
        pts = (b.fyld - pris) if kort else (pris - b.fyld)
        b.cur.update(exit=tid(t).strftime("%H:%M:%S"), exit_pris=pris, grund=grund, points=round(pts, 2),
                     usd=round(pts * abs(b.pos) * USD_PT, 2))
        handler.append(b.cur)
        b.pos, b.luk, b.cur = 0, None, None

    def luk(b, grund):
        b.vent = None
        if b.pos != 0 and b.luk is None:
            b.luk = grund

    for i in range(len(T)):
        t, o, h, l, c = int(T[i]), O[i], H[i], L[i], C[i]
        # A) markedsordrer fra forrige bars luk fyldes paa open
        for b in ben.values():
            if b.luk is not None and b.pos != 0:
                ud(b, o, b.luk, t)
            if b.vent is not None:
                v = b.vent
                b.vent = None
                b.fyld, b.pos, b.be_flyt = o, -v["antal"] if v["kort"] else v["antal"], False
                b.stop = v["stop_pris"] if v["stop_pris"] is not None else (o + v["stop_afst"] if v["kort"] else o - v["stop_afst"])
                b.tp, b.ud_t, b.be_pt = v["tp"], v["ud_t"], v["be_pt"]
                lt_ = tid(t)
                b.cur = dict(model=b.navn, dato=str(lt_.date()), tid=lt_.strftime("%H:%M:%S"),
                             retning="SHORT" if v["kort"] else "LONG", antal=v["antal"], signal=v["signal"],
                             fyld=o, stop=b.stop, tp=b.tp, signal_stop_pt=v.get("sig_stop"))
        # B) stop / TP inde i baren
        for b in ben.values():
            if b.pos == 0:
                continue
            kort = b.pos < 0
            if (h >= b.stop) if kort else (l <= b.stop):
                ud(b, max(b.stop, o) if kort else min(b.stop, o), "BE" if b.be_flyt else "SL", t)
            elif b.tp is not None and ((l <= b.tp) if kort else (h >= b.tp)):
                ud(b, min(b.tp, o) if kort else max(b.tp, o), "TP", t)
        # C) barens luk
        for n in ("Swing", "Market Open"):
            b = ben[n]
            if b.pos == 0:
                continue
            if t + 15 >= b.ud_t:
                luk(b, "TID")
            elif b.be_pt > 0 and not b.be_flyt:
                bedst = (b.fyld - l) if b.pos < 0 else (h - b.fyld)
                if bedst >= b.be_pt:
                    b.stop, b.be_flyt = b.fyld, True
        for n, m in motorer.items():
            for od in m.paa_bar(t, dage[i], int(sek[i]), o, h, l, c, harE[i], EO[i], EH[i], EL[i], EC[i]):
                if od["navn"] != ("SWING" if n == "Swing" else "MO") or dage[i] < start_d:
                    continue
                b = ben[n]
                if b.pos != 0 or b.vent is not None:
                    continue
                if m.rv5 is None:
                    papirlog.append((n, str(dage[i]), "rv5 ukendt"))
                    continue
                b.vent = dict(kort=od["kort"], antal=ANTAL[n], stop_pris=None, stop_afst=od["stop"], tp=None,
                              ud_t=od["ud_t"], be_pt=od["be"], signal=c)
        for navn, typ, x in begiv.get(i, []):
            if dage[i] < start_d:
                continue
            b, anden, mo = ben[navn], ben["Vergence" if navn == "SMT" else "SMT"], ben["Market Open"]
            if typ == "luk":
                if x["R"] is not None:
                    b.kurve.append((x["noegle"], x["R"]))
                if b.rigtig is x and b.pos != 0:
                    luk(b, "papir lukket")
                if b.rigtig is x:
                    b.rigtig = None
            elif typ == "be":
                if b.rigtig is x and b.pos != 0 and not b.be_flyt:
                    b.stop, b.be_flyt = b.fyld, True
            else:
                ok = kurve_ok(b, KURVE[navn], x["noegle"])
                modsat = anden.pos != 0 and (anden.pos < 0) != x["kort"]
                if not ok or modsat:
                    papirlog.append((navn, x["noegle"], "kurvefilter" if not ok else "modsat " + anden.navn))
                    luk(b, "afloest")
                    b.rigtig = None
                    continue
                if mo.pos != 0 and (mo.pos < 0) != x["kort"]:
                    luk(mo, "modsat " + navn)
                if b.pos != 0 and (b.pos < 0) == x["kort"] and b.luk is None:
                    b.rigtig, b.stop, b.tp, b.be_flyt = x, x["sl"], x["tp"], False
                    b.cur["afloest"] = b.cur.get("afloest", 0) + 1
                    continue
                luk(b, "afloest")
                b.rigtig = x
                b.vent = dict(kort=x["kort"], antal=ANTAL[navn], stop_pris=x["sl"], stop_afst=0, tp=x["tp"],
                              ud_t=None, be_pt=0.0, signal=x["rec"].entry, sig_stop=x["rec"].sl_pts)
    return handler, papirlog


if __name__ == "__main__":
    nq, es, smt_csv, vrg_csv, start, end, out = sys.argv[1:8]
    h, p = run(nq, es, smt_csv, vrg_csv, start, end)
    df = pd.DataFrame(h)
    df.to_csv(out, index=False)
    pd.DataFrame(p, columns=["model", "noegle", "grund"]).to_csv(out.replace(".csv", "_papir.csv"), index=False)
    for n, g in df.groupby("model"):
        print(f"{n:12s} {len(g):4d} handler  {g.points.sum():+9.1f} point  {g.usd.sum():+10.0f} USD")
    print(f"{'I alt':12s} {len(df):4d} handler  {df.usd.sum():+10.0f} USD")
