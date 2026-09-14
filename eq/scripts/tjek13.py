import sys, os, importlib, pandas as pd
ENG=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ENG); SP=os.path.dirname(ENG)
import model; importlib.reload(model)
model.BASE=SP+"/vendata"; model.TZ="America/New_York"; model.OPEN_MIN,model.CLOSE_MIN=9*60+30,16*60
BASEK=dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True, daily_stop=None, daily_target=None,
           max_stop=None, max_be=None)
for oaat in (False, True):
    df,_,_,_,_ = model.run_full(entry_from=9*60+30, entry_to=10*60, one_at_a_time=oaat, **BASEK)
    d=df[(df.day>="2026-01-02")&(df.day<="2026-01-16")].copy()
    dk=pd.to_datetime(d.entry_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
    xd=pd.to_datetime(d.exit_t).dt.tz_localize('America/New_York').dt.tz_convert('Europe/Copenhagen')
    d['t']=dk.dt.strftime('%H:%M'); d['x']=xd.dt.strftime('%H:%M')
    n=d[d.asset=='NQ']
    print("\n===== en-ad-gangen = %s  ->  %d handler i alt (2.-16. jan) =====" % (oaat, len(n)))
    print(" 13. januar:")
    for r in n[n.day=="2026-01-13"].sort_values('id').itertuples():
        e=d[(d.id==r.id)&(d.asset=='ES')].iloc[0]
        print("   %s-%s %-5s | ES indg %8.2f stop %8.2f (%4.2f p) %+6.3f %-2s | NQ indg %9.2f stop %9.2f (%5.1f p) %+6.3f %s"
              % (r.t, r.x, r.side, e.entry, e.stop, e.stop_dist, e.R, e.reason,
                 r.entry, r.stop, r.stop_dist, r.R, r.reason))
    # hvor mange rammer 8/40
    print("   stops over loft: ES %d/%d | NQ %d/%d"
          % ((d[d.asset=='ES'].stop_dist>8).sum(), len(d[d.asset=='ES']),
             (n.stop_dist>40).sum(), len(n)))
