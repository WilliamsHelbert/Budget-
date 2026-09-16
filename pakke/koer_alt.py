#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Koerer BEGGE modeller og skriver en samlet fil.

    python koer_alt.py <datamappe> [<datamappe2> ...]

Datamappen skal indeholde ES.parquet og NQ.parquet med 15s-barer og
kolonnerne time (UTC), open, high, low, close. Fuld doegndata
(mindst 02:00-22:10 dansk tid) - SMT har brug for Asien og London.

Skriver:
    alle_trades.csv   begge modeller, en raekke pr. handel
    eq_trades.csv     kun EQ
    smt_trades.csv    kun SMT
"""
import sys, os, math, importlib
import numpy as np, pandas as pd

# ---------------------------------------------------------------- EQ-opsaetning
# Laast 16-09-2026. AEndr ikke uden at notere hvorfor.
EQ_CFG = dict(
    conf_sec      = 15,                       # bekraeftelseslys
    sl_mode       = 'anchor',                 # SL paa EQ-toppen
    max_conf_bars = 4,
    flat_at       = 24*60,                    # ingen tvangsluk
    entry_from    = 9*60+30,                  # 09:30 NY = 15:30 dansk
    entry_to      = 10*60,                    # 10:00 NY = 16:00 dansk
    sides         = ('bear',),                # KUN SHORTS
    be_src        = 'liq',                    # BE = naermeste LEVENDE 5m-liq
    liq_piv       = 0,                        # alle 5m-lys taeller, ikke kun pivots
    liq_from      = 0,                        # niveauer fra hele doegnet
    be_min        = {'ES': 0.25, 'NQ':  2.0},
    max_stop      = {'ES': 8.0,  'NQ': 40.0}, # 8/40-reglen paa stoppet
    max_be        = {'ES': 8.0,  'NQ': 40.0}, # 8/40-reglen paa BE-afstanden
    conf_now      = True,
    block_mode    = 'any',                    # aaben position -> naeste setup ugyldigt
    # INTET dagsstop. Journalen viser at der ikke handles med et.
)

def koer_eq(mappe):
    import eq_model; importlib.reload(eq_model)
    eq_model.BASE = mappe
    eq_model.TZ = "America/New_York"          # US sommertid starter 3 uger foer EU
    eq_model.OPEN_MIN, eq_model.CLOSE_MIN = 9*60+30, 16*60
    df, *_ = eq_model.run_full(**EQ_CFG)
    if not len(df): return pd.DataFrame()
    nq = df[df.asset == 'NQ'].set_index('id')
    es = df[df.asset == 'ES'].set_index('id')
    a = nq.join(es[['entry','stop','tp','exit','reason','R']], rsuffix='_es').reset_index()
    dk = pd.to_datetime(a.entry_t).dt.tz_localize('America/New_York',
            ambiguous='NaT', nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    xd = pd.to_datetime(a.exit_t).dt.tz_localize('America/New_York',
            ambiguous='NaT', nonexistent='NaT').dt.tz_convert('Europe/Copenhagen')
    return pd.DataFrame(dict(
        model='EQ', dag=a.day, ind=dk.dt.strftime('%H:%M:%S'), ud=xd.dt.strftime('%H:%M:%S'),
        retning='Short',
        nq_entry=a.entry, nq_sl=a.stop, nq_tp=a.tp, nq_exit=a.exit,
        nq_udfald=a.reason, nq_R=a.R,
        es_entry=a.entry_es, es_sl=a.stop_es, es_tp=a.tp_es, es_exit=a.exit_es,
        es_udfald=a.reason_es, es_R=a.R_es,
        stop_pt=a.stop_dist, kilde=os.path.basename(mappe.rstrip('/'))))

def koer_smt(mappe):
    import smt_model; importlib.reload(smt_model)
    df = smt_model.run(mappe)
    if not len(df): return pd.DataFrame()
    return pd.DataFrame(dict(
        model='SMT', dag=df.dag, ind=df.t, ud=df.exit_t.fillna(''),
        retning=np.where(df.short, 'Short', 'Long'),
        nq_entry=df.entry, nq_sl=df.sl, nq_tp=df.tp, nq_exit=df.exit,
        nq_udfald=df.reason, nq_R=df.R,
        es_entry=np.nan, es_sl=np.nan, es_tp=np.nan, es_exit=np.nan,
        es_udfald='', es_R=np.nan,
        stop_pt=(df.entry-df.sl).abs(),
        kilde=os.path.basename(mappe.rstrip('/'))))

def tal(x, lbl):
    x = np.asarray([v for v in x if v == v])
    if len(x) < 2:
        print("  %-26s n %3d" % (lbl, len(x))); return
    e = np.cumsum(x)
    print("  %-26s n %3d | R %+8.2f | pr.h %+5.2f | maxDD %+7.2f | t %+5.2f"
          % (lbl, len(x), x.sum(), x.mean(),
             (e - np.maximum.accumulate(e)).min(),
             x.mean()*math.sqrt(len(x))/x.std()))

def main(mapper):
    dele = []
    for m in mapper:
        if not os.path.isdir(m):
            print("Mappen findes ikke:", m); continue
        for navn in ("ES.parquet", "NQ.parquet"):
            if not os.path.exists(os.path.join(m, navn)):
                print("Mangler %s i %s" % (navn, m)); return
        print("\n=== %s ===" % m, flush=True)
        print("  EQ ...", flush=True);  e = koer_eq(m);  print("  EQ:  %d handler" % len(e))
        print("  SMT ...", flush=True); s = koer_smt(m); print("  SMT: %d handler" % len(s))
        dele += [e, s]
    if not dele: return
    alle = pd.concat([d for d in dele if len(d)], ignore_index=True)
    alle = alle.sort_values(['dag','ind','model']).reset_index(drop=True)
    alle['mnd'] = alle.dag.str[:7]
    alle.to_csv("alle_trades.csv", index=False)
    alle[alle.model=='EQ'].to_csv("eq_trades.csv", index=False)
    alle[alle.model=='SMT'].to_csv("smt_trades.csv", index=False)

    eq, smt = alle[alle.model=='EQ'], alle[alle.model=='SMT']
    print("\n" + "="*84)
    print("EQ  (kun shorts, 15:30-16:00 dansk tid)")
    tal(eq.nq_R.values, "NQ-benet")
    tal(eq.es_R.values, "ES-benet")
    print("  udfald NQ:", eq.nq_udfald.value_counts().to_dict())
    print("\nSMT")
    tal(smt.nq_R.values, "NQ")
    print("  udfald:", smt.nq_udfald.value_counts().to_dict())
    print("\n" + "="*84)
    print("MAANED FOR MAANED")
    m = alle.pivot_table(index='mnd', columns='model', values='nq_R',
                         aggfunc=['count','sum']).round(2)
    print(m.to_string())
    eqm = eq.groupby('mnd').es_R.sum().round(2)
    print("\nEQ ES-benet pr. maaned:"); print(eqm.to_string())
    print("\nSkrevet: alle_trades.csv, eq_trades.csv, smt_trades.csv")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    main(sys.argv[1:])
