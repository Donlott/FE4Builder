"""ROM and PNG operations. File offsets are headerless throughout."""
from pathlib import Path
from dataclasses import dataclass
import hashlib, os, tempfile
from PIL import Image
from codec import decompress, compress
GFX_TABLE=0xAB4F9
PAL_TABLE=0xAB7E1
COUNT=248
class EditorError(ValueError):pass

def rgb(word):return tuple(((word>>s)&31)*255//31 for s in (0,5,10))
def bgr(color):return sum(((v*31+127)//255)<<s for v,s in zip(color,(0,5,10)))
def unpack(raw):
    im=Image.new('P',(64,64))
    for t in range(64):
        row,col=divmod(t,16)
        # First twelve tiles: two rows of the 48-pixel-wide portrait.
        if col<12:x0=(col%6)*8;y0=row*8+(col//6)*32
        else:x0=48+(col%2)*8;y0=row*8+(32 if col>=14 else 0)
        for y in range(8):
            for x in range(8):
                v=sum(((raw[t*32+y*2+(k%2)+(16 if k>=2 else 0)]>>(7-x))&1)<<k for k in range(4))
                im.putpixel((x0+x,y0+y),v)
    return im

def pack(im):
    raw=bytearray(2048)
    for t in range(64):
        row,col=divmod(t,16)
        if col<12:x0=(col%6)*8;y0=row*8+(col//6)*32
        else:x0=48+(col%2)*8;y0=row*8+(32 if col>=14 else 0)
        for y in range(8):
            for x in range(8):
                v=im.getpixel((x0+x,y0+y))
                for k in range(4):raw[t*32+y*2+(k%2)+(16 if k>=2 else 0)]|=((v>>k)&1)<<(7-x)
    return bytes(raw)

def apply_palette(im,palette,shared_grey=True):
    colors=[rgb(int.from_bytes(palette[i:i+2],'little')) for i in range(0,32,2)]
    if shared_grey:colors[14]=rgb(0x35ad)
    im.putpalette([c for color in colors for c in color]+[0]*720)
    im.info['transparency']=0
    return im

@dataclass
class Portrait:
    id:int
    gfx:int
    pal:int
    raw:bytes
    palette:bytes
    touched:set
    shared_grey:bool=True
    def image(self):return apply_palette(unpack(self.raw),self.palette,self.shared_grey)

class ROM:
    def __init__(self,path):
        self.path=Path(path).resolve();full=self.path.read_bytes()
        if len(full)%0x8000==512:self.header=full[:512];body=full[512:]
        elif len(full)%0x8000==0:self.header=b'';body=full
        else:raise EditorError('ROM length is not a whole number of SNES banks (with optional 512-byte header).')
        if len(body)<0x400000 or len(body)>0x800000:raise EditorError('Supported ROM size: 4–8 MiB.')
        self.data=bytearray(body);self.original=full;self.sha256=hashlib.sha256(full).hexdigest()
        self.exhirom=(body[0xffd5]&0x2f)==0x25
        if body[0xffc0:0xffc0+11]!=b'FIREEMBLEM4':raise EditorError('FE4 internal title not found.')
        if len(body)>0x400000 and not self.exhirom:raise EditorError('Expanded ROM is not marked ExHiROM.')
        if body[0xab335:0xab33c]!=bytes.fromhex('bf f9 b4 8a 85 65 bf'):raise EditorError('Portrait loader differs from the supported FE4 layout.')
        if hashlib.sha256(body[0xaa02:0xad24]).hexdigest()!='2884bcf9f548bc28015d2cb4407c034ae6fd9dadd4ba07d5e7d5058756ed2457':
            raise EditorError('Graphics decoder differs from the supported FE4 profile.')
        common_sites={0x9a183:bytes.fromhex('f0'),0xb8374:bytes.fromhex('9f d7 55 7f'),0xbd780:bytes.fromhex('8d 5c 02'),0x16cad5:bytes.fromhex('8d fc 01'),0x16cb04:bytes.fromhex('8d fc 01')}
        unlocked_sites={0x9a183:bytes.fromhex('d0'),0xb8374:bytes.fromhex('ea ea ea ea'),0xbd780:bytes.fromhex('ea ea ea'),0x16cad5:bytes.fromhex('ea ea ea'),0x16cb04:bytes.fromhex('ea ea ea')}
        if all(body[a:a+len(b)]==b for a,b in common_sites.items()):self.shared_grey=True
        elif all(body[a:a+len(b)]==b for a,b in unlocked_sites.items()):self.shared_grey=False
        else:raise EditorError('Unrecognized or partial common portrait-colour patch. Supported profiles: original shared grey or documented five-site palette unlock.')
        self.portraits=[]
        for i in range(COUNT):
            g=self.address(int.from_bytes(body[GFX_TABLE+3*i:GFX_TABLE+3*i+3],'little'))
            p=self.address(int.from_bytes(body[PAL_TABLE+3*i:PAL_TABLE+3*i+3],'little'))
            raw,touched=decompress(body,g,2048)
            if len(raw)!=2048 or p+32>len(body):raise EditorError(f'Portrait {i:02X} has an unsupported size or pointer.')
            self.portraits.append(Portrait(i,g,p,raw,bytes(body[p:p+32]),touched,self.shared_grey))
        self.pending={};self.arena=None;self.text=None;self.animations=None
        self.optimize_portraits=False;self._compression_cache={}
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
    def import_png(self,idx,path,quantize=False):
        im=Image.open(path);im.load()
        if im.format!='PNG':raise EditorError('Choose a PNG file.')
        if im.size!=(64,64):raise EditorError('PNG must be 64×64: portrait at left (48×64), animation tiles at right (16×64). Export a sheet first.')
        old=self.portraits[idx];palette=bytearray(old.palette)
        slots=(list(range(1,14))+[15]) if self.shared_grey else list(range(1,16))
        limit=len(slots)
        # Exact exported indexed sheets preserve indices, including identical colours.
        pal=im.getpalette()
        if im.mode=='P' and pal and max(im.getdata())<16 and im.info.get('transparency') in (None,0):
            if self.shared_grey and rgb(bgr(tuple(pal[42:45])))!=rgb(0x35ad) and 14 in im.getdata():
                raise EditorError('Index 14 is the shared grey colour. Use RGB PNG import or retain the exported palette.')
            for i in slots:palette[i*2:i*2+2]=bgr(pal[i*3:i*3+3]).to_bytes(2,'little')
            indexed=im.copy();notice='Indexed palette retained; colours rounded to SNES precision.'
        else:
            rgba=im.convert('RGBA');pixels=list(rgba.getdata())
            if any(p[3] not in (0,255) for p in pixels):raise EditorError('Use fully opaque or transparent pixels; partial transparency is unsupported.')
            # For opaque PNGs, the top-left colour is the transparent background key.
            has_alpha=any(p[3]==0 for p in pixels);key=pixels[0][:3]
            words=[None if p[3]==0 or (not has_alpha and p[:3]==key) else bgr(p[:3]) for p in pixels]
            opaque=sorted(set(w for w in words if w is not None and (not self.shared_grey or w!=0x35ad)))
            if len(opaque)>limit:
                if not quantize:raise EditorError(f'PNG uses {len(opaque)} editable colours after SNES conversion; this profile allows {limit}. Enable colour reduction and inspect the preview.')
                src=Image.new('RGB',(len(opaque),1));src.putdata([rgb(w) for w in opaque]);q=src.quantize(colors=limit,method=getattr(Image, 'Quantize', Image).MEDIANCUT)
                opaque=sorted(set(bgr(c) for c in q.convert('RGB').getdata()))
            mapping={w:i for w,i in zip(opaque,slots)}
            for w,i in mapping.items():palette[2*i:2*i+2]=w.to_bytes(2,'little')
            if self.shared_grey:mapping[0x35ad]=14
            indexed=Image.new('P',(64,64));indices=[]
            for w in words:
                if w is None:indices.append(0)
                elif w in mapping:indices.append(mapping[w])
                else:
                    c=rgb(w);best=min(opaque,key=lambda a:sum((x-y)**2 for x,y in zip(c,rgb(a))));indices.append(mapping[best])
            indexed.putdata(indices);notice='Colours converted to SNES precision. Index 0 is transparent.'+(' Index 14 is shared grey.' if self.shared_grey else ' All 15 opaque palette entries are editable.')
        if self.shared_grey:palette[28:30]=old.palette[28:30]
        raw=pack(indexed)
        self.pending[idx]=(raw,bytes(palette))
        return apply_palette(indexed,bytes(palette),self.shared_grey),notice
    def image(self,idx):
        if idx in self.pending:
            raw,pal=self.pending[idx];return apply_palette(unpack(raw),pal,self.shared_grey)
        return self.portraits[idx].image()
    def packing_plan(self):
        from repack import Plan
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
        if self.text is not None and self.text.dirty:
            log.extend(self.text.apply(data))
        if self.animations is not None and self.animations.dirty:
            log.extend(self.animations.apply(data))
        if self.optimize_portraits:
            for q in self.portraits:
                g=self.address(int.from_bytes(data[GFX_TABLE+3*q.id:GFX_TABLE+3*q.id+3],'little'))
                p=self.address(int.from_bytes(data[PAL_TABLE+3*q.id:PAL_TABLE+3*q.id+3],'little'))
                expected=self.pending.get(q.id,(q.raw,q.palette))
                if decompress(data,g,2048)[0]!=expected[0] or bytes(data[p:p+32])!=expected[1]:
                    raise EditorError('Other staged edits overlap packed portrait data. No file changed.')
        if log:
            if len(data)&(len(data)-1):raise EditorError('Checksum update currently requires a power-of-two ROM size.')
            headers=[0xffdc]+([0x40ffdc] if self.exhirom else [])
            for h in headers:data[h:h+4]=b'\xff\xff\x00\x00'
            checksum=sum(data)&65535
            for h in headers:data[h:h+4]=(checksum^65535).to_bytes(2,'little')+checksum.to_bytes(2,'little')
        return self.header+data,log
    def save(self,path):
        path=Path(path).resolve()
        if path==self.path or (path.exists() and os.path.samefile(path,self.path)):raise EditorError('Choose a different output filename. The input ROM is protected.')
        blob,log=self.build()
        fd,temp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
            os.replace(temp,path)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        return log
