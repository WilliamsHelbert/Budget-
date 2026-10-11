"""Koer modellen for en periode:
python3 run_year.py ES|NQ DATA_DIR FRA TIL NAVN [TP_MODE FIXED_RR FALLBACK]
fx: python3 run_year.py ES data 2025-01-02 2025-12-31 2025 fixed 1.5 none"""
import sys
sys.path.insert(0,'.')
import continuation_model as cm
ex,cm.DATA_DIR,fra,til,navn=sys.argv[1:6]
suffix=''
if len(sys.argv)>6:
    cm.TP_MODE,cm.FIXED_RR,cm.FALLBACK=sys.argv[6],float(sys.argv[7]),sys.argv[8]
    suffix=f"_{cm.TP_MODE}{sys.argv[7]}_{cm.FALLBACK}"
cm.EXEC=ex; cm.PERIOD=(fra,til)
df=cm.run()
df.to_csv(f'results/{navn}_trades_{ex}{suffix}.csv',index=False)
print(navn,ex,suffix,len(df))
