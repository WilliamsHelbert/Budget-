import sys
sys.path.insert(0,'.')
import continuation_model as cm
cm.DATA_DIR=sys.argv[2] if len(sys.argv)>2 else '.'
ex=sys.argv[1]; cm.EXEC=ex; cm.PERIOD=('2024-01-02','2024-12-31')
df=cm.run()
df.to_csv(f'results/2024_trades_{ex}.csv',index=False)
print(ex,len(df))
