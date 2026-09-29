"""Generate fake NQ / ES tick data so the site can be tried before real data is imported.

    python tools/make_sample.py            # one week ending last Friday
    python tools/make_sample.py --days 3

Prices are a random walk on the 0.25 tick grid; activity is heavier in the
regular session (09:30-16:00 New York) and there is no trading during the
daily 17:00-18:00 break or over the weekend, like CME Globex.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.import_ticks import write_days  # noqa: E402

NY = ZoneInfo("America/New_York")
START_PRICE = {"NQ": 18000.0, "ES": 5200.0}
TICK = 0.25


def sessions(days: int) -> list[tuple[dt.datetime, dt.datetime]]:
    """Globex sessions (18:00 prev day -> 17:00) for the last `days` weekdays ending last Friday."""
    today = dt.datetime.now(NY).date()
    last_fri = today - dt.timedelta(days=(today.weekday() - 4) % 7 or 7)
    out, d = [], last_fri
    while len(out) < days:
        if d.weekday() < 5:
            prev = d - dt.timedelta(days=1)
            out.append((dt.datetime(prev.year, prev.month, prev.day, 18, tzinfo=NY),
                        dt.datetime(d.year, d.month, d.day, 17, tzinfo=NY)))
        d -= dt.timedelta(days=1)
    return out[::-1]


def gen_symbol(sym: str, sess: list, rng: np.random.Generator, rth_rate: float, eth_rate: float):
    ts_all, px_all, sz_all = [], [], []
    price = START_PRICE[sym]
    for s, e in sess:
        rth0 = dt.datetime(e.year, e.month, e.day, 9, 30, tzinfo=NY)
        rth1 = dt.datetime(e.year, e.month, e.day, 16, 0, tzinfo=NY)
        for a, b, rate in ((s, rth0, eth_rate), (rth0, rth1, rth_rate), (rth1, e, eth_rate)):
            a_ms, b_ms = int(a.timestamp() * 1000), int(b.timestamp() * 1000)
            n = rng.poisson(rate * (b_ms - a_ms) / 1000)
            ts = np.sort(rng.integers(a_ms, b_ms, n))
            steps = rng.choice([-1, 0, 1], size=n, p=[0.3, 0.4, 0.3])
            px = price + np.cumsum(steps) * TICK
            price = float(px[-1]) if n else price
            ts_all.append(ts); px_all.append(px)
            sz_all.append(np.minimum(rng.geometric(0.45, n), 50).astype(np.int32))
    return np.concatenate(ts_all), np.concatenate(px_all), np.concatenate(sz_all)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data" / "ticks")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    sess = sessions(args.days)
    for sym, rth, eth in (("NQ", 6.0, 0.8), ("ES", 4.0, 0.5)):
        ts, px, sz = gen_symbol(sym, sess, rng, rth, eth)
        n = write_days(args.out, sym, ts, px, sz)
        print(f"{sym}: {len(ts):,} ticks in {n} day files")


if __name__ == "__main__":
    main()
