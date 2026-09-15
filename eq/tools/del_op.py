#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deler en parquet-fil op i bidder under en given stoerrelse.

Koersel:   python del_op.py NQ_2025.parquet 25
           (25 = maks MB pr. bid, standard er 25)

Laver NQ_2025_del1.parquet, NQ_2025_del2.parquet ...
Raekkefoelgen bevares, saa de bare skal uploades alle sammen.
"""
import sys, os
import pandas as pd

def main(sti, maks_mb=25.0):
    if not os.path.exists(sti):
        print("Findes ikke:", sti); return
    d = pd.read_parquet(sti)
    ialt = os.path.getsize(sti) / 1e6
    print("%s: %d raekker, %.1f MB" % (sti, len(d), ialt))
    if ialt <= maks_mb:
        print("Den er allerede under %.0f MB. Upload den som den er." % maks_mb)
        return

    grund = os.path.splitext(os.path.basename(sti))[0]
    dele = max(2, int(ialt / maks_mb) + 1)
    while True:
        pr = -(-len(d) // dele)                     # loft-division
        filer = []
        for i in range(dele):
            del_ = d.iloc[i*pr:(i+1)*pr]
            if del_.empty: continue
            f = "%s_del%d.parquet" % (grund, i+1)
            del_.to_parquet(f, index=False, compression="zstd")
            filer.append((f, len(del_), os.path.getsize(f)/1e6))
        if max(mb for _, _, mb in filer) <= maks_mb:
            break
        for f, _, _ in filer: os.remove(f)
        dele += 1

    print("\n%d bidder:" % len(filer))
    for f, n, mb in filer:
        print("   %-26s %7d raekker  %5.1f MB" % (f, n, mb))
    print("\nUpload alle %d. De saettes sammen igen i raekkefoelge." % len(filer))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 25.0)
