"""
Databento OHLCV-1s (.dbn.zst) -> 15-sekunders NQ- og ES-filer til backtesten.

Brug (i mappen med scriptet):
    pip install databento pandas pyarrow
    python lav_15s.py <mappe med .dbn.zst-filer> <navn>
Eksempel:
    python lav_15s.py data2023 2023      ->  NQ_2023.parquet  og  ES_2023.parquet

Virker baade med NQ.FUT/ES.FUT (alle kontrakter) og NQ.v.0/ES.v.0 (kontinuerlig).
Spreads (fx NQZ2-NQH3) smides vaek. Hver dag (UTC-dato, dvs. skift kl. 19/20 New York,
foer Asia-sessionen) bruges den kontrakt der havde mest volumen den dag.
"""
import glob
import os
import sys

import databento as db
import pandas as pd


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    folder, name = sys.argv[1], sys.argv[2]
    files = sorted(glob.glob(os.path.join(folder, "**", "*.dbn*"), recursive=True))
    if not files:
        sys.exit(f"Ingen .dbn-filer i {folder}")
    parts = []
    for f in files:
        print("laeser", f)
        df = db.DBNStore.from_file(f).to_df()
        parts.append(df.reset_index()[["ts_event", "symbol", "open", "high", "low", "close", "volume"]])
    d = pd.concat(parts, ignore_index=True)
    d = d[~d.symbol.str.contains("-")]                     # ingen spreads
    d["root"] = d.symbol.str.extract(r"^(NQ|ES)")[0]
    d = d[d.root.notna()]
    d["day"] = d.ts_event.dt.tz_convert("UTC").dt.date
    for root in ("NQ", "ES"):
        x = d[d.root == root]
        # frontmaaned pr. dag = mest volumen
        front = x.groupby(["day", "symbol"]).volume.sum().reset_index().sort_values("volume").groupby("day").tail(1)
        x = x.merge(front[["day", "symbol"]], on=["day", "symbol"])
        x = x.set_index("ts_event").sort_index()
        b = x.resample("15s", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        out = pd.DataFrame({"time": b.index, "open": b.open.values, "high": b.high.values,
                            "low": b.low.values, "close": b.close.values})
        fn = f"{root}_{name}.parquet"
        out.to_parquet(fn, index=False)
        print(f"{fn}: {len(out)} bars, {out.time.min()} -> {out.time.max()}, "
              f"kontrakter: {', '.join(sorted(front.symbol.unique()))}")


if __name__ == "__main__":
    main()
