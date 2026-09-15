#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Databento OHLCV-1s  ->  15s-barer, ET AAR PR. FIL, under 30 MB.

Aendringer i forhold til version 1:
  * INTET RTH-filter. Beholder 02:00-22:10 dansk tid, saa Asien og London
    kommer med (SMT-modellen har brug for dem).
  * Ruller selv til frontkontrakten efter volumen, saa der kun ligger
    EEN serie i filen i stedet for alle kvartalskontrakter.
  * Gemmer tid som int32 sekunder og priser som int32 ticks (pris x 4).
    Helt tabsfrit for ES og NQ, men fylder en tredjedel.
  * Deler op pr. kalenderaar.

Resultat: ca. 11 MB pr. aar pr. symbol. ES+NQ for et helt aar ligger
paa ca. 22 MB, altsaa under graensen i en enkelt upload.

Kraever:   pip install databento pandas pyarrow
Koersel:   python databento_konverter2.py "C:\\sti\\til\\GLBX-....zip"
      ell: python databento_konverter2.py "C:\\sti\\til\\udpakket_mappe"

Skriver:   ES_2023.parquet, NQ_2023.parquet, ES_2024.parquet, ...
"""
import sys, os, glob, zipfile, re
import numpy as np
import pandas as pd
import databento as db

TZ_DK    = "Europe/Copenhagen"
DAG_FRA  = 2*60          # 02:00 dansk - Asien-sessionen starter
DAG_TIL  = 22*60 + 10    # 22:10 dansk - lidt efter NY-luk
BAR_SEC  = 15
TICK     = 0.25


def indlaes_kilder(sti):
    ud = []
    if os.path.isfile(sti) and sti.lower().endswith(".zip"):
        z = zipfile.ZipFile(sti)
        navne = [n for n in z.namelist() if n.endswith((".dbn.zst", ".dbn"))]
        print("Zip indeholder %d datafil(er)" % len(navne))
        for n in navne:
            ud.append((os.path.basename(n), db.DBNStore.from_bytes(z.read(n))))
    else:
        filer = sorted(glob.glob(os.path.join(sti, "**", "*.dbn.zst"), recursive=True) +
                       glob.glob(os.path.join(sti, "**", "*.dbn"), recursive=True))
        print("Fandt %d datafil(er)" % len(filer))
        for f in filer:
            ud.append((os.path.basename(f), db.DBNStore.from_file(f)))
    return ud


MDR = "FGHJKMNQUVXZ"          # CME-maanedskoder, jan..dec

def udloeb(sym, pre):
    """ESH5 -> (2025, 3). Bruges til at sikre at rulningen kun gaar fremad."""
    m = re.match(r"^%s([%s])(\d{1,2})$" % (pre, MDR), sym)
    if not m: return None
    mnd = MDR.index(m.group(1)) + 1
    aar = int(m.group(2))
    aar += 2030 if aar < 10 else 2000       # 5 -> 2025, 24 -> 2024
    if aar > 2040: aar -= 10
    return (aar, mnd)


def rul(d, pre):
    """Vaelger frontkontrakten pr. dag efter volumen. Ruller aldrig tilbage."""
    if "volume" not in d.columns:
        d = d.assign(volume=1)
    dag = d.groupby(["dato", "sym"], as_index=False)["volume"].sum()
    dag["rang"] = dag.sym.map(lambda s: udloeb(s, pre))
    dag = dag[dag.rang.notna()]
    valg = {}
    sidst = None
    for dt, g in dag.sort_values("dato").groupby("dato", sort=True):
        g = g.sort_values("volume", ascending=False)
        v = g.iloc[0]
        if sidst is not None and v.rang < sidst:        # aldrig tilbage
            g2 = g[g.rang >= sidst]
            if g2.empty: continue
            v = g2.iloc[0]
        valg[dt] = v.sym; sidst = v.rang
    print("  %s: %d handelsdage, %d kontrakter" % (pre, len(valg), len(set(valg.values()))))
    ser = d.dato.map(valg)
    return d[(ser.notna()) & (d.sym == ser)]


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
        d = d[~d.sym.str.contains("-", regex=False)]            # spreads vaek
        dk  = d.time.dt.tz_convert(TZ_DK)
        tod = dk.dt.hour * 60 + dk.dt.minute
        d = d[(tod >= DAG_FRA) & (tod < DAG_TIL)]               # dropper 22:10-02:00
        if d.empty:
            print("     ingen raekker i vinduet"); continue
        keep = ["time", "sym", "open", "high", "low", "close"]
        if "volume" in d.columns: keep.append("volume")
        dele.append(d[keep])
        print("     %d raekker beholdt" % len(d))

    if not dele:
        print("Ingen raekker tilbage"); return
    alle = pd.concat(dele, ignore_index=True)
    alle["dato"] = alle.time.dt.tz_convert(TZ_DK).dt.normalize()
    print("I alt: %d raekker" % len(alle))

    alle["bucket"] = alle.time.dt.floor("%ds" % BAR_SEC)
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in alle.columns: agg["volume"] = "sum"
    bar = (alle.sort_values("time")
               .groupby(["sym", "bucket", "dato"], as_index=False)
               .agg(agg)
               .rename(columns={"bucket": "time"}))

    skrevet = []
    for pre in ("ES", "NQ"):
        m = bar[bar.sym.str.match(r"^%s[%s]\d{1,2}$" % (pre, MDR))]
        if m.empty:
            print("  %s: ingen raekker - fundne symboler: %s"
                  % (pre, sorted(bar.sym.unique())[:20])); continue
        m = rul(m, pre).sort_values("time").reset_index(drop=True)

        ud = pd.DataFrame({"ts": (m.time.astype("int64") // 10**9).astype("int32")})
        for k in ("open", "high", "low", "close"):
            t = (m[k] / TICK).round()
            if not np.allclose(t, m[k] / TICK, atol=1e-6):
                print("     !! %s.%s ligger ikke paa tick - gemmer som float32" % (pre, k))
                ud[k] = m[k].astype("float32")
            else:
                ud[k] = t.astype("int32")

        aar = m.time.dt.tz_convert(TZ_DK).dt.year
        for y in sorted(aar.unique()):
            del_ = ud[(aar == y).values]
            fil = "%s_%d.parquet" % (pre, y)
            del_.to_parquet(fil, index=False, compression="zstd")
            mb = os.path.getsize(fil) / 1e6
            skrevet.append((fil, len(del_), mb))
            print("  %-18s %7d barer   %5.1f MB %s"
                  % (fil, len(del_), mb, "  <-- OVER 30 MB!" if mb > 30 else ""))

    print("\nFaerdig. %d filer:" % len(skrevet))
    for f, n, mb in skrevet:
        print("   %-18s %5.1f MB" % (f, mb))
    print("\nUpload dem et aar ad gangen. Er en enkelt fil stadig for stor,")
    print("koer:  python del_op.py %s_2025.parquet 25" % "NQ")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
