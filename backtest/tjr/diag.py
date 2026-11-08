"""Diagnose af uenige trades: kører motoren uden dagsregel med event-log og forklarer hver uenighed."""
import json, sys
import pandas as pd
import tjr, match

UD = "/mnt/project-files/backtest/tjr/jan-mar2026_alle"
tjr.MAX_TRADES, tjr.STOP_EFTER_WIN = 99, False
d = tjr.load("2026-01-02", "2026-03-31")
rows = []
for day in pd.date_range("2026-01-02", "2026-03-31", freq="B", tz=tjr.NY):
    rows += tjr.run_day(day, d, "B")
m = pd.DataFrame(rows)
log = pd.DataFrame(tjr.LOG, columns=["dato", "tid", "model", "retning", "event", "info"])
log.to_csv(f"{UD}/eventlog.csv", index=False)
m.to_pickle(f"{UD}/diag_trades.pkl")
print(len(m), "trades", len(log), "events")
