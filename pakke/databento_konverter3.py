#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Databento OHLCV-1s  ->  15s-barer, et aar pr. fil, under 30 MB.

Koersel (peg paa zip'en ELLER den udpakkede mappe):
    python databento_konverter3.py "C:\\Users\\dig\\Overfoersler\\GLBX-20260915-V9QBJHNX9X.zip"
    python databento_konverter3.py "C:\\Users\\dig\\Overfoersler\\GLBX-20260915-V9QBJHNX9X"

Kraever:  pip install databento pandas pyarrow zstandard

Hvad den goer:
  * Laeser i bidder af 2 mio. raekker ad gangen. En .zst paa 44 MB pakker ud
    til flere GB, saa hele filen kan ikke ligge i hukommelsen paa en gang.
  * INTET RTH-filter. Beholder 02:00-22:10 dansk tid, saa Asien og London
    kommer med (SMT har brug for dem).
  * Ruller selv til frontkontrakten efter dagsvolumen, aldrig tilbage.
  * Gemmer tid som int32 sekunder og priser som int32 ticks (pris x 4).
    Tabsfrit for ES og NQ, fylder en tredjedel af float64.
  * Deler op pr. kalenderaar -> ca. 11 MB pr. aar pr. symbol.

Skriver:  ES_2024.parquet, NQ_2024.parquet, ES_2025.parquet, ...
"""
import sys, os, glob, zipfile, re
import numpy as np
import pandas as pd
import databento as db

TZ_DK   = "Europe/Copenhagen"
DAG_FRA = 2*60           # 02:00 dansk - Asien aabner
DAG_TIL = 22*60 + 10     # 22:10 dansk - lidt efter NY luk
BAR_SEC = 15
TICK    = 0.25
BID     = 2_000_000      # raekker pr. bid. Saenk til 500_000 hvis RAM'en klager.
MDR     = "FGHJKMNQUVXZ"


def indlaes_kilder(sti):
    ud = []
    if os.path.isfile(sti) and sti.lower().endswith(".zip"):
        z = zipfile.ZipFile(sti)
        navne = [n for n in z.namelist()
                 if n.endswith((".dbn.zst", ".dbn")) or
                    (n.endswith(".zst") and "ohlcv" in n.lower())]
        print("Zip indeholder %d datafil(er): %s" % (len(navne), navne))
        for n in navne:
            ud.append((os.path.basename(n), lambda n=n: db.DBNStore.from_bytes(z.read(n))))
    else:
        filer = sorted(set(
            glob.glob(os.path.join(sti, "**", "*.dbn.zst"), recursive=True) +
            glob.glob(os.path.join(sti, "**", "*.dbn"),     recursive=True) +
            [f for f in glob.glob(os.path.join(sti, "**", "*.zst"), recursive=True)
             if "ohlcv" in os.path.basename(f).lower()]))
        print("Fandt %d datafil(er)" % len(filer))
        for f in filer:
            ud.append((os.path.basename(f), lambda f=f: db.DBNStore.from_file(f)))
    return ud


def udloeb(sym, pre):
    """ESH5 -> (2025, 3). Bruges til at sikre at rulningen kun gaar fremad."""
    m = re.match(r"^%s([%s])(\d{1,2})$" % (pre, MDR), sym)
    if not m: return None
    mnd = MDR.index(m.group(1)) + 1
    aar = int(m.group(2))
    aar += 2030 if aar < 10 else 2000
    if aar > 2040: aar -= 10
    return (aar, mnd)


def bearbejd(d):
    """En bid raa 1s-data -> 15s-delaggregat. Returnerer None hvis intet tilbage."""
    d = d.reset_index()
    tcol = next((c for c in ("ts_event", "ts_recv", "index") if c in d.columns), None)
    scol = next((c for c in ("symbol", "raw_symbol") if c in d.columns), None)
    if tcol is None or scol is None:
        print("     !! uventede kolonner:", list(d.columns)); return None
    d = d.assign(time=pd.to_datetime(d[tcol], utc=True), sym=d[scol].astype(str))
    d = d[~d.sym.str.contains("-", regex=False)]                 # spreads vaek
    if d.empty: return None
    d = d[d.sym.str.match(r"^(ES|NQ)[%s]\d{1,2}$" % MDR)]        # kun ES/NQ, ikke MES/MNQ
    if d.empty: return None
    dk  = d.time.dt.tz_convert(TZ_DK)
    tod = dk.dt.hour * 60 + dk.dt.minute
    d = d[((tod >= DAG_FRA) & (tod < DAG_TIL)).values]
    if d.empty: return None
    d = d.assign(bucket=d.time.dt.floor("%ds" % BAR_SEC),
                 dato=d.time.dt.tz_convert(TZ_DK).dt.normalize())
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in d.columns: agg["volume"] = "sum"
    return (d.sort_values("time")
             .groupby(["sym", "bucket", "dato"], as_index=False, sort=False)
             .agg(agg))


def rul(d, pre):
    """Frontkontrakt pr. dag efter volumen. Ruller aldrig tilbage."""
    if "volume" not in d.columns: d = d.assign(volume=1)
    dag = d.groupby(["dato", "sym"], as_index=False)["volume"].sum()
    dag["rang"] = dag.sym.map(lambda s: udloeb(s, pre))
    dag = dag[dag.rang.notna()]
    valg, sidst = {}, None
    for dt, g in dag.sort_values("dato").groupby("dato", sort=True):
        g = g.sort_values("volume", ascending=False)
        v = g.iloc[0]
        if sidst is not None and v.rang < sidst:
            g2 = g[g.rang >= sidst]
            if g2.empty: continue
            v = g2.iloc[0]
        valg[dt] = v.sym; sidst = v.rang
    print("  %s: %d handelsdage, %d kontrakter: %s"
          % (pre, len(valg), len(set(valg.values())), sorted(set(valg.values()))))
    ser = d.dato.map(valg)
    return d[(ser.notna()) & (d.sym == ser)]


def main(sti):
    if not os.path.exists(sti):
        print("Findes ikke:", sti); return
    kilder = indlaes_kilder(sti)
    if not kilder:
        print("Ingen datafil fundet i", sti); return

    dele, seq = [], 0
    for i, (navn, aabn) in enumerate(kilder, 1):
        print("\n[%d/%d] %s" % (i, len(kilder), navn), flush=True)
        it = aabn().to_df(count=BID)
        raa = 0
        for d in it:
            raa += len(d)
            p = bearbejd(d)
            if p is not None and not p.empty:
                p["seq"] = seq; seq += 1
                dele.append(p)
            print("     %10d raekker laest, %8d 15s-barer indtil nu"
                  % (raa, sum(len(x) for x in dele)), flush=True)

    if not dele:
        print("\nIngen raekker tilbage efter filtrering."); return

    # saml delaggregaterne. En 15s-bucket kan ligge paa tvaers af to bidder,
    # saa der aggregeres en gang til - sorteret paa seq saa first/last holder.
    alle = pd.concat(dele, ignore_index=True).sort_values(["sym", "bucket", "seq"])
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "dato": "first"}
    if "volume" in alle.columns: agg["volume"] = "sum"
    bar = alle.groupby(["sym", "bucket"], as_index=False, sort=False).agg(agg)
    bar = bar.rename(columns={"bucket": "time"})
    print("\nSamlet: %d 15s-barer, %s .. %s" % (len(bar), bar.time.min(), bar.time.max()))

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
            d_ = ud[(aar == y).values]
            if len(d_) < 100: continue          # springer en enkelt overlapsdag over
            fil = "%s_%d.parquet" % (pre, y)
            d_.to_parquet(fil, index=False, compression="zstd")
            mb = os.path.getsize(fil) / 1e6
            skrevet.append((fil, len(d_), mb))
            print("  %-18s %7d barer   %5.1f MB%s"
                  % (fil, len(d_), mb, "   <-- OVER 30 MB, koer del_op.py" if mb > 30 else ""))

    print("\nFaerdig. %d fil(er):" % len(skrevet))
    for f, n, mb in skrevet:
        print("   %-18s %5.1f MB" % (f, mb))
    print("\nUpload dem. Er en enkelt stadig for stor:  python del_op.py NQ_2025.parquet 25")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
