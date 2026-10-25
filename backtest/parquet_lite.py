"""Minimal ren-Python parquet-læser (pyarrow-output: snappy, dictionary/plain, v1/v2 pages)."""
import struct, numpy as np

class TR:
    def __init__(s, b, p=0): s.b=b; s.p=p
    def byte(s): v=s.b[s.p]; s.p+=1; return v
    def varint(s):
        r=0; sh=0
        while True:
            c=s.b[s.p]; s.p+=1; r|=(c&0x7f)<<sh; sh+=7
            if c<0x80: return r
    def zz(s):
        v=s.varint(); return (v>>1)^-(v&1)
    def val(s,t):
        if t==1: return True
        if t==2: return False
        if t==3: v=s.b[s.p]; s.p+=1; return v
        if t in (4,5,6): return s.zz()
        if t==7: v=struct.unpack('<d',s.b[s.p:s.p+8])[0]; s.p+=8; return v
        if t==8: n=s.varint(); v=bytes(s.b[s.p:s.p+n]); s.p+=n; return v
        if t in (9,10):
            h=s.byte(); n=h>>4; et=h&15
            if n==15: n=s.varint()
            return [ (s.byte()==1) if et in (1,2) else s.val(et) for _ in range(n)]
        if t==11:
            n=s.varint()
            if n==0: return {}
            kv=s.byte(); return {s.val(kv>>4): s.val(kv&15) for _ in range(n)}
        if t==12: return s.struct()
        raise ValueError(t)
    def struct(s):
        d={}; fid=0
        while True:
            h=s.byte()
            if h==0: return d
            t=h&15; dl=h>>4
            fid = fid+dl if dl else s.zz()
            d[fid]=s.val(t)

def snappy(b):
    p=0; n=0; sh=0
    while True:
        c=b[p]; p+=1; n|=(c&0x7f)<<sh; sh+=7
        if c<0x80: break
    o=bytearray(); L=len(b)
    while p<L:
        t=b[p]; p+=1; k=t&3
        if k==0:
            ln=t>>2
            if ln>=60:
                nb=ln-59; ln=int.from_bytes(b[p:p+nb],'little'); p+=nb
            ln+=1; o+=b[p:p+ln]; p+=ln; continue
        if k==1: ln=((t>>2)&7)+4; off=((t>>5)<<8)|b[p]; p+=1
        elif k==2: ln=(t>>2)+1; off=b[p]|(b[p+1]<<8); p+=2
        else: ln=(t>>2)+1; off=int.from_bytes(b[p:p+4],'little'); p+=4
        st=len(o)-off
        if off>=ln: o+=o[st:st+ln]
        else:
            pat=o[st:]; o+=(pat*(ln//off+1))[:ln]
    assert len(o)==n
    return bytes(o)

def hybrid(b,p,end,bw,count):
    out=np.empty(count,np.int64); i=0; byw=(bw+7)//8
    while i<count and p<end:
        h=0; sh=0
        while True:
            c=b[p]; p+=1; h|=(c&0x7f)<<sh; sh+=7
            if c<0x80: break
        if h&1:
            g=h>>1; nb=g*bw; raw=np.frombuffer(b[p:p+nb],np.uint8); p+=nb
            bits=np.unpackbits(raw,bitorder='little').reshape(-1,bw) if bw else np.zeros((g*8,0),np.uint8)
            v=(bits.astype(np.int64)<<np.arange(bw)).sum(1)
            m=min(len(v),count-i); out[i:i+m]=v[:m]; i+=m
        else:
            r=h>>1; v=int.from_bytes(b[p:p+byw],'little'); p+=byw
            m=min(r,count-i); out[i:i+m]=v; i+=m
    return out

DT={1:np.int32,2:np.int64,4:np.float32,5:np.float64}

def dec(codec,b,usize):
    if codec==0: return b
    if codec==1: return snappy(b)
    if codec==2:
        import gzip; return gzip.decompress(b)
    if codec==6:
        import ctypes
        global _Z
        try: _Z
        except NameError:
            _Z=ctypes.CDLL("libzstd.so.1"); _Z.ZSTD_decompress.restype=ctypes.c_size_t
            _Z.ZSTD_decompress.argtypes=[ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_size_t]
            _Z.ZSTD_isError.argtypes=[ctypes.c_size_t]
        out=ctypes.create_string_buffer(usize); src=bytes(b)
        r=_Z.ZSTD_decompress(out,usize,src,len(src))
        if _Z.ZSTD_isError(r): raise ValueError("zstd-fejl")
        return out.raw[:r]
    raise ValueError(f"codec {codec} ikke understøttet")

def read(path):
    b=open(path,'rb').read()
    n=struct.unpack('<I',b[-8:-4])[0]
    fm=TR(b[-8-n:-8]).struct()
    schema=fm[2]
    leaves=[e for e in schema[1:]]
    names=[e[4].decode() for e in leaves]
    opt={e[4].decode(): e.get(3,0)==1 for e in leaves}
    cols={k:[] for k in names}
    for rg in fm[4]:
        for cc in rg[1]:
            md=cc[3]; typ=md[1]; codec=md[4]; name=md[3][0].decode(); nv=md[5]
            p=md.get(11, md[9]); dt=DT[typ]; dic=None; got=0; parts=[]
            while got<nv:
                tr=TR(b,p); ph=tr.struct(); p=tr.p; cs=ph[3]; us=ph[2]; pt=ph[1]
                raw=b[p:p+cs]; p+=cs
                if pt==2:
                    dic=np.frombuffer(dec(codec,raw,us),dt).copy(); continue
                if pt==0:
                    h=ph[5]; cnt=h[1]; enc=h[2]; d=dec(codec,raw,us); q=0
                    if opt[name]:
                        ln=struct.unpack('<I',d[:4])[0]; dl=hybrid(d,4,4+ln,1,cnt); q=4+ln
                        nn=int(dl.sum())
                    else: nn=cnt
                elif pt==3:
                    h=ph[8]; cnt=h[1]; enc=h[4]; dlb=h[5]; rlb=h.get(6,0)
                    lv=raw[:dlb+rlb]; body=raw[dlb+rlb:]
                    if h.get(7,True): body=dec(codec,body,us-dlb-rlb)
                    nn=cnt-h.get(2,0)
                    if h.get(2,0): raise ValueError("nulls ikke understøttet")
                    d=body; q=0
                else: raise ValueError(pt)
                if nn!=cnt: raise ValueError("nulls ikke understøttet")
                if enc==0: v=np.frombuffer(d[q:q+nn*dt().itemsize],dt)
                elif enc in (2,8):
                    bw=d[q]; idx=hybrid(d,q+1,len(d),bw,nn); v=dic[idx]
                else: raise ValueError(f"encoding {enc}")
                parts.append(v); got+=cnt
            cols[name].append(np.concatenate(parts))
    out={k:np.concatenate(v) for k,v in cols.items()}
    tunit=None
    for e in leaves:
        lt=e.get(10)
        if lt and 8 in lt:  # TIMESTAMP
            u=lt[8][2]; tunit='ms' if 1 in u else ('us' if 2 in u else 'ns'); tname=e[4].decode()
    return out, (tname,tunit) if tunit else None

def read_pandas(path):
    import pandas as pd
    out,ts=read(path)
    df=pd.DataFrame(out)
    if ts:
        df[ts[0]]=pd.to_datetime(df[ts[0]].astype(np.int64),unit=ts[1],utc=True)
    return df
