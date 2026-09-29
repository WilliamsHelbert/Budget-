import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server.store import Store  # noqa: E402
from tools.import_ticks import read_any, write_days  # noqa: E402

T0 = int(dt.datetime(2024, 3, 5, 14, 30, tzinfo=dt.timezone.utc).timestamp() * 1000)


@pytest.fixture
def store(tmp_path):
    ts = np.array([T0, T0 + 10, T0 + 10, T0 + 10, T0 + 999, T0 + 1000, T0 + 61_000, T0 + 86_400_000])
    px = np.array([100.0, 101, 99, 100.5, 102, 98, 105, 110])
    sz = np.array([1, 2, 3, 4, 5, 6, 7, 8])
    write_days(tmp_path, "NQ", ts, px, sz)
    return Store(tmp_path)


def test_symbols(store):
    (s,) = store.symbols()
    assert s["symbol"] == "NQ" and s["point_value"] == 20.0
    assert s["first_ts"] == T0 and s["last_ts"] == T0 + 86_400_000
    assert len(s["days"]) == 2


def test_ticks_window_is_after_exclusive_until_inclusive(store):
    r = store.ticks("NQ", T0, T0 + 1000, 100)
    assert r["ts"] == [T0 + 10] * 3 + [T0 + 999, T0 + 1000]
    assert r["covered_until"] == T0 + 1000


def test_ticks_limit_never_splits_a_millisecond(store):
    r = store.ticks("NQ", T0 - 1, T0 + 5000, 2)  # limit lands inside the 3 ticks at T0+10
    assert r["ts"] == [T0]
    assert r["covered_until"] == T0 + 9
    r2 = store.ticks("NQ", r["covered_until"], T0 + 5000, 2)  # all 3 same-ms ticks come together
    assert r2["ts"] == [T0 + 10] * 3


def test_ticks_across_days_and_gap_hint(store):
    r = store.ticks("NQ", T0 + 61_000, T0 + 120_000, 100)
    assert r["ts"] == [] and r["next_ts"] == T0 + 86_400_000
    r = store.ticks("NQ", T0 - 1, T0 + 90_000_000, 100)
    assert len(r["ts"]) == 8


def test_candles_partial_last_bar(store):
    c = store.candles("NQ", 60, T0 + 999, 10)  # replay time mid-second, mid-minute
    assert len(c) == 1
    assert c[0] == {"time": T0 // 1000, "open": 100.0, "high": 102.0, "low": 99.0, "close": 102.0, "volume": 15.0}
    c = store.candles("NQ", 60, T0 + 61_000, 10)
    assert [x["close"] for x in c] == [98.0, 105.0]
    c = store.candles("NQ", 1, T0 + 1000, 10)
    assert [x["time"] for x in c] == [T0 // 1000, T0 // 1000 + 1]


def test_candles_count(store):
    c = store.candles("NQ", 1, T0 + 86_400_000, 2)
    assert [x["close"] for x in c] == [105.0, 110.0]


def test_import_ninjatrader(tmp_path):
    f = tmp_path / "NQ.txt"
    f.write_text("20240305 093000 1230000;18123.25;18123;18123.25;2\n20240305 093000 5000000;18123.5;18123.25;18123.5;1\n")
    ts, px, sz = read_any(f, "America/New_York")
    assert list(ts) == [T0 + 123, T0 + 500]
    assert list(px) == [18123.25, 18123.5] and list(sz) == [2, 1]


def test_import_csv_variants(tmp_path):
    a = tmp_path / "a.csv"
    a.write_text("ts_event,price,size\n1709649000123000000,18123250000000,2\n")  # databento ns + fixed-point
    ts, px, sz = read_any(a, "UTC")
    assert list(ts) == [T0 + 123] and list(px) == [18123.25] and list(sz) == [2]

    b = tmp_path / "b.csv"
    b.write_text("Date, Time, Open, High, Low, Last, Volume\n2024/3/5, 09:30:00.123, 1,1,1, 18000.5, 3\n")  # Sierra Chart
    ts, px, sz = read_any(b, "America/New_York")
    assert list(ts) == [T0 + 123] and list(px) == [18000.5] and list(sz) == [3]

    c = tmp_path / "c.csv"
    c.write_text("timestamp,price,volume\n2024-03-05T14:30:00.123Z,1.5,4\n")
    ts, px, sz = read_any(c, "America/New_York")  # explicit offset wins over --tz
    assert list(ts) == [T0 + 123]


DB_HEADER = "ts_recv,ts_event,rtype,publisher_id,instrument_id,action,side,depth,price,size,flags,ts_in_delta,sequence,symbol\n"


def _db_row(ms_offset, inst, px, sz, sym):
    ns = (T0 + ms_offset) * 1_000_000
    return f"{ns},{ns},0,1,{inst},T,A,0,{int(px * 1e9)},{sz},0,0,0,{sym}\n"


def test_databento_parent_download_keeps_front_contract(tmp_path):
    rows = [
        _db_row(0, 1, 18000.25, 5, "NQZ6"),       # front month, most volume
        _db_row(5, 2, 18250.00, 1, "NQH7"),       # back month
        _db_row(7, 3, 250.25, 40, "NQZ6-NQH7"),   # calendar spread (big size, must still be dropped)
        _db_row(9, 1, 18000.50, 3, "NQZ6"),
    ]
    f = tmp_path / "glbx-mdp3-trades.csv"
    f.write_text(DB_HEADER + "".join(rows))
    ts, px, sz = read_any(f, "UTC")
    assert list(px) == [18000.25, 18000.5] and list(ts) == [T0, T0 + 9]


def test_databento_zst_and_dbn(tmp_path):
    import zstandard
    raw = (DB_HEADER + _db_row(0, 1, 18000.25, 5, "NQZ6")).encode()
    f = tmp_path / "glbx-mdp3-20240305.trades.csv.zst"
    f.write_bytes(zstandard.ZstdCompressor().compress(raw))
    ts, px, sz = read_any(f, "UTC")
    assert list(px) == [18000.25] and list(ts) == [T0]
    assert not (tmp_path / "glbx-mdp3-20240305.trades.csv").exists()  # temp file cleaned up

    d = tmp_path / "x.trades.dbn.zst"
    d.write_bytes(b"DBN")
    with pytest.raises(SystemExit, match="Encoding = CSV"):
        read_any(d, "UTC")
