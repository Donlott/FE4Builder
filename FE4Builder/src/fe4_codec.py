"""FE4 byte-stream decompression, following ulti-mage's SRC/Decompressor.asm."""
def decompress(data,start,limit=16384,banked=False,read_addresses=None):
    position=start
    returned=None
    remaining=0
    consumed=start
    output=bytearray()
    commands=0

    def read(check=True):
        nonlocal position,remaining,returned,consumed
        physical=position
        if banked:
            chunk=(start&0x7fff)+(position-start)
            physical=(start&~0xffff)+(start&0x8000)+(chunk//0x8000)*0x10000+(chunk%0x8000)
        if not 0<=physical<len(data):
            raise ValueError('Compressed graphics read outside the ROM.')
        value=data[physical]
        if read_addresses is not None:
            read_addresses.add(physical)
        position+=1
        if remaining and check:
            remaining-=1
            if remaining==0:
                position=returned
                returned=None
        elif not remaining:
            consumed=max(consumed,position)
        return value

    def lookback(distance,length):
        if distance==0 or distance>len(output):
            raise ValueError('Invalid graphics back-reference.')
        for _ in range(length):
            output.append(output[-distance])

    while True:
        commands+=1
        if commands>65536 or len(output)>limit:
            raise ValueError('Compressed graphics exceeded the decode limit.')
        command=read()
        if command<0x40:
            output.extend(read() for _ in range(command+1))
        elif command<0x50:
            count=(command&15)+2
            variable=read()
            if variable>=0x80:
                fixed=15 if variable&0x40 else 0
                if variable&0x10:
                    output.append(((variable&15)<<4)|fixed)
                    variable=0x10|fixed
                else:
                    output.append((fixed<<4)|(variable&15))
                    variable=fixed
            high=not variable&0x10
            fixed=variable&15
            while count:
                value=read()
                for nibble in (value>>4,value&15):
                    output.append((fixed<<4)|nibble if high else (nibble<<4)|fixed)
                    count-=1
                    if not count:
                        break
        elif command<0x60:
            for _ in range((command&15)+1):
                value=read()
                output.extend((value,value))
        elif command<0x80:
            fixed=read()
            for _ in range((command&15)+2):
                value=read()
                output.extend((fixed,value) if command<0x70 else (value,fixed))
        elif command<0xc0:
            distance=((command&3)<<8)|read()
            lookback(distance,((command&0x3f)>>2)+2)
        elif command<0xe0:
            second=read()
            distance=((second&0x7f)<<8)|read()
            lookback(distance,((command&31)<<1)+(second>>7)+2)
        elif command<0xf0:
            length=((command&15)<<8)+read()+3
            value=read()
            output.extend(bytes([value])*length)
        elif command<0xf8:
            value=read()
            output.extend(bytes([value])*((command&7)+3))
        elif command<0xfe:
            if command<0xfc:
                second=read(False)
                distance=((second&31)<<8)+read(False)+3
                count=((command&3)<<3)+(second>>5)+3
            else:
                second=read(False)
                distance=(second&63)+2
                count=((command&1)<<2)+(second>>6)+3
            returned=position
            position-=distance
            remaining=count
        else:
            if len(output)>limit:
                raise ValueError('Graphics exceeded the decode limit.')
            return bytes(output),consumed-start

def compress(data):
    """Encode using literals, byte runs and overlapping LZ back-references."""
    output=bytearray()
    literal=bytearray()
    positions={}
    i=0
    def flush():
        if literal:
            output.append(len(literal)-1)
            output.extend(literal)
            literal.clear()
    def register(position):
        key=data[position:position+3]
        bucket=positions.setdefault(key,[])
        bucket.append(position)
        if len(bucket)>128:
            del bucket[:-128]
    while i<len(data):
        run=1
        while i+run<len(data) and data[i+run]==data[i] and run<4098:
            run+=1
        best=0
        distance=0
        for previous in reversed(positions.get(data[i:i+3],[])):
            dist=i-previous
            if dist>32767:
                continue
            length=0
            while length<65 and i+length<len(data) and data[i+length]==data[i+length-dist]:
                length+=1
            if length>best:
                best,distance=length,dist
        if run>=3 and run>=best:
            flush()
            if run<=10:
                output.extend((0xf0+run-3,data[i]))
            else:
                output.extend((0xe0|((run-3)>>8),(run-3)&255,data[i]))
            length=run
        elif best>=3:
            flush()
            length=best
            if distance<=1023:
                length=min(length,17)
                output.extend((0x80|((length-2)<<2)|(distance>>8),distance&255))
            else:
                value=length-2
                output.extend((0xc0|(value>>1),((value&1)<<7)|(distance>>8),distance&255))
        else:
            literal.append(data[i])
            length=1
            if len(literal)==64:
                flush()
        for position in range(i,i+length):
            register(position)
        i+=length
    flush()
    output.append(0xff)
    return bytes(output)
