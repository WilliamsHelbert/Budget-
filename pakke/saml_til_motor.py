#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mellemtrinnet mellem databento_konverter3.py og eq_model.py.

Konverteren skriver ES_2025.parquet med kolonnen `ts` (epoch-sekunder) og
priser som HELTAL I TICKS. Motoren laeser ES.parquet med kolonnen `time`
(UTC-datetime) og priser i RIGTIGE POINT. Denne fil oversaetter.

    python saml_til_motor.py <mappe-med-aarsfiler> [<udmappe>]

Samler ES_*.parquet / NQ_*.parquet (inkl. _del1/_del2 fra del_op.py),
sorterer paa tid, fjerner dubletter og skriver ES.parquet + NQ.parquet.

Heltalskolonner ganges med 0,25. Float-kolonner staar allerede i point
(konverterens fallback naar en pris ikke ligger paa tick) og roeres ikke.
"""
import sys, os, glob
import pandas as pd

TICK  = 0.25
KOL   = ("open", "high", "low", "close")
GRAENSER = {"ES": (1000, 15000), "NQ": (3000, 60000)}   # sund fornuft, ikke en regel


def saml(mappe, pre):
    filer = sorted(f for f in glob.glob(os.path.join(mappe, "%s_*.parquet" % pre))
                   if not os.path.basename(f).startswith("%s.parquet" % pre))
    if not filer:
        print("  %s: ingen %s_*.parquet i %s" % (pre, pre, mappe)); return None
    dele = []
    for f in filer:
        d = pd.read_parquet(f)
        print("     %-28s %8d raekker" % (os.path.basename(f), len(d)))
        dele.append(d)
    d = pd.concat(dele, ignore_index=True)

    if "ts" in d.columns:
        t = pd.to_datetime(d["ts"].astype("int64"), unit="s", utc=True)
    elif "time" in d.columns:
        t = pd.to_datetime(d["time"], utc=True)
    else:
        print("  %s: hverken ts eller time i kolonnerne: %s" % (pre, list(d.columns)))
        return None

    ud = pd.DataFrame({"time": t})
    for k in KOL:
        if k not in d.columns:
            print("  %s: mangler kolonnen %s" % (pre, k)); return None
        s = d[k]
        # heltal = ticks fra konverteren. float = allerede point.
        ud[k] = s.astype("float64") * TICK if pd.api.types.is_integer_dtype(s) \
                else s.astype("float64")

    ud = (ud.sort_values("time")
            .drop_duplicates(subset="time", keep="last")
            .reset_index(drop=True))
    return ud


def tjek(pre, d):
    lo, hi = GRAENSER[pre]
    mn, mx = float(d[list(KOL)].min().min()), float(d[list(KOL)].max().max())
    dk = d["time"].dt.tz_convert("Europe/Copenhagen")
    dage = dk.dt.strftime("%Y-%m-%d").nunique()
    mins = (dk.dt.hour*60 + dk.dt.minute)
    print("  %s: %d barer, %d dage, %s .. %s"
          % (pre, len(d), dage, d["time"].min(), d["time"].max()))
    print("     pris %.2f .. %.2f | doegndaekning dansk tid %02d:%02d .. %02d:%02d"
          % (mn, mx, mins.min()//60, mins.min() % 60, mins.max()//60, mins.max() % 60))
    if not (lo <= mn and mx <= hi):
        print("     !! priserne ligger uden for %d-%d. Er tick-ganget forkert?" % (lo, hi))
    if mins.min() > 2*60 or mins.max() < 22*60+10:
        print("     !! daekker ikke 02:00-22:10 dansk tid. Et RTH-klippet saet"
              " virker som et skjult ekstrafilter.")
    steps = d["time"].diff().dt.total_seconds().dropna()
    if len(steps) and steps.mod(15).ne(0).any():
        print("     !! ikke alle afstande er hele 15 sekunder")


def main(mappe, udmappe=None):
    udmappe = udmappe or mappe
    os.makedirs(udmappe, exist_ok=True)
    for pre in ("ES", "NQ"):
        print("\n%s:" % pre)
        d = saml(mappe, pre)
        if d is None: continue
        tjek(pre, d)
        fil = os.path.join(udmappe, "%s.parquet" % pre)
        d.to_parquet(fil, index=False, compression="zstd")
        print("     skrevet: %s  (%.1f MB)" % (fil, os.path.getsize(fil)/1e6))
    print("\nKoer nu:  python koer_alt.py %s" % udmappe)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
