import pandas as pd, json
exec(open('simnr.py').read().split('\nrows=[]')[0])
s=maxday(stopwin(load('s_pm','SMT')),2); v=maxday(stopwin(load('v_pm','VRG')),2); sf=eqfilter(s,30)
out=[]
for m in sorted(set(s.dato.str[:7])|set(v.dato.str[:7])):
    f=lambda t:(int((t.dato.str[:7]==m).sum()), round(float(t[t.dato.str[:7]==m].R.sum()),1))
    a,b,c=f(s),f(sf),f(v); out.append(dict(m=m,s_n=a[0],s_R=a[1],f_n=b[0],f_R=b[1],v_n=c[0],v_R=c[1]))
json.dump(out,open('monthly.json','w')); 
d=pd.DataFrame(out); d['tot']=d.f_R+d.v_R; print(d.to_string(index=False))
