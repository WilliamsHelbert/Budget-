# -*- coding: utf-8 -*-
import json, math
D=json.load(open('/tmp/side.json'))
MINUS="−"
def dk(x,n=2,s=True):
    if x is None or (isinstance(x,float) and math.isnan(x)): return "–"
    if abs(x)<0.005: return "0,"+"0"*n
    return (("%+.*f" if s else "%.*f")%(n,x)).replace('.',',').replace('-',MINUS)
def dkp(x,n=2): return dk(x,n,False)
def cl(x): return "pos" if x>0.005 else ("neg" if x<-0.005 else "flat")

CSS=open('/tmp/css2.txt').read()

def mtable(tag):
    d=D[tag]; out=[]
    for r in d['rows']:
        out.append(
          '<tr><td class="mnd">%s</td><td class="num">%d</td><td class="num %s big">%s</td>'
          '<td class="num sep">%d</td><td class="num %s">%s</td>'
          '<td class="num sep">%d</td><td class="num %s">%s</td>'
          '<td class="num sep">%d</td><td class="num %s">%s</td></tr>'
          % (r['navn'], r['nor']['n'], cl(r['nor']['R']), dk(r['nor']['R']),
             r['lng']['n'], cl(r['lng']['R']), dk(r['lng']['R']),
             r['sht']['n'], cl(r['sht']['R']), dk(r['sht']['R']),
             r['B']['n'],   cl(r['B']['R']),   dk(r['B']['R'])))
    t=d['tot']
    out.append('<tr class="sum"><td class="mnd">I alt</td><td class="num">%d</td><td class="num %s big">%s</td>'
      '<td class="num sep">%d</td><td class="num %s">%s</td>'
      '<td class="num sep">%d</td><td class="num %s">%s</td>'
      '<td class="num sep">%d</td><td class="num %s">%s</td></tr>'
      % (t['nor']['n'], cl(t['nor']['R']), dk(t['nor']['R']),
         t['lng']['n'], cl(t['lng']['R']), dk(t['lng']['R']),
         t['sht']['n'], cl(t['sht']['R']), dk(t['sht']['R']),
         t['B']['n'],   cl(t['B']['R']),   dk(t['B']['R'])))
    return "\n".join(out)

def keyrow(tag):
    t=D[tag]['tot']; cells=[]
    for lbl,k,tk in (("Normal<br><span class=\"sub\">begge sider</span>","nor","t_nor"),
                     ("Variant A<br><span class=\"sub\">shorts, longs blokerer</span>","sht","t_sht"),
                     ("Variant B<br><span class=\"sub\">kun shorts findes</span>","B","t_B"),
                     ("Kun longs findes<br><span class=\"sub\">long-spejlet af B</span>","Bull","t_Bull")):
        o=t["oos_"+k]
        cells.append('<div class="vk"><div class="vh">%s</div>'
          '<div class="vv %s">%s<small>R</small></div>'
          '<div class="vr"><span>%d handler</span><span>%s R/handel</span>'
          '<span>maxDD %s</span><span>t %s</span></div>'
          '<div class="vo">Out-of-sample: <b class="%s">%s R</b> på %d handler · t %s</div></div>'
          % (lbl, cl(t[k]['R']), dk(t[k]['R']), t[k]['n'],
             dk(t[k]['R']/t[k]['n'] if t[k]['n'] else 0), dk(t["dd_"+k]), dk(t[tk]),
             cl(o['R']), dk(o['R']), o['n'], dk(o['t'])))
    return "".join(cells)

def liste(tag):
    d=D[tag]; out=[]
    for m in range(1,10):
        ts=d['liste'][str(m)] if str(m) in d['liste'] else d['liste'][m]
        if not ts: continue
        navn=[r['navn'] for r in d['rows'] if r['m']==m][0]
        R=sum(x['R'] for x in ts); Rl=sum(x['R'] for x in ts if x['side']=='LONG')
        Rs=sum(x['R'] for x in ts if x['side']=='SHORT')
        out.append('<tbody><tr class="msep"><td colspan="12"><div class="ms">'
          '<span class="mn">%s</span><span class="mm">%d handler</span>'
          '<span class="mp"><b class="%s">%s</b> long</span>'
          '<span class="mp"><b class="%s">%s</b> short</span>'
          '<span class="mt num %s">%s<small>R</small></span></div></td></tr>'
          % (navn, len(ts), cl(Rl), dk(Rl), cl(Rs), dk(Rs), cl(R), dk(R)))
        for x in ts:
            out.append('<tr class="%s"><td class="mono dd">%s<span class="sw">%s</span></td>'
              '<td class="mono tid">%s</td>'
              '<td><span class="chip %s">%s</span></td>'
              '<td><span class="chip trig %s">%s</span></td>'
              '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
              '<td class="num sd">%s</td>'
              '<td class="num">%s<span class="sw">%s</span></td>'
              '<td class="udf"><span class="chip r-%s">%s</span>%s</td>'
              '<td class="num big %s">%s</td><td class="num %s">%s</td></tr>'
              % ("lng" if x['side']=='LONG' else "sht",
                 x['dag'][8:]+"/"+x['dag'][5:7], x['ugedag'][:3],
                 x['dk'], "long" if x['side']=='LONG' else "short",
                 "Long" if x['side']=='LONG' else "Short",
                 x['trig'].lower(), x['trig'],
                 dkp(x['entry']), dkp(x['stop']), dkp(x['tp']), dkp(x['sd']),
                 dkp(x['exit']), x['exit_dk'],
                 x['reason'].lower(), x['reason'],
                 '<span class="bedot" title="stop flyttet til break-even"></span>' if x['be'] else '',
                 cl(x['R']), dk(x['R']), cl(x['Rr']), dk(x['Rr'])))
        out.append('</tbody>')
    return "\n".join(out)

TH=('<thead><tr><th>Dato</th><th>Entry</th><th>Retning</th><th>Sweep</th>'
    '<th>Indgang</th><th>Stop</th><th>Mål</th><th>Stop pts</th>'
    '<th>Exit</th><th>Udfald</th><th>R</th><th>R risiko</th></tr></thead>')
MTH=('<thead><tr><th>Måned</th><th>Handler</th><th>Netto R</th>'
     '<th class="sep">n</th><th>Longs R</th>'
     '<th class="sep">n</th><th>Shorts R</th>'
     '<th class="sep">n</th><th>Variant B R</th></tr></thead>')

open('/tmp/parts2.json','w').write(json.dumps(dict(
    css=CSS, m1600=mtable("1600"), m1630=mtable("1630"),
    k1600=keyrow("1600"), k1630=keyrow("1630"),
    l1600=liste("1600"), l1630=liste("1630"), TH=TH, MTH=MTH)))
print("dele klar")
