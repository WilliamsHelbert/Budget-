"""
EQ / Equilibrium dual-asset (ES + NQ) backtest.

Port of the "EQ - Equilibrium Tracker v10" Pine script + the ES/NQ
confluence entry model.
"""
import pandas as pd, numpy as np
from dataclasses import dataclass, field

TZ = "Europe/Copenhagen"
OPEN_H, OPEN_M = 15, 30          # market open (CPH) = 09:30 NY
CLOSE_H, CLOSE_M = 22, 0         # RTH close (CPH) = 16:00 NY

R_UNIT = {"ES": 2.0, "NQ": 10.0}     # 15pts ES / 75pts NQ = 7.5R
TP_PTS = {"ES": 15.0, "NQ": 75.0}


def load(sym, path):
    df = pd.read_parquet(path)
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(TZ)
    df = df.sort_values("time").reset_index(drop=True)
    # bar timestamps are bar-OPEN times (TradingView convention)
    df["min"] = df["time"].dt.floor("1min")
    df["m5"] = df["time"].dt.floor("5min")
    df["date"] = df["time"].dt.date
    return df


def agg(df, key):
    g = df.groupby(key)
    return pd.DataFrame({
        "open": g["open"].first(), "high": g["high"].max(),
        "low": g["low"].min(), "close": g["close"].last(),
    })


@dataclass
class EQ:
    direction: str      # 'bear' | 'bull'
    anchor: float       # bear: creating 1m candle high | bull: its low
    anchor_t: pd.Timestamp
    ext: float          # running extreme (bear: lowest low, bull: highest high)
    active: bool = True

    @property
    def eq(self):
        return (self.anchor + self.ext) / 2.0


class EQTracker:
    """One per asset. Fed 15s bars in order; mirrors the Pine bar loop."""

    def __init__(self, m1):
        self.m1 = m1                 # 1m OHLC indexed by minute open
        self.bear = None
        self.bull = None
        self.last_reset_day = None
        self.hits = []               # freeze events

    def on_bar(self, b, prev_min):
        """b: a 15s bar row. prev_min: the 1m candle that just completed
        (None if this bar is not the first of a new minute)."""
        t = b["time"]
        ev = []

        # ---- market-open reset: wipes active + frozen ----
        t_min = t.hour * 60 + t.minute
        if t_min >= OPEN_H * 60 + OPEN_M and self.last_reset_day != t.date():
            self.last_reset_day = t.date()
            self.bear = None
            self.bull = None
            ev.append(("reset", None))

        pre_open = t_min < OPEN_H * 60 + OPEN_M

        # ---- growth + freeze (runs BEFORE creation, as in Pine) ----
        for side in ("bear", "bull"):
            e = getattr(self, side)
            if e is None:
                continue
            if side == "bear":
                e.ext = min(e.ext, b["low"])
                lvl = e.eq
                touched = b["high"] >= lvl
            else:
                e.ext = max(e.ext, b["high"])
                lvl = e.eq
                touched = b["low"] <= lvl
            if touched:
                # closed-over = invalid; otherwise a clean rejection off EQ
                closed_over = (b["close"] > lvl) if side == "bear" else (b["close"] < lvl)
                ev.append(("hit", dict(side=side, level=lvl, anchor=e.anchor,
                                       closed_over=closed_over, t=t)))
                setattr(self, side, None)

        # ---- creation from the just-closed 1m candle ----
        if prev_min is not None and not pre_open:
            o, h, l, c = prev_min["open"], prev_min["high"], prev_min["low"], prev_min["close"]
            eq1 = (h + l) / 2.0
            if c < o and c < eq1 and self.bear is None:
                self.bear = EQ("bear", h, prev_min.name, min(l, b["low"]))
                ev.append(("new", "bear"))
            if c > o and c > eq1 and self.bull is None:
                self.bull = EQ("bull", l, prev_min.name, max(h, b["high"]))
                ev.append(("new", "bull"))
        return ev
