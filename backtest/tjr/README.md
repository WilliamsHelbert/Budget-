# TJR-modellen (4-step) på NQ

```bash
python3 -m pip install pandas pyarrow
python3 backtest/tjr/tjr.py 2026-01-02 2026-03-31 --ud /mnt/project-files/backtest/tjr/jan-mar2026
python3 backtest/tjr/rapport.py /mnt/project-files/backtest/tjr/jan-mar2026 "TJR 4-step · NQ jan–mar 2026"
```

Regler og antagelser står i toppen af `tjr.py`. Data: `/mnt/project-files/data/NQ_samlet_15s.parquet` (15s, UTC).
Regel A: TP er nærmeste liq, og tradet springes over, hvis den er under 0,9R. Regel B: TP er nærmeste liq, der er mindst 0,9R væk.
