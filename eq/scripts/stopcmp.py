# -*- coding: utf-8 -*-
import sys, os, importlib, numpy as np, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
DAGE = ["2026-01-08","2026-01-09","2026-01-13","2026-01-14","2026-01-15","2026-01-16"]
import model; importlib.reload(model)
model.BASE=SP+"/dbfull"; model.TZ="America/New_York"
model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
df,_,_,sig,_ = model.run_full(entry_from=9*60+30, entry_to=10*60,
    conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60,
    be_min={'ES':0.25,'NQ':2.0}, conf_now=True,
    be_src='liq', liq_piv=0, liq_from=0, block_mode='opposite')   # INGEN caps
s = pd.DataFrame(sig)
s['t']=pd.to_datetime(s.ts,unit='s',utc=True).dt.tz_convert('Europe/Copenhagen')
s['dag']=s.t.dt.strftime('%Y-%m-%d'); s['kl']=s.t.dt.strftime('%H:%M'); s['mm']=s.t.dt.hour*60+s.t.dt.minute
s = s[s.dag.isin(DAGE) & s.NQ_entry.notna()]
s['dir'] = np.where(s.side=='bear','Short','Long')
s['nq_stop'] = (s.NQ_entry - s.NQ_stop).abs()
s['es_stop'] = (s.ES_entry - s.ES_stop).abs()
jour = pd.read_csv(SP+"/meq.csv")
jour['mm'] = jour.ind.str[:2].astype(int)*60 + jour.ind.str[3:].astype(int)
print("%-11s %-6s %-6s | %-9s %-9s | %-9s %-9s %-9s | %s" %
      ("dag","jour","dir","JOUR stop","MODEL stop","MODEL BE","ES stop","ES BE","match"))
print("-"*112)
tr=[]
for _,j in jour.iterrows():
    g = s[(s.dag==j.dag) & (s.mm>=j.mm-2) & (s.mm<=j.mm+2)]
    gd = g[g.dir==j.dir]
    r = gd.iloc[0] if len(gd) else (g.iloc[0] if len(g) else None)
    jstop = abs(j.R)*10 if j.R<0 else np.nan
    if r is None:
        print("%-11s %-6s %-6s | %-9s %s" % (j.dag,j.ind,j.dir,
              ("%.2f"%jstop) if jstop==jstop else "BE/TP","-- modellen ser intet --")); continue
    ok = "JA" if len(gd) else "retning!"
    print("%-11s %-6s %-6s | %-9s %-9.2f | %-9s %-9.2f %-9s | %s"
          % (j.dag, j.ind, j.dir, ("%.2f"%jstop) if jstop==jstop else "BE/TP", r.nq_stop,
             ("%.2f"%r.NQ_bedist) if pd.notna(r.NQ_bedist) else "-", r.es_stop,
             ("%.2f"%r.ES_bedist) if pd.notna(r.ES_bedist) else "-", ok))
    if jstop==jstop: tr.append((jstop, r.nq_stop))
if tr:
    a=np.array(tr)
    print("\nJOURNALENS stop: median %.2f pt, spaend %.2f-%.2f" % (np.median(a[:,0]), a[:,0].min(), a[:,0].max()))
    print("MODELLENS stop:  median %.2f pt, spaend %.2f-%.2f" % (np.median(a[:,1]), a[:,1].min(), a[:,1].max()))
    print("modellen er i snit %.1fx for stor" % (a[:,1].mean()/a[:,0].mean()))
