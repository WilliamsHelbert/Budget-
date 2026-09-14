"""Bar-by-bar trace of EQ life + signal logic for one day, to eyeball vs TradingView."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-09-08"
C = M._data(60); BAR, M1, TL, TOD, DAY_ = C["bar"], C["m1"], C["tl"], C["tod"], C["day"]
OPEN_MIN, END = 15*60+30, 16*60

bear = {k: None for k in M.SYMS}; bull = {k: None for k in M.SYMS}
pmin = {k: None for k in M.SYMS}; pconf = {k: None for k in M.SYMS}
armed = None
print(f"=== {DAY}  EQ-trace 15:30-16:00 (CPH) ===\n")
for ts in TL:
    if DAY_.get(ts) != DAY: continue
    tod = TOD[ts]
    if not (OPEN_MIN <= tod < END): continue
    mb = ts//60*60
    for k in M.SYMS:
        b = BAR[k].get(ts)
        if b is None: continue
        o, h, l, c = b
        nm = M1[k].get(pmin[k]) if (pmin[k] is not None and mb != pmin[k]) else None
        pmin[k] = mb
        pre = {"bear": bear[k], "bull": bull[k]}
        if bear[k]:
            a, e = bear[k]; e = min(e, l); lvl = (a+e)/2
            if h >= lvl:
                print(f"{M.fmt(ts)[11:]} {k} RAID  bear EQ {lvl:9.2f} (anker {a:.2f}, laveste {e:.2f})  "
                      f"15s-luk {c:.2f} -> {'LUKKET IGENNEM (ugyldig)' if c>lvl else 'afvist = gyldig'}")
                bear[k] = None
            else: bear[k] = (a, e)
        if bull[k]:
            a, e = bull[k]; e = max(e, h); lvl = (a+e)/2
            if l <= lvl:
                print(f"{M.fmt(ts)[11:]} {k} RAID  bull EQ {lvl:9.2f} (anker {a:.2f}, hoejeste {e:.2f})  "
                      f"15s-luk {c:.2f} -> {'LUKKET IGENNEM (ugyldig)' if c<lvl else 'afvist = gyldig'}")
                bull[k] = None
            else: bull[k] = (a, e)
        if nm is not None:
            po, ph, pl, pc = nm; eq1 = (ph+pl)/2
            t1 = M.fmt(pmin[k]-60)[11:16]
            if pc < po and pc < eq1:
                if bear[k] is None:
                    bear[k] = (ph, min(pl, l))
                    print(f"{M.fmt(ts)[11:]} {k} NY    bear EQ fra 1m {t1}  O{po:.2f} H{ph:.2f} L{pl:.2f} C{pc:.2f} "
                          f"(eq {eq1:.2f}) -> anker={ph:.2f}")
                else:
                    print(f"{M.fmt(ts)[11:]} {k}  -    1m {t1} var bearish-trigger, men bear EQ er stadig aktiv -> ingen ny")
            if pc > po and pc > eq1:
                if bull[k] is None:
                    bull[k] = (pl, max(ph, h))
                    print(f"{M.fmt(ts)[11:]} {k} NY    bull EQ fra 1m {t1}  O{po:.2f} H{ph:.2f} L{pl:.2f} C{pc:.2f} "
                          f"(eq {eq1:.2f}) -> anker={pl:.2f}")
                else:
                    print(f"{M.fmt(ts)[11:]} {k}  -    1m {t1} var bullish-trigger, men bull EQ er stadig aktiv -> ingen ny")
