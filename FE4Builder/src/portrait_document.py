"""Studio portrait storage engine adapted to FE4Builder's live ROM and history.

Derived from the contributed FE4 Modding Studio core; file offsets here exclude
the copier header. Image conversion and UI live in portrait_window.py.
"""
from pathlib import Path
from dataclasses import dataclass
import hashlib
from portrait_codec import decompress, compress
GFX_TABLE=0xAB4F9
PAL_TABLE=0xAB7E1
COUNT=248
class EditorError(ValueError):pass

@dataclass
class Portrait:
    id:int
    gfx:int
    pal:int
    raw:bytes
    palette:bytes
    touched:set
    shared_grey:bool=True

class PortraitDocument:
    def __init__(self,rom):
        self.path=Path(rom.path).resolve();full=bytes(rom.data)
        self.snapshot=full
        if len(full)%0x8000==512:self.header=full[:512];body=full[512:]
        elif len(full)%0x8000==0:self.header=b'';body=full
        else:raise EditorError('ROM length is not a whole number of SNES banks (with optional 512-byte header).')
        if len(body)<0x400000 or len(body)>0x800000:raise EditorError('Supported ROM size: 4–8 MiB.')
        self.data=bytearray(body)
        self.exhirom=(body[0xffd5]&0x2f)==0x25
        if body[0xffc0:0xffc0+11]!=b'FIREEMBLEM4':raise EditorError('FE4 internal title not found.')
        if len(body)>0x400000 and not self.exhirom:raise EditorError('Expanded ROM is not marked ExHiROM.')
        self.shared_grey=self.validate_profile(body)
        self.portraits=[]
        for i in range(COUNT):
            g=self.address(int.from_bytes(body[GFX_TABLE+3*i:GFX_TABLE+3*i+3],'little'))
            p=self.address(int.from_bytes(body[PAL_TABLE+3*i:PAL_TABLE+3*i+3],'little'))
            raw,touched=decompress(body,g,2048)
            if len(raw)!=2048 or p+32>len(body):raise EditorError(f'Portrait {i:02X} has an unsupported size or pointer.')
            self.portraits.append(Portrait(i,g,p,raw,bytes(body[p:p+32]),touched,self.shared_grey))
        self.pending={};self.arena=None
        self.optimize_portraits=False;self._compression_cache={}
    @staticmethod
    def validate_profile(body):
        if body[0xab335:0xab33c]!=bytes.fromhex('bf f9 b4 8a 85 65 bf'):raise EditorError('Portrait loader differs from the supported FE4 layout.')
        if hashlib.sha256(body[0xaa02:0xad24]).hexdigest()!='2884bcf9f548bc28015d2cb4407c034ae6fd9dadd4ba07d5e7d5058756ed2457':
            raise EditorError('Graphics decoder differs from the supported FE4 profile.')
        common_sites={0x9a183:bytes.fromhex('f0'),0xb8374:bytes.fromhex('9f d7 55 7f'),0xbd780:bytes.fromhex('8d 5c 02'),0x16cad5:bytes.fromhex('8d fc 01'),0x16cb04:bytes.fromhex('8d fc 01')}
        unlocked_sites={0x9a183:bytes.fromhex('d0'),0xb8374:bytes.fromhex('ea ea ea ea'),0xbd780:bytes.fromhex('ea ea ea'),0x16cad5:bytes.fromhex('ea ea ea'),0x16cb04:bytes.fromhex('ea ea ea')}
        if all(body[a:a+len(b)]==b for a,b in common_sites.items()):return True
        elif all(body[a:a+len(b)]==b for a,b in unlocked_sites.items()):return False
        else:raise EditorError('Unrecognized or partial common portrait-colour patch. Supported profiles: original shared grey or documented five-site palette unlock.')

    def address(self,pointer):
        bank=pointer>>16;low=pointer&65535
        if bank>=0xc0:offset=pointer&0x3fffff
        elif 0x80<=bank<=0xbf and low>=0x8000:offset=pointer&0x3fffff
        elif self.exhirom and 0x40<=bank<=0x7d:offset=pointer
        else:raise EditorError(f'Unsupported SNES pointer ${pointer:06X}')
        if offset>=len(self.data):raise EditorError('Pointer outside ROM')
        return offset
    def pointer(self,offset):
        if offset<0x400000:return offset|0xc00000
        if self.exhirom and offset<0x7e0000:return offset
        raise EditorError('Allocation is not in supported mapped ROM space.')
    def reserve(self,start,end):
        if not 0x10000<=start<end<=len(self.data):raise EditorError('Invalid reservation range.')
        self.pointer(start);self.pointer(end-1)
        if start<0x400000<end:raise EditorError('Reservation cannot cross the 4 MiB mapping boundary.')
        b=self.data[start:end]
        if not(all(v==0 for v in b) or all(v==255 for v in b)):raise EditorError('Reserve only a uniformly 00- or FF-filled region.')
        protected=set(range(GFX_TABLE,PAL_TABLE+COUNT*3))
        for p in self.portraits:protected.update(p.touched);protected.update(range(p.pal,p.pal+32))
        if any(start<=p<end for p in protected):raise EditorError('Region overlaps portrait data or pointer tables.')
        for h in (0xffb0,0x40ffb0):
            if start<h+80 and end>h:raise EditorError('Region overlaps an internal ROM header.')
        self.arena=(start,end)
    def stage(self,idx,sheet,colors):
        from portraits import encode_tiles,encode_palette
        raw,palette=encode_tiles(sheet),encode_palette(colors)
        old=self.portraits[idx]
        if self.shared_grey:
            palette=palette[:28]+old.palette[28:30]+palette[30:]
        if (raw,palette)==(old.raw,old.palette):self.pending.pop(idx,None)
        else:self.pending[idx]=(raw,palette)

    @property
    def dirty(self):return bool(self.pending or self.optimize_portraits)

    def commit(self,rom):
        # Other editors/history or an external program may have changed the ROM.
        if bytes(rom.data)!=self.snapshot:
            raise EditorError('The ROM changed while the portrait editor was open. Close and reopen the portrait editor before writing.')
        blob,log=self.build()
        before=bytes(rom.data)
        try:
            rom.data[:]=blob
            rom.save_original('Portrait editor: '+', '.join(f'{i:02X}' for i in sorted(self.pending)),log)
        except (ValueError,OSError):
            rom.data[:]=before
            raise
        return log

    def packing_plan(self):
        from portrait_packing import Plan
        return Plan(self)
    def build(self):
        data=bytearray(self.data);log=[];cursor=self.arena[0] if self.arena else None
        def alloc(blob):
            nonlocal cursor
            if cursor is None:raise EditorError('Replacement needs separate storage. Use “Reserve space…” to designate unused ROM space, then save again. No file has been changed.')
            # Keep each newly encoded stream within one 32 KiB window.
            if cursor//0x8000!=(cursor+len(blob)-1)//0x8000:cursor=(cursor//0x8000+1)*0x8000
            if cursor+len(blob)>self.arena[1]:raise EditorError('Reserved space is full.')
            p=cursor;cursor+=len(blob);data[p:cursor]=blob;return p
        if self.optimize_portraits:
            log.extend(self.packing_plan().apply(self,data))
        else:
            written_graphics={}
            for idx,(raw,pal) in sorted(self.pending.items()):
                old=self.portraits[idx];g=old.gfx;p=old.pal
                if raw!=old.raw and (g,raw) not in written_graphics:
                    encoded=compress(raw)
                    check,_=decompress(encoded,0,2048)
                    if check!=raw:raise EditorError('Internal encoder verification failed.')
                    half=g&0x8000;logical=(g>>16)*0x8000+(g&0x7fff)
                    addresses=[((logical+j)//0x8000)*0x10000+half+((logical+j)%0x8000) for j in range(len(encoded))]
                    target=set(addresses)
                    # A compressed lookback in a different portrait can also reference this stream.
                    # Exact aliases may share this write only when every affected slot
                    # expects the same replacement. Other streams/lookbacks remain protected.
                    conflicts=any(
                        (bool(target&q.touched) and not (
                            q.gfx==old.gfx and self.pending.get(q.id,(q.raw,q.palette))[0]==raw))
                        or bool(target&set(range(q.pal,q.pal+32)))
                        for q in self.portraits)
                    if target<=old.touched and not conflicts:
                        for a,b in zip(addresses,encoded):data[a]=b
                        written_graphics[(old.gfx,raw)]=True
                    else:
                        g=alloc(encoded);at=GFX_TABLE+idx*3;data[at:at+3]=self.pointer(g).to_bytes(3,'little')
                    log.append(f'{idx:02X}: graphics {len(encoded)} bytes at {g:06X}')
                if pal!=old.palette:
                    if any(q.id!=idx and (set(range(p,p+32))&set(range(q.pal,q.pal+32)) or set(range(p,p+32))&q.touched) for q in self.portraits):
                        p=alloc(pal);at=PAL_TABLE+idx*3;data[at:at+3]=self.pointer(p).to_bytes(3,'little')
                    else:data[p:p+32]=pal
                    log.append(f'{idx:02X}: palette at {p:06X}')
        # Verify every portrait, including ones with shared compressed data.
        for q in self.portraits:
            g=self.address(int.from_bytes(data[GFX_TABLE+3*q.id:GFX_TABLE+3*q.id+3],'little'))
            p=self.address(int.from_bytes(data[PAL_TABLE+3*q.id:PAL_TABLE+3*q.id+3],'little'))
            decoded,_=decompress(data,g,2048);expected=self.pending.get(q.id,(q.raw,q.palette))
            if decoded!=expected[0] or bytes(data[p:p+32])!=expected[1]:raise EditorError(f'Post-write verification failed for portrait {q.id:02X}')
        if log:
            if len(data)&(len(data)-1):raise EditorError('Checksum update currently requires a power-of-two ROM size.')
            headers=[0xffdc]+([0x40ffdc] if self.exhirom else [])
            for h in headers:data[h:h+4]=b'\xff\xff\x00\x00'
            checksum=sum(data)&65535
            for h in headers:data[h:h+4]=(checksum^65535).to_bytes(2,'little')+checksum.to_bytes(2,'little')
        return self.header+data,log
