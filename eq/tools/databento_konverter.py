#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Databento OHLCV-1s  ->  15s-barer klar til EQ-konfluensmodellen.

Kraever:   pip install databento pandas pyarrow
Koersel:   python databento_konverter.py "C:\\sti\\til\\GLBX-....zip"
      ell: python databento_konverter.py "C:\\sti\\til\\udpakket_mappe"

Laver ES_15s.parquet og NQ_15s.parquet ved siden af scriptet.
"""
import sys, os, glob, zipfile, io
import pandas as pd
import databento as db

TZ_NY   = "America/New_York"
SESSION = (9*60+25, 16*60+5)     # lidt margen om 09:30-16:00 NY
BAR_SEC = 15


def indlaes_kilder(sti):
    """-> liste af (navn, DBNStore)"""
    ud = []
    if os.path.isfile(sti) and sti.lower().endswith(".zip"):
        z = zipfile.ZipFile(sti)
        navne = [n for n in z.namelist() if n.endswith((".dbn.zst", ".dbn"))]
        print("Zip indeholder %d datafil(er): %s" % (len(navne), navne))
        for n in navne:
            ud.append((os.path.basename(n), db.DBNStore.from_bytes(z.read(n))))
    else:
        filer = sorted(glob.glob(os.path.join(sti, "**", "*.dbn.zst"), recursive=True) +
                       glob.glob(os.path.join(sti, "**", "*.dbn"), recursive=True))
        print("Fandt %d datafil(er)" % len(filer))
        for f in filer:
            ud.append((os.path.basename(f), db.DBNStore.from_file(f)))
    return ud


def main(sti):
    if not os.path.exists(sti):
        print("Findes ikke:", sti); return
    kilder = indlaes_kilder(sti)
    if not kilder:
        print("Ingen .dbn/.dbn.zst fundet i", sti); return

    dele = []
    for i, (navn, store) in enumerate(kilder, 1):
        print("  [%d/%d] laeser %s ..." % (i, len(kilder), navn), flush=True)
        d = store.to_df()
        if d.empty:
            print("     tom"); continue
        d = d.reset_index()

        tcol = next((c for c in ("ts_event", "ts_recv", "index") if c in d.columns), None)
        scol = next((c for c in ("symbol", "raw_symbol") if c in d.columns), None)
        if tcol is None or scol is None:
            print("     !! uventede kolonner:", list(d.columns)); continue

        d = d.assign(time=pd.to_datetime(d[tcol], utc=True), sym=d[scol].astype(str))
        d = d[~d.sym.str.contains("-", regex=False)]          # spreads vaek
        ny  = d.time.dt.tz_convert(TZ_NY)
        tod = ny.dt.hour * 60 + ny.dt.minute
        d = d[(tod >= SESSION[0]) & (tod < SESSION[1])]       # kun RTH
        if d.empty:
            print("     ingen RTH-raekker"); continue

        keep = ["time", "sym", "open", "high", "low", "close"]
        if "volume" in d.columns: keep.append("volume")
        dele.append(d[keep])
        print("     %d raekker beholdt" % len(d))

    if not dele:
        print("Ingen raekker tilbage efter filtrering"); return
    alle = pd.concat(dele, ignore_index=True)
    print("I alt efter filtrering: %d raekker" % len(alle))

    alle["bucket"] = alle.time.dt.floor("%ds" % BAR_SEC)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in alle.columns: agg["volume"] = "sum"
    ud = (alle.sort_values("time")
              .groupby(["sym", "bucket"], as_index=False)
              .agg(agg)
              .rename(columns={"bucket": "time"}))

    for pre, fil in (("ES", "ES_15s.parquet"), ("NQ", "NQ_15s.parquet")):
        m = ud[ud.sym.str.match(r"^%s[A-Z]\d+$" % pre)]       # ESH5 osv, ikke MES
        if m.empty:
            print("  %s: ingen raekker - fundne symboler: %s"
                  % (pre, sorted(ud.sym.unique())[:20])); continue
        m = m.sort_values(["time", "sym"]).reset_index(drop=True)
        m.to_parquet(fil, index=False)
        print("  %-16s %7d barer   %s .. %s   %.1f MB   kontrakter: %s"
              % (fil, len(m), m.time.min(), m.time.max(),
                 os.path.getsize(fil) / 1e6, sorted(m.sym.unique())))
    print("\nFaerdig. Upload de to .parquet-filer.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
