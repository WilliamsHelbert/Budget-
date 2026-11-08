"""Skriver min vurdering af hver uenig trade (motor uden dagsregel vs Williams journal) til vurdering.json."""
import json, pandas as pd, numpy as np, tjr, match
UD = "/mnt/project-files/backtest/tjr/jan-mar2026_alle"
tjr.MAX_TRADES, tjr.STOP_EFTER_WIN = 99, False
d = tjr.load("2026-01-02", "2026-03-31")
rows = []
for day in pd.date_range("2026-01-02", "2026-03-31", freq="B", tz=tjr.NY):
    rows += tjr.run_day(day, d, "B")
m = pd.DataFrame(rows); m = m[m.dato <= "2026-03-26"].copy()
log = pd.DataFrame(tjr.LOG, columns=["dato", "tid", "model", "retning", "event", "info"])
w = match.load_j()
par, used = match.match(m, w)
wpar = {p[0] for p in par}
def hm(x):
    return f"{x:%H:%M}"
def dk(ts):
    return ts.tz_convert("Europe/Copenhagen").strftime("%H:%M")
# Williams exit i NY-tid
def wexit(r):
    a = pd.Timestamp("2000-01-01 " + r.entry); b = pd.Timestamp("2000-01-01 " + r.exit)
    return r.ts + (b - a)
w["exit_ts"] = w.apply(wexit, axis=1)
m["ts"] = m["_ts"]; m["xts"] = m["_exit_ts"]
out = {}
# --- motor-trades William ikke har
for j, r in m[~m.index.isin(used)].iterrows():
    lv = r["_lv"]; long = r.retning == "long"; ts = r["_ts"]; t1 = lv["sweep"][1]
    mins = round((ts - t1).total_seconds() / 60)
    dist = abs(r.entry - lv["sweep"][2])
    t2 = lv["s2"][1] if "s2" in lv else t1 + pd.Timedelta(minutes=5)
    x2 = d[(d.index >= t1) & (d.index < t2)]; x3 = d[(d.index >= t2) & (d.index < ts)]
    ext2 = (x2.low.min() if long else x2.high.max()) if len(x2) else np.nan
    resweep = bool(len(x3)) and ((x3.low.min() < ext2) if long else (x3.high.max() > ext2))
    pts = []; svag = 0
    if mins > 90:
        pts.append(f"{mins} min fra step 1 til entry: setuppet er gammelt (ingen af dine trades er over 90 min)"); svag += 2
    elif mins > 60:
        pts.append(f"{mins} min fra step 1 til entry (langt, men du har ét på 75 min)"); svag += 1
    if dist > 100:
        pts.append(f"entry {dist:.0f} pts fra liq (din vens 100-pts regel)"); svag += 1
    if resweep:
        pts.append("sweep-ekstremen blev taget igen før entry (din vens regel 2)"); svag += 1
    wd = w[w.dato == r.dato]
    inde = wd[(wd.ts <= ts) & (wd.exit_ts > ts)]
    if len(inde):
        q = inde.iloc[0]; pts.append(f"du var selv i en {q.retning}-trade fra {dk(q.ts)}, så du kunne ikke tage den")
    elif len(wd[(wd.ts < ts) & (wd.r > 0)]):
        pts.append("du havde allerede et win den dag (din dagsregel)")
    same = wd[wd.retning == r.retning]
    if len(same) and not len(inde):
        pts.append("du tog samme retning kl. " + ", ".join(dk(x) for x in same.ts) + " (mere end 10 min fra)")
    if not pts:
        pts.append("jeg kan ikke se noget ugyldigt i reglerne: tjek chartet, måske en du har overset")
    dom = "sandsynligvis ugyldig" if svag >= 2 else ("tvivlsom" if svag == 1 else ("ok, men du var optaget" if len(inde) else "ser gyldig ud"))
    out[f"{r.dato}|{r.retning}|{ts.hour*60+ts.minute}|m"] = dom + ": " + "; ".join(pts)
# --- Williams trades motoren ikke har
for i, r in w[~w.index.isin(wpar)].iterrows():
    ts = r.ts; pts = []
    md = m[m.dato == r.dato]
    inde = md[(md.ts <= ts) & (md.xts > ts)]
    if len(inde):
        q = inde.iloc[0]; pts.append(f"motoren var i en {q.retning} {q.model} fra {dk(q.ts)} til {dk(q.xts)}")
    lg = log[(log.dato == r.dato) & (log.retning == r.retning)]
    lg = lg[lg.tid <= ts.strftime("%H:%M")]
    for mod in ["4-step", "3-step"]:
        e = lg[lg.model == mod]
        if len(e):
            last = e.iloc[-1]; ev = last.event
            if ev.startswith("1"):
                st = "venter på step 2" if mod == "4-step" else "venter på pullback"
            elif ev.startswith("2"):
                st = "venter på pullback (step 3)"
            elif ev == "pullback":
                st = "har pullback, venter på 1m entry-BOS (step 4)"
            elif ev.startswith("entry blokeret"):
                st = "entry blev blokeret af en åben trade, setuppet gik tilbage og venter på ny pullback"
            elif ev == "skip TP<0,9R":
                st = "entry droppet fordi intet TP lå 0,9R væk, venter på ny pullback"
            else:
                st = ev
            pts.append(f"{mod}: " + st + f" (sidste hændelse {ev} kl. {dk(pd.Timestamp(r.dato + ' ' + last.tid, tz=tjr.NY))})")
        else:
            pts.append(f"{mod} {r.retning}: intet step 1 endnu" + (" (ingen liq taget i den retning)" if mod == "4-step" else " (ingen 5m close gennem liq)"))
    near = md[(md.retning == r.retning)]
    if len(near):
        pts.append("motoren tog samme retning kl. " + ", ".join(dk(x) for x in near.ts))
    if ts.hour * 60 + ts.minute > 12 * 60:
        pts.insert(0, "entry efter 12:00 NY (18:00 dansk), uden for vinduet")
    out[f"{r.dato}|{r.retning}|{ts.hour*60+ts.minute}|w"] = "; ".join(pts)
json.dump(out, open(f"{UD}/vurdering.json", "w"), ensure_ascii=False, indent=0)
print(len(out))
for k, v in out.items():
    print(k, "::", v)
