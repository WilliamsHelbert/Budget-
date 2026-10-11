"""Koer modellen for en periode med valgfrie indstillinger:
python3 run_year.py ES|NQ DATA_DIR FRA TIL NAVN [KEY=VAL ...]
fx: python3 run_year.py ES data 2025-01-02 2025-12-31 2025 TP_MODE=session FALLBACK=fixed FIXED_RR=2 ENTRY=ote"""
import sys
sys.path.insert(0,'.')
import continuation_model as cm
ex,cm.DATA_DIR,fra,til,navn=sys.argv[1:6]
tag=[]
for kv in sys.argv[6:]:
    k,v=kv.split('=')
    cur=getattr(cm,k)
    setattr(cm,k,(v=='True') if isinstance(cur,bool) else type(cur)(v)); tag.append(f"{k}-{v}")
cm.EXEC=ex; cm.PERIOD=(fra,til)
df=cm.run()
out=f"results/{navn}_trades_{ex}{'_'+'_'.join(tag) if tag else ''}.csv"
df.to_csv(out,index=False)
print(out,len(df))
