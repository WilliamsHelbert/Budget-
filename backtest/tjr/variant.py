"""Koer motoren (uden dagsregel) med flag sat via argv: NAVN=vaerdi ... og print match mod journalen."""
import sys, pandas as pd, tjr, match
for a in sys.argv[1:]:
    k, v = a.split("=")
    setattr(tjr, k, {"True": True, "False": False}.get(v, v))
tjr.MAX_TRADES, tjr.STOP_EFTER_WIN = 99, False
d = tjr.load("2026-01-02", "2026-03-26")
rows = []
for day in pd.date_range("2026-01-02", "2026-03-26", freq="B", tz=tjr.NY):
    rows += tjr.run_day(day, d, "B")
m = pd.DataFrame(rows); w = match.load_j()
par, used = match.match(m, w)
print(" ".join(sys.argv[1:]) or "standard", "| trades", len(m), "sumR", round(m.R.sum(), 2), "| enige", len(par), "kun motor", len(m) - len(used), "kun W", len(w) - len(par), flush=True)
m.to_pickle("/tmp/claude-0/-home-user-Budget-/e8c34211-8e14-53c9-8717-a26fd4586bbc/scratchpad/v_" + ("_".join(sys.argv[1:]) or "std") + ".pkl")
