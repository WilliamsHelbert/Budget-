"""
Databento OHLCV-1s -> 15-sekunders NQ- og ES-filer til backtesten.

Brug: laeg denne fil i samme mappe som Databento-zip-filerne (GLBX-....zip) og koer
    python lav_15s.py
Scriptet finder selv alle GLBX-*.zip (eller .dbn.zst) i mappen og laver for hver af dem
    NQ_<fra>_<til>.parquet  og  ES_<fra>_<til>.parquet

Virker baade med NQ.FUT/ES.FUT (alle kontrakter) og NQ.v.0/ES.v.0 (kontinuerlig).
Spreads (fx NQZ2-NQH3) smides vaek. Hver dag (UTC-dato, dvs. skift kl. 19/20 New York,
foer Asia-sessionen) bruges den kontrakt der havde mest volumen den dag.
"""
import glob
import os
import sys
import tempfile
import zipfile

import databento as db
import pandas as pd


def convert(dbn_files):
    parts = []
    for f in dbn_files:
        print("  laeser", os.path.basename(f))
        df = db.DBNStore.from_file(f).to_df()
        parts.append(df.reset_index()[["ts_event", "symbol", "open", "high", "low", "close", "volume"]])
    d = pd.concat(parts, ignore_index=True)
    d = d[~d.symbol.str.contains("-")]                     # ingen spreads
    d["root"] = d.symbol.str.extract(r"^(NQ|ES)")[0]
    d = d[d.root.notna()]
    d["day"] = d.ts_event.dt.tz_convert("UTC").dt.date
    for root in ("NQ", "ES"):
        x = d[d.root == root]
        if x.empty:
            continue
        # frontmaaned pr. dag = mest volumen
        front = x.groupby(["day", "symbol"]).volume.sum().reset_index().sort_values("volume").groupby("day").tail(1)
        x = x.merge(front[["day", "symbol"]], on=["day", "symbol"])
        x = x.set_index("ts_event").sort_index()
        b = x.resample("15s", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        out = pd.DataFrame({"time": b.index, "open": b.open.values, "high": b.high.values,
                            "low": b.low.values, "close": b.close.values})
        fn = f"{root}_{out.time.min():%Y-%m-%d}_{out.time.max():%Y-%m-%d}.parquet"
        out.to_parquet(fn, index=False)
        print(f"  -> {fn}: {len(out)} bars, kontrakter: {', '.join(sorted(front.symbol.unique()))}")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)
    zips = sorted(glob.glob("GLBX-*.zip"))
    loose = sorted(glob.glob("*.dbn.zst")) + sorted(glob.glob("*.dbn"))
    if not zips and not loose:
        sys.exit("Fandt ingen GLBX-*.zip eller .dbn.zst i " + here)
    for z in zips:
        print("zip:", z)
        with tempfile.TemporaryDirectory() as tmp:
            zipfile.ZipFile(z).extractall(tmp)
            files = sorted(glob.glob(os.path.join(tmp, "**", "*.dbn*"), recursive=True))
            if files:
                convert(files)
            else:
                print("  (ingen .dbn-filer i zip-filen)")
    if loose:
        convert(loose)
    print("Faerdig. Send NQ_*.parquet og ES_*.parquet.")


if __name__ == "__main__":
    main()
