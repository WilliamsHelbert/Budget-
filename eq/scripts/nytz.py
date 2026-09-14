# -*- coding: utf-8 -*-
"""Koer modellen i New York-tid, saa 09:30 altid er 09:30 uanset sommertid."""
import sys, os, importlib
ENG = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ENG)
CFG = dict(conf_sec=15, sl_mode='anchor', max_conf_bars=4, flat_at=24*60, be_ref='prev',
           max_stop={'ES':8,'NQ':40}, max_be={'ES':8,'NQ':40},
           be_min={'ES':0.25,'NQ':2.0}, conf_now=True)
DAY = dict(daily_stop=-2.5, daily_target=3.75, daily_basis='NQ')

def run(base, ny=True, frm=None, to=None, **extra):
    import model
    importlib.reload(model)
    model.BASE = base
    if ny:
        model.TZ = "America/New_York"
        model.OPEN_MIN, model.CLOSE_MIN = 9*60+30, 16*60
        frm = frm if frm is not None else 9*60+30
        to  = to  if to  is not None else 10*60+30
    else:
        frm = frm if frm is not None else 15*60+30
        to  = to  if to  is not None else 16*60+30
    cfg = dict(CFG); cfg.update(extra)
    df,_,n,_,aud = model.run_full(entry_from=frm, entry_to=to, **DAY, **cfg)
    return df[df.asset=='NQ'].copy(), df, aud

if __name__ == "__main__":
    SP = os.path.dirname(ENG)
    a,_,_ = run(SP, ny=False)
    a = a[(a.day>="2026-08-12")&(a.day<="2026-09-10")]
    b,_,_ = run(SP, ny=True)
    b = b[(b.day>="2026-08-12")&(b.day<="2026-09-10")]
    print("CPH-tid 15:30-16:30 : %2d handler %+7.2f R" % (len(a), a.R.sum()))
    print("NY-tid  09:30-10:30 : %2d handler %+7.2f R" % (len(b), b.R.sum()))
    A = {(r.day,r.entry_t[11:19]) for r in a.itertuples()}
    B = {(r.day,r.entry_t[11:19]) for r in b.itertuples()}
    print("identiske entries:", len(A & B), "| kun CPH:", len(A-B), "| kun NY:", len(B-A))
