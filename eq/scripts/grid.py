import sys, os, itertools, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import run, SYMS

rows = []
for conf in (15, 60, 300):
    for em in ("loose", "strict"):
        for be in ("liq5", "close5", "off"):
            res, st, n = run(conf_sec=conf, entry_mode=em, be_mode=be)
            r = dict(confTF=f"{conf}s", entry=em, BE=be, pairs=n,
                     signals=st["signals"], skipped=st["skipped"])
            for k in SYMS:
                s = res[res.asset == k]
                if len(s):
                    r[f"{k}_TP"] = int((s.reason == "TP").sum())
                    r[f"{k}_SL"] = int((s.reason == "SL").sum())
                    r[f"{k}_BE"] = int((s.reason == "BE").sum())
                    r[f"{k}_R"] = round(s.R.sum(), 1)
            r["totR"] = round(res.R.sum(), 1) if len(res) else 0
            rows.append(r)
df = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(df.to_string(index=False))
