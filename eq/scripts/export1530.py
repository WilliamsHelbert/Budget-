import sys, os, json, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
BASE = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
            max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
            be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
W = dict(entry_from=15*60+30, entry_to=16*60+30)

def pack(df):
    out = []
    for tid, g in df.groupby('id'):
        g = g.set_index('asset')
        r = dict(id=int(tid), day=g.iloc[0]['day'], hit_t=g.iloc[0]['hit_t'],
                 entry_t=g.iloc[0]['entry_t'], side=g.iloc[0]['side'],
                 trig=g.iloc[0]['trigger_asset'])
        for k in ('NQ','ES'):
            if k not in g.index: continue
            x = g.loc[k]
            r[k] = dict(entry=float(x.entry), stop=float(x.stop), tp=float(x.tp),
                        exit=float(x['exit']), exit_t=x.exit_t, reason=x.reason,
                        be=bool(x.moved_be), be_t=x.be_t or "",
                        sd=float(x.stop_dist), R=float(x.R),
                        Rr=float(x.pts)/float(x.stop_dist))
        out.append(r)
    return out

# konfig A: kun NQ, dagsregler paa NQ
dfA,stA,nA,_,_ = model.run_full(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ', **W, **BASE)
# konfig B: begge ben, dagsregler paa summen (som rapporten hidtil)
dfB,stB,nB,_,_ = model.run_full(daily_stop=-5, daily_target=7.5, daily_basis='sum', **W, **BASE)

def summ(df, asset=None):
    if asset:
        s = df[df.asset==asset].sort_values('id'); r = s.R.values
        rr = (s.pts/s.stop_dist).values
    else:
        s = df; g = df.groupby('id')
        r = g.R.sum().sort_index().values
        rr = (df.pts/df.stop_dist).groupby(df.id).sum().sort_index().values
    eq = np.cumsum(r); eqr = np.cumsum(rr)
    return dict(n=len(r), R=float(r.sum()), pr=float(r.mean()),
                dd=float((eq-np.maximum.accumulate(eq)).min()),
                Rr=float(rr.sum()), prr=float(rr.mean()),
                ddr=float((eqr-np.maximum.accumulate(eqr)).min()),
                win=float((r>0).mean()*100), sd=float(r.std()),
                t=float(r.mean()*np.sqrt(len(r))/r.std()),
                best=float(r.max()), worst=float(r.min()),
                TP=int((s.reason=='TP').sum()) if asset else int((df.reason=='TP').sum()),
                SL=int((s.reason=='SL').sum()) if asset else int((df.reason=='SL').sum()),
                BE=int((s.reason=='BE').sum()) if asset else int((df.reason=='BE').sum()),
                bemoved=int(s.moved_be.sum()) if asset else int(df.moved_be.sum()),
                legs=int(len(s)) if asset else int(len(df)),
                sdmin=float(s.stop_dist.min()) if asset else 0,
                sdmed=float(s.stop_dist.median()) if asset else 0,
                sdmax=float(s.stop_dist.max()) if asset else 0)

data = dict(
  trades=pack(dfA),
  tradesB=pack(dfB),
  A=dict(NQ=summ(dfA,'NQ'), ES=summ(dfA,'ES'), pair=summ(dfA)),
  B=dict(NQ=summ(dfB,'NQ'), ES=summ(dfB,'ES'), pair=summ(dfB)),
  days=sorted(dfA.day.unique().tolist()),
)
# andre vinduer til sammenligning (NQ-ben, dagsregler NQ)
cmp = []
for name,a,b in [("15:30–16:00",15*60+30,16*60),("16:00–16:30",16*60,16*60+30),
                 ("15:30–16:30",15*60+30,16*60+30),("16:30–17:00",16*60+30,17*60),
                 ("15:30–17:00",15*60+30,17*60)]:
    d,_,_,_,_ = model.run_full(entry_from=a, entry_to=b, daily_stop=-2.5,
                               daily_target=3.75, daily_basis='NQ', **BASE)
    s = summ(d,'NQ'); s['name']=name; cmp.append(s)
data['cmp']=cmp
json.dump(data, open('/tmp/w1530.json','w'))
print("par:", nA, "| NQ", round(data['A']['NQ']['R'],2), "| ES", round(data['A']['ES']['R'],2))
print("dage:", len(data['days']))
print(json.dumps(data['trades'][0], indent=1)[:600])
