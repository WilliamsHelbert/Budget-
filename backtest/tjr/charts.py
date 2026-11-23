"""PNG-chart pr. trade (enige + uenige) med alle steps markeret. Brug: charts.py ud_mappe"""
import json, sys, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

d = json.load(open("/mnt/project-files/backtest/tjr/jan-mar2026_alle/artifact_data.json"))
UP, DN, ACC = "#1f9d63", "#d64535", "#2f5bd3"

def hm(m, dk):
    m = int(round(m + dk)) % 1440; return f"{m//60:02d}:{m%60:02d}"

def navn(t):
    return f'{t["dato"]}_{t["entry_tid"].replace(":", "")}_{t["retning"]}_{"w" if t["model"] == "William" else "m"}'

def tegn(t, fil):
    B = d["bars"][t["dato"]]; dk = B["dk"]; t0 = B["t0"]
    lv = t.get("lv"); te = t["t_entry"]
    if lv:
        a = min(lv["liq"][1], te) - 15; b = max(t.get("t_exit") or te, te) + 15
    else:
        a, b = te - 75, te + 60
    a = max(a, te - 300)
    idx = [i for i, m in enumerate(B["m"]) if a <= t0 + m <= b]
    if not idx: return False
    step = 1 if len(idx) <= 180 else (2 if len(idx) <= 360 else 5)
    fig, ax = plt.subplots(figsize=(12, 6.2), dpi=110)
    xs = []
    for k in range(0, len(idx), step):
        g = idx[k:k + step]; x = t0 + B["m"][g[0]]
        o, c = B["o"][g[0]], B["c"][g[-1]]; h = max(B["h"][i] for i in g); l = min(B["l"][i] for i in g)
        col = UP if c >= o else DN
        ax.plot([x + step / 2, x + step / 2], [l, h], color=col, lw=.8, zorder=2)
        ax.add_patch(Rectangle((x + .15, min(o, c)), step - .3, max(abs(c - o), .25), color=col, zorder=3))
        xs.append(x)
    lo = min(B["l"][i] for i in idx); hi = max(B["h"][i] for i in idx); pad = (hi - lo) * .08
    def lab(x, y, txt, col, op=True):
        ax.annotate(txt, (x, y), xytext=(0, 18 if op else -22), textcoords="offset points", ha="center", fontsize=9,
                    color="white", fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", fc=col, ec="none"),
                    arrowprops=dict(arrowstyle="-", color=col, lw=1), zorder=6)
    long = t["retning"] == "long"
    if lv:
        L = lv["liq"]
        ax.hlines(L[2], max(L[0], a), b, color="#8a6d1f", lw=1.2, ls="--", zorder=4)
        ax.text(max(L[0], a) + 1, L[2], f' {L[3]} {L[2]}', color="#8a6d1f", fontsize=8, va="bottom")
        lab(L[1], L[2], "1 " + ("sweep" if t["model"] == "4-step" else "5m close"), "#8a6d1f", not long)
        n = 2
        if lv.get("s2"):
            S = lv["s2"]; ax.hlines(S[2], S[0], S[1], color=ACC, lw=1.2, zorder=4)
            lab(S[1], S[2], "2 5m BOS/iFVG", ACC, not long); n = 3
        S = lv["s3"]
        if S[4] == "bos":
            ax.hlines(S[2], S[0], S[1], color="#7a4fc9", lw=1.2, zorder=4); yy = S[2]
        else:
            ax.add_patch(Rectangle((S[0], S[2]), S[1] - S[0], S[3] - S[2], color="#7a4fc9", alpha=.18, zorder=1)); yy = (S[2] + S[3]) / 2
        lab(S[1], yy, f"{n} pullback ({'1m BOS' if S[4]=='bos' else 'iFVG'})", "#7a4fc9", long); n += 1
        S = lv["s4"]; ax.hlines(S[2], S[0], S[1], color="#222", lw=1.2, zorder=4)
        lab(S[1], S[2], f"{n} entry", "#222", not long)
        for y, c_, nv in [(t["entry"], "#555", "entry"), (t["sl"], DN, "SL"), (t["tp"], UP, "TP")]:
            ax.hlines(y, te, (t.get("t_exit") or te) + 3, color=c_, lw=1, ls=":", zorder=4)
            lo, hi = min(lo, y), max(hi, y)
        if t.get("t_exit"): ax.axvline(t["t_exit"], color="#999", lw=.8, ls=":")
        tit = (f'{t["dato"]} · motor {t["model"]} {t["retning"]} · entry {t["entry_tid"]} · {t["R"]:+.2f}R · '
               + ("ENIG" if t["journal"] == "enig" else "KUN MOTOR"))
    else:
        ax.axvline(te, color=ACC, lw=1.5); ax.text(te, hi + pad * .5, " din entry", color=ACC, fontsize=9)
        tit = f'{t["dato"]} · din {t["retning"]} {t["entry_tid"]} · {t["R"]:+.2f}R · KUN DIG · motor samme dag: {t.get("motor_dag") or "-"}'
    ax.set_ylim(lo - pad, hi + pad); ax.set_xlim(a, b)
    tk = [x for x in range(int(a) - int(a) % 15, int(b) + 1, 15) if x >= a]
    ax.set_xticks(tk); ax.set_xticklabels([hm(x, dk) for x in tk], fontsize=8)
    ax.tick_params(axis="y", labelsize=8); ax.grid(alpha=.15)
    ax.set_title(tit + f"   ({step}m candles, dansk tid)", fontsize=10, loc="left")
    for s in ["top", "right"]: ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(fil); plt.close(fig); return True

if __name__ == "__main__":
    UD = sys.argv[1]; os.makedirs(UD, exist_ok=True)
    n = 0
    for t in d["trades"]:
        if t["journal"] in ("enig", "kun_motor", "kun_william") and t["dato"] in d["bars"]:
            n += tegn(t, os.path.join(UD, navn(t) + ".png"))
    print(n)

def step_felter(t):
    """Tekst for hvert step (motorens trades). Tom for Williams egne."""
    if t["model"] == "William":
        return {"Steps": "Kun i din journal, motoren har ingen steps her", "Motor samme dag": t.get("motor_dag") or "-"}
    f = {"Liq": t.get("liq") or "", "Step 1": t.get("step1") or ""}
    if t["model"] == "4-step":
        f["Step 2"] = t.get("step2") or ""
    f["Pullback"] = t.get("pullback") or ""
    f["Entry"] = t.get("entry_bos") or ""
    f["Exit"] = t.get("exit") or ""
    return f
