# -*- coding: utf-8 -*-
import pandas as pd, datetime, json
d = pd.read_csv('/tmp/y2025_1600.csv').sort_values('id')
MINUS="−"
def dk(x,n=2,s=True):
    if abs(x)<0.005: return "0,"+"0"*n
    return (("%+.*f" if s else "%.*f")%(n,x)).replace('.',',').replace('-',MINUS)
def dkp(x,n=2): return dk(x,n,False)
def cl(x): return "pos" if x>0.005 else ("neg" if x<-0.005 else "flat")
MND={1:"Januar",2:"Februar",3:"Marts",4:"April",5:"Maj",6:"Juni",7:"Juli",8:"August",
     9:"September",10:"Oktober",11:"November",12:"December"}
UGE=["man","tir","ons","tor","fre","lør","søn"]
d['m']=pd.to_datetime(d.dag).dt.month
body=[]; msum=[]
for m,g in d.groupby('m'):
    R=g.R.sum(); tp=(g.reason=='TP').sum(); sl=(g.reason=='SL').sum(); be=(g.reason=='BE').sum()
    msum.append((MND[m],len(g),R,tp,sl,be,g.dag.nunique()))
    body.append('<tbody>\n<tr class="msep"><td colspan="9"><div class="ms">'
      '<span class="mn">%s</span><span class="mm">%d handler · %d dage</span>'
      '<span class="mx mono">%d TP · %d SL · %d BE</span>'
      '<span class="mt num %s">%s<small>R</small></span></div></td></tr>'
      % (MND[m], len(g), g.dag.nunique(), tp, sl, be, cl(R), dk(R)))
    for r in g.itertuples():
        dd=datetime.date.fromisoformat(r.dag)
        body.append('<tr>'
          '<td class="dd mono">%d/%d<span class="sw">%s</span></td>'
          '<td class="tid mono">%s<span class="sw">%s</span></td>'
          '<td><span class="chip t-%s">%s</span></td>'
          '<td class="num">%s</td><td class="num">%s</td><td class="num sd">%s</td>'
          '<td class="num">%s</td>'
          '<td class="udf"><span class="chip r-%s">%s</span>%s</td>'
          '<td class="num big %s">%s</td></tr>'
          % (dd.day, dd.month, UGE[dd.weekday()], r.t, r.x,
             r.trigger_asset.lower(), r.trigger_asset,
             dkp(r.entry), dkp(r.stop), dkp(r.stop_dist,2), dkp(r.tp),
             r.reason.lower(), r.reason,
             '<span class="bedot"></span>' if r.moved_be else '',
             cl(r.R), dk(r.R)))
    body.append('</tbody>')
mrows=[]
for navn,n,R,tp,sl,be,dage in msum:
    mrows.append('<tr><td class="mnd">%s</td><td class="num">%d</td><td class="num">%d</td>'
      '<td class="num sep">%d</td><td class="num">%d</td><td class="num">%d</td>'
      '<td class="num big %s">%s</td></tr>' % (navn,n,dage,tp,sl,be,cl(R),dk(R)))
tot=d.R.sum()
mrows.append('<tr class="sum"><td class="mnd">I alt</td><td class="num">%d</td><td class="num">%d</td>'
  '<td class="num sep">%d</td><td class="num">%d</td><td class="num">%d</td>'
  '<td class="num big %s">%s</td></tr>'
  % (len(d), d.dag.nunique(), (d.reason=='TP').sum(), (d.reason=='SL').sum(),
     (d.reason=='BE').sum(), cl(tot), dk(tot)))

# revalidering
REV=[("Vindue 15:30–16:00",167,74.80,0.45,-26.70,1.67,"valgt"),
     ("Vindue 15:30–16:30",265,43.15,0.16,-34.98,0.84,""),
     ("Kun shorts",167,74.80,0.45,-26.70,1.67,"valgt"),
     ("Kun longs",145,11.62,0.08,-29.30,0.32,""),
     ("Begge sider",312,86.43,0.28,-24.75,1.50,""),
     ("Dagsregel −2,5/+3,75",167,74.80,0.45,-26.70,1.67,"valgt"),
     ("Dagsregel −5/+7,5",191,67.95,0.36,-28.55,1.45,""),
     ("Ingen dagsregel",202,66.57,0.33,-29.65,1.40,"")]
rev=[]
for navn,n,R,pr,dd,t,mk in REV:
    rev.append('<tr%s><td class="mnd">%s</td><td class="num">%d</td>'
      '<td class="num %s">%s</td><td class="num %s">%s</td>'
      '<td class="num neg">%s</td><td class="num">%s</td></tr>'
      % (' class="hl"' if mk else '', navn, n, cl(R), dk(R), cl(pr), dk(pr), dk(dd), dk(t)))
json.dump(dict(body="\n".join(body), mrows="\n".join(mrows), rev="\n".join(rev),
               n=len(d), dage=int(d.dag.nunique()), tot=float(tot)),
          open('/tmp/p2025.json','w'))
print("ok", len(d), round(tot,2))
