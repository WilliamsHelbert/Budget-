"""Koer modellen for en periode: python3 run_year.py ES|NQ DATA_DIR FRA TIL NAVN"""
import sys
sys.path.insert(0,'.')
import continuation_model as cm
ex,cm.DATA_DIR,fra,til,navn=sys.argv[1:6]
cm.EXEC=ex; cm.PERIOD=(fra,til)
df=cm.run()
df.to_csv(f'results/{navn}_trades_{ex}.csv',index=False)
print(navn,ex,len(df))
