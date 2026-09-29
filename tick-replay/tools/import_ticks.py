"""Import tick data (CSV / TXT) into the replay's Parquet store.

    python tools/import_ticks.py --symbol NQ path/to/file.csv [more files...] [--tz America/New_York]

Recognised inputs:

* NinjaTrader tick export (.txt, no header):
      20240305 093000 1230000;18123.25;18123;18123.25;2
      (date time 100ns-fraction;last;bid;ask;volume)
* Any CSV with a header row containing
      - a timestamp column: ts, ts_event, ts_recv, timestamp, time, datetime, date_time
        or separate "date" and "time" columns (e.g. Sierra Chart exports)
      - a price column: price, last, close, trade_price
      - optional size column: size, volume, qty, quantity, vol, last_size
  Numeric timestamps are treated as epoch UTC (s / ms / us / ns detected from magnitude).
  Text timestamps without an offset are read in --tz (default UTC).
  Databento CSVs with fixed-point prices (1e-9 units) are rescaled automatically.

Each UTC day covered by the import is (re)written as data/ticks/<SYMBOL>/<YYYY-MM-DD>.parquet.
Days already on disk are merged with the new ticks unless --replace is given.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

DAY_MS = 86_400_000
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "ticks"

TS_COLS = ["ts", "ts_event", "ts_recv", "timestamp", "time", "datetime", "date_time"]
PRICE_COLS = ["price", "last", "close", "trade_price"]
SIZE_COLS = ["size", "volume", "qty", "quantity", "vol", "last_size"]
NINJA_RE = re.compile(r"^\d{8} \d{6}( \d{7})?;")


# ---- writing -----------------------------------------------------------------

def write_days(out_dir: Path, symbol: str, ts, price, size, replace: bool = True) -> int:
    """Split ticks by UTC day and write one Parquet file per day. Returns number of files written."""
    ts = np.asarray(ts, np.int64)
    price = np.asarray(price, np.float64)
    size = np.asarray(size, np.int32)
    order = np.argsort(ts, kind="stable")
    ts, price, size = ts[order], price[order], size[order]

    sym_dir = Path(out_dir) / symbol
    sym_dir.mkdir(parents=True, exist_ok=True)
    day_idx = ts // DAY_MS
    bounds = np.flatnonzero(np.r_[True, day_idx[1:] != day_idx[:-1], True])
    written = 0
    for a, b in zip(bounds[:-1], bounds[1:]):
        d_ts, d_px, d_sz = ts[a:b], price[a:b], size[a:b]
        day = np.datetime64(int(day_idx[a]), "D").astype(str)
        path = sym_dir / f"{day}.parquet"
        if path.exists() and not replace:
            old = pq.read_table(path)
            d_ts = np.concatenate([old.column("ts").to_numpy(), d_ts])
            d_px = np.concatenate([old.column("price").to_numpy(), d_px])
            d_sz = np.concatenate([old.column("size").to_numpy(), d_sz])
            o = np.argsort(d_ts, kind="stable")
            d_ts, d_px, d_sz = d_ts[o], d_px[o], d_sz[o]
        table = pa.table({"ts": pa.array(d_ts, pa.int64()),
                          "price": pa.array(d_px, pa.float64()),
                          "size": pa.array(d_sz, pa.int32())})
        pq.write_table(table, path, compression="zstd")
        written += 1
    return written


# ---- reading -----------------------------------------------------------------

def _epoch_to_ms(values: np.ndarray) -> np.ndarray:
    v = values.astype(np.float64)
    mag = np.nanmedian(np.abs(v))
    if mag > 1e17:
        return (values.astype(np.int64) // 1_000_000)  # ns
    if mag > 1e14:
        return (values.astype(np.int64) // 1_000)  # us
    if mag > 1e11:
        return values.astype(np.int64)  # ms
    return np.round(v * 1000).astype(np.int64)  # s


def _text_to_ms(series, tz: str) -> np.ndarray:
    import pandas as pd

    t = pd.to_datetime(series, format="mixed", utc=False)
    if t.dt.tz is None:
        t = t.dt.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    return t.dt.tz_convert("UTC").dt.as_unit("ms").astype("int64").to_numpy()


def read_ninjatrader(path: Path, tz: str):
    import pandas as pd

    df = pd.read_csv(path, sep=";", header=None, names=["dt", "last", "bid", "ask", "vol"], dtype={"dt": str})
    parts = df["dt"].str.split(" ", expand=True)
    frac = parts[2].fillna("0000000") if parts.shape[1] > 2 else "0000000"
    text = parts[0] + " " + parts[1] + "." + frac
    ts = _text_to_ms(pd.Series(pd.to_datetime(text, format="%Y%m%d %H%M%S.%f")), tz)
    return ts, df["last"].to_numpy(np.float64), df["vol"].to_numpy(np.int64)


def read_csv(path: Path, tz: str):
    import pandas as pd

    df = pd.read_csv(path, sep=None, engine="python") if path.suffix.lower() == ".txt" else pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    cols = set(df.columns)

    ts_col = next((c for c in TS_COLS if c in cols), None)
    if "date" in cols and "time" in cols:
        ts = _text_to_ms(df["date"].astype(str).str.strip() + " " + df["time"].astype(str).str.strip(), tz)
    elif ts_col is not None:
        col = df[ts_col]
        if pd.api.types.is_numeric_dtype(col):
            ts = _epoch_to_ms(col.to_numpy())
        else:
            ts = _text_to_ms(col.astype(str).str.strip(), tz)
    else:
        raise SystemExit(f"{path}: no timestamp column found (have {sorted(cols)})")

    px_col = next((c for c in PRICE_COLS if c in cols), None)
    if px_col is None:
        raise SystemExit(f"{path}: no price column found (have {sorted(cols)})")
    price = df[px_col].to_numpy(np.float64, copy=True)
    if np.nanmedian(np.abs(price)) > 1e8:  # Databento fixed-point prices
        price = price / 1e9
    price[np.abs(price) >= 1e8] = np.nan  # Databento's "undefined price" sentinel

    sz_col = next((c for c in SIZE_COLS if c in cols), None)
    size = df[sz_col].to_numpy(np.int64) if sz_col else np.ones(len(df), np.int64)

    keep = front_contract_mask(df, ts, size)
    return ts[keep], price[keep], size[keep]


def front_contract_mask(df, ts: np.ndarray, size: np.ndarray) -> np.ndarray:
    """Keep only the most-traded outright contract of each day.

    A Databento "parent" download (e.g. NQ.FUT) holds every expiry plus calendar
    spreads in one file; mixing them would make the chart jump between prices.
    Picking the highest-volume contract per day is what Databento's NQ.v.0 does.
    """
    import pandas as pd

    inst_col = next((c for c in ("instrument_id", "symbol") if c in df.columns), None)
    keep = np.ones(len(df), bool)
    if inst_col is None or df[inst_col].nunique() <= 1:
        return keep
    if "symbol" in df.columns:  # spreads look like "NQZ6-NQH7"
        keep &= ~df["symbol"].astype(str).str.contains(r"[-: ]", regex=True).to_numpy()
    frame = pd.DataFrame({"day": ts // DAY_MS, "inst": df[inst_col].to_numpy(), "size": size})[keep]
    vol = frame.groupby(["day", "inst"])["size"].sum()
    top = vol.loc[vol.groupby(level="day").idxmax()].index  # (day, inst) pairs to keep
    chosen = pd.MultiIndex.from_arrays([ts // DAY_MS, df[inst_col].to_numpy()]).isin(top)
    return keep & chosen


def read_any(path: Path, tz: str):
    path = Path(path)
    name = path.name.lower()
    if ".dbn" in name:
        raise SystemExit(f"{path.name}: this is Databento's binary format (DBN). "
                         "Download again with Encoding = CSV.")
    if name.endswith(".zst"):
        return _read_zst(path, tz)
    with open(path, "r", errors="replace") as f:
        first = f.readline()
    if NINJA_RE.match(first):
        return read_ninjatrader(path, tz)
    return read_csv(path, tz)


def _read_zst(path: Path, tz: str):
    """Databento compresses downloads with zstd (file.csv.zst): unpack next to it, then read."""
    import zstandard

    plain = path.with_name(path.name[:-4])  # drop ".zst"
    if plain.suffix.lower() not in (".csv", ".txt"):
        plain = plain.with_name(plain.name + ".csv")
    with open(path, "rb") as src, open(plain, "wb") as dst:
        zstandard.ZstdDecompressor().copy_stream(src, dst)
    try:
        return read_any(plain, tz)
    finally:
        plain.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--symbol", required=True, help="e.g. NQ or ES")
    ap.add_argument("--tz", default="UTC", help="timezone of timestamps without an offset (default UTC)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--replace", action="store_true", help="overwrite existing day files instead of merging")
    args = ap.parse_args()

    ts_l, px_l, sz_l = [], [], []
    for p in args.files:
        ts, px, sz = read_any(p, args.tz)
        ok = ~(np.isnan(px)) & (px > 0)
        ts_l.append(ts[ok]); px_l.append(px[ok]); sz_l.append(sz[ok])
        print(f"{p}: {ok.sum():,} ticks")
    ts, px, sz = np.concatenate(ts_l), np.concatenate(px_l), np.concatenate(sz_l)
    if not len(ts):
        raise SystemExit("nothing to import")

    n = write_days(args.out, args.symbol.upper(), ts, px, sz, replace=args.replace)
    fmt = lambda ms: np.datetime64(int(ms), "ms").astype(str) + "Z"  # noqa: E731
    print(f"{args.symbol.upper()}: {len(ts):,} ticks, {fmt(ts.min())} -> {fmt(ts.max())}, {n} day files")
    print("Check the first/last times above against your source (UTC). If they are off by hours, re-run with --tz.")


if __name__ == "__main__":
    main()
