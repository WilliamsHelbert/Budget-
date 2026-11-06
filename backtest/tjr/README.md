# TJR-modellen (3-step og 4-step) på NQ

```bash
python3 -m pip install pandas pyarrow
python3 backtest/tjr/tjr.py 2026-01-02 2026-03-31 --ud /mnt/project-files/backtest/tjr/jan-mar2026
python3 backtest/tjr/eksport.py /mnt/project-files/backtest/tjr/jan-mar2026   # JSON til artifacten
```

`artifact_skabelon.html` + `artifact_data.json` (erstat `__DATA__`) = trade-journalen.
Regler og antagelser står i toppen af `tjr.py`.
