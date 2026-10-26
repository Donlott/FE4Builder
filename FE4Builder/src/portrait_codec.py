"""FE4 graphics codec, independently implemented from SRC/Decompressor.asm."""
def decompress(data, start, limit=0x10000, direct=None):
    # The game's decoder walks successive 32 KiB windows, keeping the initial half.
    half = start & 0x8000
    pos = (start >> 16)*0x8000 + (start & 0x7fff)
    out=bytearray(); touched=set(); remaining=0; resume=None
    def get():
        nonlocal pos,remaining,resume
        physical=(pos//0x8000)*0x10000+half+(pos%0x8000)
        if not 0<=physical<len(data): raise ValueError('Compressed stream outside ROM')
        value=data[physical];touched.add(physical)
        if direct is not None and not remaining:direct.add(physical)
        pos+=1
        if remaining:
            remaining-=1
            if not remaining:pos=resume;resume=None
        return value
    for _ in range(100000):
        c=get()
        if c<0x40:out.extend(get() for _ in range(c+1))
        elif c<0x50:
            n=(c&15)+2;v=get()
            if v>=0x80:
                kind=((v>>4)&1)*2+((v>>6)&1)*4
                if kind==0:out.append(v&15);v=0
                elif kind==2:out.append((v&15)<<4);v=16
                elif kind==4:out.append(0xf0|(v&15));v=15
                else:out.append(((v&15)<<4)|15);v=31
            for j in range((n+1)//2):
                b=get()
                out.append(((b&0xf0)|(v&15)) if v>=16 else ((v<<4)|(b>>4)))
                if j*2+1<n:out.append((((b&15)<<4)|(v&15)) if v>=16 else ((v<<4)|(b&15)))
        elif c<0x60:
            for _ in range((c&15)+1):b=get();out.extend([b,b])
        elif c<0x80:
            v=get()
            for _ in range((c&15)+2):
                b=get();out.extend([v,b] if c<0x70 else [b,v])
        elif c<0xe0:
            if c<0xc0:n=((c&0x3f)>>2)+2;dist=((c&3)<<8)|get()
            else:
                b=get();n=((c&31)<<1)+(b>>7)+2;dist=((b&127)<<8)|get()
            if dist==0 or dist>len(out):raise ValueError('Invalid graphics back-reference')
            for _ in range(n):out.append(out[-dist])
        elif c<0xf0:
            n=((c&15)<<8)+get()+3;v=get();out.extend([v]*n)
        elif c<0xf8:
            v=get();out.extend([v]*((c&7)+3))
        elif c<0xfe:
            if remaining:raise ValueError('Nested compressed lookback unsupported')
            if c<0xfc:
                b=get();d=get();n=((c&3)<<3)+(b>>5)+3;dist=((b&31)<<8)+d+3
            else:
                b=get();n=((c&1)<<2)+(b>>6)+3;dist=(b&63)+2
            resume=pos;remaining=n;pos-=dist
            if pos<0:raise ValueError('Invalid compressed lookback')
        else:return bytes(out),touched
        if len(out)>limit:raise ValueError('Decoded graphics exceed size limit')
    raise ValueError('Unterminated compressed stream')

def compress(raw):
    """Dynamic-programming encoder: literals, RLE, duplicate, append, LZ77."""
    n=len(raw);cost=[10**9]*(n+1);choice=[None]*n;cost[n]=1
    positions={}
    for i,b in enumerate(raw):positions.setdefault(b,[]).append(i)
    import bisect
    for i in range(n-1,-1,-1):
        def offer(length,encoded):
            c=len(encoded)+cost[i+length]
            if c<cost[i]:cost[i]=c;choice[i]=(length,encoded)
        for l in range(1,min(64,n-i)+1):offer(l,bytes([l-1])+raw[i:i+l])
        run=1
        while run<min(4098,n-i) and raw[i+run]==raw[i]:run+=1
        for l in range(3,run+1):
            offer(l,bytes([0xf0+l-3,raw[i]]) if l<=10 else bytes([0xe0+((l-3)>>8),(l-3)&255,raw[i]]))
        for pairs in range(1,min(16,(n-i)//2)+1):
            s=raw[i:i+pairs*2]
            if all(s[k]==s[k+1] for k in range(0,len(s),2)):offer(pairs*2,bytes([0x50+pairs-1])+s[::2])
            if pairs>=2:
                if len(set(s[::2]))==1:offer(pairs*2,bytes([0x60+pairs-2,s[0]])+s[1::2])
                if len(set(s[1::2]))==1:offer(pairs*2,bytes([0x70+pairs-2,s[1]])+s[::2])
        ps=positions[raw[i]];end=bisect.bisect_left(ps,i)
        bestshort=1;bestlong=1
        for prev in reversed(ps[max(0,end-600):end]):
            dist=i-prev
            if dist>32767:break
            l=1
            while l<min(65,n-i) and raw[i+l]==raw[i+l-dist]:l+=1
            if dist<=1023 and l>bestshort:
                for count in range(max(2,bestshort+1),min(l,17)+1):offer(count,bytes([0x80+((count-2)<<2)+(dist>>8),dist&255]))
                bestshort=min(l,17)
            if l>bestlong:
                for count in range(max(2,bestlong+1),l+1):offer(count,bytes([0xc0+((count-2)>>1),(((count-2)&1)<<7)+(dist>>8),dist&255]))
                bestlong=l
            if bestshort>=min(17,n-i) and bestlong>=min(65,n-i):break
    out=bytearray();i=0
    while i<n:l,b=choice[i];out.extend(b);i+=l
    out.append(255);return bytes(out)
