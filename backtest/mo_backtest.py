"""
Market open-retning (Pine "Market open-retning") oversat til Python, bar for bar paa 15s-data.

SWING (NQ = chart, ES = andet asset), alle tider New York:
  - London high/low 02:00-08:00, formarked high/low 08:00-09:00 (NQ og ES hver for sig).
  - London-niveauer der rammes 08:00-08:45 er brugt op.
  - Vindue: 08:45 til og med baren der lukker 09:29:45. Formarkedets niveauer gaelder fra 09:00.
    Beroering (high >= niveau / low <= niveau) = taget.
  - Naar BEGGE har taget et nyt faelles niveau paa en side, aabnes det minut (og det naeste, hvis det
    skete i minuttets sidste 15s-bar). En 15s-bar i det/de minutter hvor BEGGE lukker modsat vej = swing.
    Entry = close. Short vinder hvis begge sider er gyldige paa samme bar.
  - Swingen foelges til 09:29:45: stop SW_STOP, TP SW_TP (stop foerst hvis begge paa samme bar).
MARKET OPEN:
  - swing tabt -> modsat; ellers samme vej; ingen swing -> intet trade; rv5 >= 2,25 % -> spring over.
  - Entry = close paa baren der lukker 09:29:45. Stop MO_STOP point. Exit ved close 09:31:00 (slut 09:30-minuttet).
  - R = point / 10.
"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from smt_backtest import load, NO_TRADE_DAYS

SW_STOP, SW_TP = 10.0, 175.0
MO_STOP = 30.0
RV_LIM = 2.25
MO_EXIT_MIN = 9 * 60 + 31   # exit ved close af baren der lukker 09:31:00


def rv5_table(nq):
    """rv5 pr. dag: gennemsnit af de 5 forrige dages RTH true range i % (som rv5.pine, [1])."""
    d = nq[(nq.mn >= 570) & (nq.mn < 960)].groupby('dato').agg(h=('high', 'max'), l=('low', 'min'), c=('close', 'last'))
    pc = d.c.shift(1)
    tr = pd.concat([d.h - d.l, (d.h - pc).abs(), (d.l - pc).abs()], axis=1).max(axis=1) / d.c * 100
    return tr.rolling(5).mean().shift(1).to_dict()


def run(nq_path, es_path, start, end):
    a = load(nq_path); b = load(es_path)
    lt = pd.to_datetime(a.t, unit='s', utc=True).dt.tz_convert('America/New_York')
    a = a.assign(dato=lt.dt.strftime('%Y-%m-%d').values, mn=(lt.dt.hour * 60 + lt.dt.minute).values, sec=lt.dt.second.values)
    rv = rv5_table(a)
    b = b.set_index('t').reindex(a.t)   # gaps_on: manglende ES-bar = NaN
    a = a[(a.dato >= start) & (a.dato <= end)]
    out = []
    for dstr, g in a.groupby('dato', sort=True):
        e = b.loc[g.t.values]
        T = g.t.values; MN = g.mn.values; SEC = g.sec.values
        O, H, L, C = g.open.values, g.high.values, g.low.values, g.close.values
        EO, EH, EL, EC = e.open.values, e.high.values, e.low.values, e.close.values
        nLH = nLL = eLH = eLL = nPH = nPL = ePH = ePL = None
        brugt = dict(nLH=False, nLL=False, eLH=False, eLL=False)
        tk = {k: False for k in ('nLH', 'nLL', 'nPH', 'nPL', 'eLH', 'eLL', 'ePH', 'ePL')}
        sNH = sNL = 0; fraH = tilH = fraL = tilL = None
        sw = None; swStatus = None; pNu = None; moIdx = None
        for i in range(len(T)):
            mn, hi, lo, cl, op = MN[i], H[i], L[i], C[i], O[i]
            harE = not (np.isnan(EC[i]) or np.isnan(EO[i]))
            eh, el, ec, eo = EH[i], EL[i], EC[i], EO[i]
            if 120 <= mn < 480:
                nLH = hi if nLH is None else max(nLH, hi); nLL = lo if nLL is None else min(nLL, lo)
                if harE:
                    eLH = eh if eLH is None else max(eLH, eh); eLL = el if eLL is None else min(eLL, el)
            if 480 <= mn < 540:
                nPH = hi if nPH is None else max(nPH, hi); nPL = lo if nPL is None else min(nPL, lo)
                if harE:
                    ePH = eh if ePH is None else max(ePH, eh); ePL = el if ePL is None else min(ePL, el)
            if 480 <= mn < 525:
                if nLH is not None and hi >= nLH: brugt['nLH'] = True
                if nLL is not None and lo <= nLL: brugt['nLL'] = True
                if harE and eLH is not None and eh >= eLH: brugt['eLH'] = True
                if harE and eLL is not None and el <= eLL: brugt['eLL'] = True
            before = mn * 60 + SEC[i] < 9 * 3600 + 29 * 60 + 45   # bar-open foer 09:29:45
            # foelg swingen
            if sw is not None and swStatus == 'Aaben' and T[i] > sw['t'] and before:
                k = sw['short']
                stop = hi >= sw['entry'] + SW_STOP if k else lo <= sw['entry'] - SW_STOP
                tp = lo <= sw['entry'] - SW_TP if k else hi >= sw['entry'] + SW_TP
                if stop: swStatus = 'Tabt'; sw['statusT'] = T[i]
                elif tp: swStatus = 'Vundet'
            if sw is not None and before:
                pNu = cl; moIdx = i
            # find swing
            if mn >= 525 and before and sw is None:
                pA = mn >= 540
                if not tk['nLH'] and not brugt['nLH'] and nLH is not None and hi >= nLH: tk['nLH'] = True
                if pA and not tk['nPH'] and nPH is not None and hi >= nPH: tk['nPH'] = True
                if harE and not tk['eLH'] and not brugt['eLH'] and eLH is not None and eh >= eLH: tk['eLH'] = True
                if harE and pA and not tk['ePH'] and ePH is not None and eh >= ePH: tk['ePH'] = True
                if not tk['nLL'] and not brugt['nLL'] and nLL is not None and lo <= nLL: tk['nLL'] = True
                if pA and not tk['nPL'] and nPL is not None and lo <= nPL: tk['nPL'] = True
                if harE and not tk['eLL'] and not brugt['eLL'] and eLL is not None and el <= eLL: tk['eLL'] = True
                if harE and pA and not tk['ePL'] and ePL is not None and el <= ePL: tk['ePL'] = True
                nH = int(tk['nLH'] and tk['eLH']) + int(tk['nPH'] and tk['ePH'])
                nL = int(tk['nLL'] and tk['eLL']) + int(tk['nPL'] and tk['ePL'])
                minNr = T[i] // 60
                last15 = SEC[i] == 45
                if nH > sNH: fraH = minNr; tilH = minNr + 1 if last15 else minNr; sNH = nH
                if nL > sNL: fraL = minNr; tilL = minNr + 1 if last15 else minNr; sNL = nL
                kort = nH > 0 and harE and cl < op and ec < eo and fraH <= minNr <= tilH
                lang = nL > 0 and harE and cl > op and ec > eo and fraL <= minNr <= tilL
                if kort or lang:
                    sw = dict(short=kort, entry=cl, t=T[i], mn=mn, sec=SEC[i]); swStatus = 'Aaben'; pNu = cl; moIdx = i
        if sw is None:
            out.append(dict(dato=dstr, swing='', mo='INGEN', R=None)); continue
        moShort = (not sw['short']) if swStatus == 'Tabt' else sw['short']
        r5 = rv.get(dstr)
        skip = r5 is not None and not np.isnan(r5) and r5 >= RV_LIM
        rec = dict(dato=dstr, swing=('SHORT' if sw['short'] else 'LONG'), sw_tid=f"{(sw['mn'] + 360) // 60:02d}:{(sw['mn'] + 360) % 60:02d}:{sw['sec']:02d}",
                   sw_status=swStatus, rv5=None if r5 is None else round(r5, 2), mo=('SPRING OVER' if skip else ('SHORT' if moShort else 'LONG')))
        # market open-trade
        R = None
        if not skip and dstr not in NO_TRADE_DAYS and moIdx is not None:
            ent = pNu; stp = ent + MO_STOP if moShort else ent - MO_STOP; pts = None
            for j in range(moIdx + 1, len(T)):
                hj, lj = H[j], L[j]
                if (hj >= stp) if moShort else (lj <= stp):
                    pts = -MO_STOP; break
                if (MN[j] * 60 + SEC[j] + 15) >= MO_EXIT_MIN * 60:
                    pts = (ent - C[j]) if moShort else (C[j] - ent); break
            if pts is not None:
                R = round(pts / 10, 2)
        rec['entry'] = pNu; rec['R'] = R
        out.append(rec)
    return pd.DataFrame(out)
