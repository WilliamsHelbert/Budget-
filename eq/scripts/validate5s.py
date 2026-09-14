"""Afgoer NQ-raids paa 5s-data og maal hvor godt 15s-reglerne ramte.

For hver bar hvor en EQ var aktiv, evalueres fire regler paa PRAECIS samme
EQ-tilstand. Tilstanden drives af 5s-sandheden, saa alle regler bedoemmes
paa de samme beslutningspunkter.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M, pandas as pd, collections

def load5s(sym="NQ"):
    d = pd.read_parquet(f"{M.BASE}/{sym}5s.parquet")
    return {int(t): (float(o), float(h), float(l), float(c))
            for t, o, h, l, c in zip(d.ts, d.open, d.high, d.low, d.close)}

def run(SYM="NQ"):
    C = M._data(15); BAR, M1, TL, TOD, DAY = C["bar"], C["m1"], C["tl"], C["tod"], C["day"]
    S5 = load5s(SYM)
    have = set()
    for t in S5: have.add(t // 86400)
    rows = []
    day = bear = bull = None
    for ts in TL:
        tod = TOD[ts]
        if not (M.OPEN_MIN <= tod < M.CLOSE_MIN): continue
        b = BAR[SYM].get(ts)
        if b is None: continue
        subs = [S5.get(ts), S5.get(ts+5), S5.get(ts+10)]
        if any(x is None for x in subs): continue        # kun barer med fuld 5s-daekning
        o, h, l, c = b
        d = DAY[ts]
        if day != d: day = d; bear = bull = None
        mb = ts//60*60

        def judge(side, a, e0):
            """returner (sandhed_5s, ext, pre, order)"""
            if side == "bear":
                e1 = min(e0, l)
                ext = h >= (a+e1)/2.0
                pre = h >= (a+e0)/2.0
                order = pre or (ext and c > o)
                e = e0; true = False
                for (so, sh, sl, sc) in subs:
                    e = min(e, sl)
                    if sh >= (a+e)/2.0: true = True; break
            else:
                e1 = max(e0, h)
                ext = l <= (a+e1)/2.0
                pre = l <= (a+e0)/2.0
                order = pre or (ext and c < o)
                e = e0; true = False
                for (so, sh, sl, sc) in subs:
                    e = max(e, sh)
                    if sl <= (a+e)/2.0: true = True; break
            return true, ext, pre, order

        for side, st in (("bear", bear), ("bull", bull)):
            if st is None: continue
            a, e0 = st
            true, ext, pre, order = judge(side, a, e0)
            rows.append(dict(ts=ts, side=side, true=true, ext=ext, pre=pre, order=order))
            if true:
                if side == "bear": bear = None
                else: bull = None
            else:
                e = min(e0, l) if side == "bear" else max(e0, h)
                if side == "bear": bear = (a, e)
                else: bull = (a, e)

        pm = M1[SYM].get(mb-60) if ts == mb else None
        if pm:
            po, ph, pl, pc = pm; eq1 = (ph+pl)/2.0
            if pc < po and pc < eq1 and bear is None:
                true, ext, pre, order = judge("bear", ph, pl)
                rows.append(dict(ts=ts, side="bear", true=true, ext=ext, pre=pre, order=order, birth=True))
                if not true: bear = (ph, min(pl, l))
            if pc > po and pc > eq1 and bull is None:
                true, ext, pre, order = judge("bull", pl, ph)
                rows.append(dict(ts=ts, side="bull", true=true, ext=ext, pre=pre, order=order, birth=True))
                if not true: bull = (pl, max(ph, h))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    import sys as _s
    SYM = _s.argv[1] if len(_s.argv) > 1 else "NQ"
    print("=== " + SYM + " ===")
    df = run(SYM)
    print(f"beslutningspunkter med fuld 5s-daekning: {len(df)}   (aegte raids paa 5s: {df.true.sum()})\n")
    print(f"{'regel':10s} {'enig':>7s} {'falsk positiv':>15s} {'falsk negativ':>15s}   {'praecision':>11s}")
    for r in ("ext", "pre", "order"):
        agree = (df[r] == df.true).mean()*100
        fp = ((df[r]) & (~df.true)).sum()
        fn = ((~df[r]) & (df.true)).sum()
        print(f"{r:10s} {agree:6.2f}% {fp:15d} {fn:15d}   {(df[r]&df.true).sum()/max(df[r].sum(),1)*100:10.1f}%")
    print("\nkun de punkter hvor 15s-reglerne er uenige (dvs. flytningen er afgoerende):")
    amb = df[df.ext != df.pre]
    print(f"  {len(amb)} punkter. Heraf var {amb.true.sum()} aegte raids paa 5s ({amb.true.mean()*100:.1f} %).")
    for r in ("ext", "pre", "order"):
        print(f"    {r:6s} rigtig i {(amb[r]==amb.true).mean()*100:5.1f} % af dem")
