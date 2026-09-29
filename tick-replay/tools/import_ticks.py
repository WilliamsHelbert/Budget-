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
      - optional best bid / ask before the trade: bid_px_00 / ask_px_00 (Databento TBBO), bid / ask
      - optional aggressor side: side (B = buyer lifted the offer, A/S = seller hit the bid)
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
BID_COLS = ["bid_px_00", "bid", "bid_price"]
ASK_COLS = ["ask_px_00", "ask", "ask_price"]
NINJA_RE = re.compile(r"^\d{8} \d{6}( \d{7})?;")


# ---- writing -----------------------------------------------------------------

def write_days(out_dir: Path, symbol: str, ts, price, size, replace: bool = True,
               bid=None, ask=None, side=None) -> int:
    """Split ticks by UTC day and write one Parquet file per day. Returns number of files written.

    bid / ask are the best quotes just before each trade (NaN when unknown); side is the
    aggressor (+1 buyer, -1 seller, 0 unknown).
    """
    n = len(ts)
    cols = {
        "ts": np.asarray(ts, np.int64),
        "price": np.asarray(price, np.float64),
        "size": np.asarray(size, np.int32),
        "bid": np.full(n, np.nan) if bid is None else np.asarray(bid, np.float64),
        "ask": np.full(n, np.nan) if ask is None else np.asarray(ask, np.float64),
        "side": np.zeros(n, np.int8) if side is None else np.asarray(side, np.int8),
    }
    order = np.argsort(cols["ts"], kind="stable")
    cols = {k: v[order] for k, v in cols.items()}

    sym_dir = Path(out_dir) / symbol
    sym_dir.mkdir(parents=True, exist_ok=True)
    day_idx = cols["ts"] // DAY_MS
    bounds = np.flatnonzero(np.r_[True, day_idx[1:] != day_idx[:-1], True])
    written = 0
    for a, b in zip(bounds[:-1], bounds[1:]):
        day_cols = {k: v[a:b] for k, v in cols.items()}
        day = np.datetime64(int(day_idx[a]), "D").astype(str)
        path = sym_dir / f"{day}.parquet"
        if path.exists() and not replace:
            old = read_day_file(path)
            day_cols = {k: np.concatenate([old[k], day_cols[k]]) for k in day_cols}
            o = np.argsort(day_cols["ts"], kind="stable")
            day_cols = {k: v[o] for k, v in day_cols.items()}
        table = pa.table({
            "ts": pa.array(day_cols["ts"], pa.int64()),
            "price": pa.array(day_cols["price"], pa.float64()),
            "size": pa.array(day_cols["size"], pa.int32()),
            "bid": pa.array(day_cols["bid"], pa.float64()),
            "ask": pa.array(day_cols["ask"], pa.float64()),
            "side": pa.array(day_cols["side"], pa.int8()),
        })
        pq.write_table(table, path, compression="zstd")
        written += 1
    return written


def read_day_file(path: Path) -> dict:
    """Load one stored day; files written before bid/ask support get empty quote columns."""
    t = pq.read_table(path)
    n = t.num_rows
    names = set(t.column_names)
    return {
        "ts": t.column("ts").to_numpy().astype(np.int64, copy=False),
        "price": t.column("price").to_numpy().astype(np.float64, copy=False),
        "size": t.column("size").to_numpy().astype(np.int32, copy=False),
        "bid": t.column("bid").to_numpy().astype(np.float64, copy=False) if "bid" in names else np.full(n, np.nan),
        "ask": t.column("ask").to_numpy().astype(np.float64, copy=False) if "ask" in names else np.full(n, np.nan),
        "side": t.column("side").to_numpy().astype(np.int8, copy=False) if "side" in names else np.zeros(n, np.int8),
    }


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
    return {"ts": ts, "price": df["last"].to_numpy(np.float64), "size": df["vol"].to_numpy(np.int64),
            "bid": df["bid"].to_numpy(np.float64), "ask": df["ask"].to_numpy(np.float64),
            "side": np.zeros(len(df), np.int8)}


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
    fixed_point = np.nanmedian(np.abs(price)) > 1e8  # Databento prices without "pretty_px"

    def prices(col: str | None) -> np.ndarray:
        if col is None:
            return np.full(len(df), np.nan)
        v = pd.to_numeric(df[col], errors="coerce").to_numpy(np.float64, copy=True)
        if fixed_point:
            v = v / 1e9
        v[np.abs(v) >= 1e8] = np.nan  # Databento's "undefined price" sentinel
        return v

    price = prices(px_col)
    bid = prices(next((c for c in BID_COLS if c in cols), None))
    ask = prices(next((c for c in ASK_COLS if c in cols), None))

    sz_col = next((c for c in SIZE_COLS if c in cols), None)
    size = df[sz_col].to_numpy(np.int64) if sz_col else np.ones(len(df), np.int64)

    side = np.zeros(len(df), np.int8)
    if "side" in cols:
        sv = df["side"].astype(str).str.strip().str.upper()
        side[sv.isin(["B", "BUY", "1"]).to_numpy()] = 1
        side[sv.isin(["A", "S", "SELL", "-1"]).to_numpy()] = -1

    keep = front_contract_mask(df, ts, size)
    return {"ts": ts[keep], "price": price[keep], "size": size[keep],
            "bid": bid[keep], "ask": ask[keep], "side": side[keep]}


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
    """(ts, price, size) arrays of a tick file."""
    t = read_ticks(path, tz)
    return t["ts"], t["price"], t["size"]


def clean(t: dict) -> dict:
    """Drop rows without a usable trade price."""
    ok = ~np.isnan(t["price"]) & (t["price"] > 0)
    return {k: v[ok] for k, v in t.items()}


def concat(parts: list[dict]) -> dict:
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def read_ticks(path: Path, tz: str) -> dict:
    """All columns of a tick file: ts, price, size, bid, ask, side."""
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
        return read_ticks(plain, tz)
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

    parts = []
    for p in args.files:
        parts.append(clean(read_ticks(p, args.tz)))
        print(f"{p}: {len(parts[-1]['ts']):,} ticks")
    t = concat(parts)
    ts = t["ts"]
    if not len(ts):
        raise SystemExit("nothing to import")

    n = write_days(args.out, args.symbol.upper(), ts, t["price"], t["size"], replace=args.replace,
                   bid=t["bid"], ask=t["ask"], side=t["side"])
    fmt = lambda ms: np.datetime64(int(ms), "ms").astype(str) + "Z"  # noqa: E731
    print(f"{args.symbol.upper()}: {len(ts):,} ticks, {fmt(ts.min())} -> {fmt(ts.max())}, {n} day files")
    print("Check the first/last times above against your source (UTC). If they are off by hours, re-run with --tz.")


if __name__ == "__main__":
    main()
