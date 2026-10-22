"""Editable intro/title resources for the verified Project Naga profile."""
import json
import struct
import zlib
from pathlib import Path
from rom import DATA_DIR
from portraits import pc_address,pointer_for,decode_palette,export_png,png_bytes
from fe4_codec import decompress,compress

ARENA=0x700000
ARENA_SIZE=0xa0000
MAGIC=b'FE4BINTROv1'

def assets():return json.loads((DATA_DIR/'intro_assets.json').read_text(encoding='utf-8'))['assets']

def pointer(rom,refs):
    d=rom.data;h=rom.header;values=[]
    for ref in refs:
        if ref['kind']=='long':
            a=ref['address']+h
            if bytes(d[a+3:a+6])!=bytes.fromhex('888b7e'):raise ValueError('Unsupported scene pointer layout.')
            values.append(int.from_bytes(d[a:a+3],'little'))
        else:
            a=ref['low']+h;b=ref['bank']+h
            if d[a-1]!=0xa2 or bytes(d[a+2:a+5])!=bytes.fromhex('86c8a9') or bytes(d[b+1:b+3])!=bytes.fromhex('85ca'):raise ValueError('Unsupported scene loader instructions.')
            values.append(int.from_bytes(d[a:a+2],'little')+(d[b]<<16))
    if not values or len(set(values))!=1:raise ValueError('Scene resource pointers disagree. Reload or use a matching ROM profile.')
    return values[0]

def patch_pointer(rom,refs,value):
    for ref in refs:
        if ref['kind']=='long':a=ref['address']+rom.header;rom.data[a:a+3]=value.to_bytes(3,'little')
        else:
            a=ref['low']+rom.header;b=ref['bank']+rom.header
            rom.data[a:a+2]=(value&65535).to_bytes(2,'little');rom.data[b]=value>>16

def read_stream(rom,refs):
    p=pointer(rom,refs);raw,size=decompress(memoryview(rom.data)[rom.header:],pc_address(p),limit=65536,banked=True)
    return raw,p,size

def write_stream(rom,refs,raw):
    packed=compress(raw)
    if decompress(packed,0,limit=65536)[0]!=raw:raise ValueError('Scene recompression verification failed.')
    if len(packed)>0x8000:raise ValueError('This compressed resource exceeds one 32 KiB half-bank.')
    block=bytes(rom.data[ARENA+rom.header:ARENA+rom.header+ARENA_SIZE])
    if len(rom.data)-rom.header!=0x800000:raise ValueError('Intro/title editing requires the supported 8 MiB ROM.')
    if block.startswith(MAGIC.ljust(16,b'\0')):
        cursor=int.from_bytes(block[16:20],'little');fill=block[20]
        if not 32<=cursor<=ARENA_SIZE or fill not in (0,255):raise ValueError('Intro storage metadata is invalid.')
    else:
        if len(set(block))!=1 or block[0] not in (0,255):raise ValueError('Reserved intro storage is occupied; no ROM data was changed.')
        cursor,fill=32,block[0]
    old,oldpointer,oldsize=read_stream(rom,refs)
    address=pc_address(oldpointer)
    if ARENA+32<=address<ARENA+cursor and len(packed)<=oldsize:
        # FE4Builder streams use output LZ references only, never other streams.
        pass
    else:
        cursor=(cursor+31)&~31
        if cursor%0x8000+len(packed)>0x8000:cursor=(cursor+0x7fff)&~0x7fff
        if cursor+len(packed)>ARENA_SIZE or any(v!=fill for v in block[cursor:cursor+len(packed)]):raise ValueError('Reserved intro storage is full or occupied.')
        address=ARENA+cursor;cursor+=len(packed)
        # Known resources must not already reference the proposed space.
        for entry in assets():
            if entry['kind']=='raw_palette':continue
            for rr in (entry['refs'],entry.get('map_refs',[])):
                if not rr:continue
                p=pc_address(pointer(rom,rr))
                if address<=p<address+len(packed):raise ValueError('Another scene resource references this storage.')
    meta=MAGIC.ljust(16,b'\0')+cursor.to_bytes(4,'little')+bytes([fill])+bytes(11)
    rom.data[ARENA+rom.header:ARENA+rom.header+32]=meta
    rom.data[address+rom.header:address+rom.header+len(packed)]=packed
    patch_pointer(rom,refs,pointer_for(address))

def decode_tiles(raw):
    rows=[[0]*128 for _ in range(((len(raw)//32+15)//16)*8)]
    for t in range(len(raw)//32):
        for y in range(8):
            for x in range(8):rows[t//16*8+y][t%16*8+x]=sum(((raw[t*32+y*2+p//2*16+p%2]>>(7-x))&1)<<p for p in range(4))
    return rows

def encode_tile(rows):
    data=bytearray(32)
    for y in range(8):
        for p in range(4):data[p//2*16+y*2+p%2]=sum(((rows[y][x]>>p)&1)<<(7-x) for x in range(8))
    return bytes(data)

def encode_sheet(rows,size):
    return b''.join(encode_tile([row[t%16*8:t%16*8+8] for row in rows[t//16*8:t//16*8+8]]) for t in range(size//32))

def indexed_png(path):
    """Preserve duplicate palette entries on exports reimported without editing."""
    data=Path(path).read_bytes();position=8;plte=None;compressed=bytearray();header=None
    if not data.startswith(b'\x89PNG'):return None
    while position+12<=len(data):
        length=int.from_bytes(data[position:position+4],'big');kind=data[position+4:position+8];body=data[position+8:position+8+length];position+=length+12
        if kind==b'IHDR':header=struct.unpack('>IIBBBBB',body)
        elif kind==b'PLTE':plte=[tuple(body[i:i+3]) for i in range(0,len(body),3)]
        elif kind==b'IDAT':compressed.extend(body)
        elif kind==b'IEND':break
    if header is None or plte is None:return None
    w,h,depth,kind,_,_,interlace=header
    if kind!=3 or depth!=8 or interlace:return None
    if w*h>1048576:raise ValueError('PNG is too large.')
    raw=zlib.decompress(compressed);rows=[];previous=bytearray(w);offset=0
    for _ in range(h):
        filt=raw[offset];line=bytearray(raw[offset+1:offset+1+w]);offset+=w+1
        for x in range(w):
            a=line[x-1] if x else 0;b=previous[x];c=previous[x-1] if x else 0
            if filt==1:line[x]=(line[x]+a)&255
            elif filt==2:line[x]=(line[x]+b)&255
            elif filt==3:line[x]=(line[x]+(a+b)//2)&255
            elif filt==4:
                p=a+b-c;dist=[abs(p-a),abs(p-b),abs(p-c)];line[x]=(line[x]+(a,b,c)[dist.index(min(dist))])&255
            elif filt!=0:raise ValueError('Unsupported PNG filter.')
        rows.append(list(line));previous=line
    return rows,plte

class IntroAsset:
    def __init__(self,rom,entry):
        self.rom=rom;self.entry=entry;self.key=entry['key']
        if len(rom.data)-rom.header!=0x800000:raise ValueError('This editor currently supports the 8 MiB Project Naga profile.')
        if entry['kind']=='raw_palette':
            a=entry['address']+rom.header;self.raw=bytes(rom.data[a:a+entry['decoded_size']]);self.pointer=None
        else:self.raw,self.pointer,self.compressed_size=read_stream(rom,entry['refs'])
        if len(self.raw)!=entry['decoded_size']:raise ValueError('The resource size does not match the supported scene profile.')
        self.original=self.raw;self.map=None
        if entry.get('map_refs'):self.map,self.map_pointer,_=read_stream(rom,entry['map_refs'])
        if entry['kind']=='caption':self.map=decompress(memoryview(rom.data)[rom.header:],0x415710,limit=1024,banked=True)[0]
        self.original_map=self.map

    def colors(self,index=0):
        from logo_layout import KEYS,PALETTES,colors
        if self.key in KEYS and index in PALETTES:return colors(self.rom)[index*16:index*16+16]
        if self.entry['palette']=='title':
            pal=IntroAsset(self.rom,next(e for e in assets() if e['key']=='title_palette')).raw
            return decode_palette(pal[index*32:index*32+32])
        if self.entry['palette']=='nintendo':
            a=0x20283f+self.rom.header;return decode_palette(bytes(2)+bytes(self.rom.data[a:a+30]))
        return [(v*17,)*3 for v in range(16)]

    def full_colors(self):
        if self.entry['palette']=='title':
            pal=IntroAsset(self.rom,next(e for e in assets() if e['key']=='title_palette')).raw
            return sum((decode_palette(pal[i:i+32]) for i in range(0,256,32)),[])
        return self.colors()*8

    def screen(self):
        e=self.entry;h=e['height'];shift=e.get('scroll_y',0);rows=[[0]*256 for _ in range(h)]
        for y in range(h):
            for x in range(256):
                c=e.get('map_page',0)*1024+(y+shift)//8*32+x//8;v=int.from_bytes(self.map[c*2:c*2+2],'little');t=v&1023
                sx=7-x%8 if v&16384 else x%8;sy=7-(y+shift)%8 if v&32768 else (y+shift)%8
                o=t*32+sy*2
                if o+17>=len(self.raw):continue
                value=sum(((self.raw[o+p//2*16+p%2]>>(7-sx))&1)<<p for p in range(4))
                rows[y][x]=((v>>10)&7)*16+value if value else 0
        return rows

    def caption(self):
        sheet=decode_tiles(self.raw);rows=[[0]*256 for _ in range(16)]
        for c in range(64):
            t=(int.from_bytes(self.map[c*2:c*2+2],'little')&1023)-128
            for y in range(8):rows[c//32*8+y][c%32*8:c%32*8+8]=sheet[t//16*8+y][t%16*8:t%16*8+8]
        return rows

    def rows(self,index=0,readable=True):
        from logo_layout import KEYS,render,colors
        if readable and self.key in KEYS:return render(self.raw,self.key,colors(self.rom),self.rom)
        view=self.entry['view']
        if view=='screen':return self.screen(),self.full_colors()
        if view=='caption':return self.caption(),self.colors()
        if view=='palette':
            colors=decode_palette(bytes(2)+self.raw) if self.entry['kind']=='raw_palette' else sum((decode_palette(self.raw[i:i+32]) for i in range(0,len(self.raw),32)),[])
            width=16;return [list(range(i,min(i+width,len(colors)))) for i in range(0,len(colors),width)],colors
        return decode_tiles(self.raw),self.colors(index)

    def png(self,index=0,readable=True):
        rows,colors=self.rows(index,readable)
        return png_bytes(rows,colors) if self.entry['view'] in ('screen','palette') else export_png(rows,colors)

    def import_png(self,master,path,index=0,readable=True):
        import tkinter as tk
        image=tk.PhotoImage(master=master,file=str(path));expected,colors=self.rows(index,readable)
        if (image.width(),image.height())!=(len(expected[0]),len(expected)):raise ValueError(f'Use a {len(expected[0])} x {len(expected)} PNG exported from this resource.')
        pixels=[[image.get(x,y) for x in range(image.width())] for y in range(image.height())]
        if self.entry['view']=='palette':
            flat=[v for row in pixels for v in row];offset=1 if self.entry['kind']=='raw_palette' else 0
            old=[int.from_bytes(self.raw[i:i+2],'little') for i in range(0,len(self.raw),2)]
            self.raw=b''.join(((old[i]&0x8000)|sum(round(c*31/255)<<s for c,s in zip(rgb,(0,5,10)))).to_bytes(2,'little') for i,rgb in enumerate(flat[offset:]));return
        exact=all(pixels[y][x]==colors[v] and (v==0 or not image.transparency_get(x,y)) for y,row in enumerate(expected) for x,v in enumerate(row))
        if exact:return
        if self.entry['view']=='screen':self.import_screen(pixels,master,image);return
        indexed=indexed_png(path)
        from logo_layout import KEYS,import_pixels
        if readable and self.key in KEYS:
            indices=indexed[0] if indexed and indexed[1]==colors else None
            self.raw=import_pixels(self.raw,self.key,colors,pixels,image,indices,self.rom);return
        if indexed and indexed[1]==colors:rows=indexed[0]
        else:
            rows=[]
            for y,line in enumerate(pixels):rows.append([0 if image.transparency_get(x,y) else min(range(16),key=lambda i:sum((a-b)**2 for a,b in zip(rgb,colors[i]))) for x,rgb in enumerate(line)])
        if any(v>15 for row in rows for v in row):raise ValueError('Tile sheets must use a 16-color palette.')
        if self.entry['view']=='caption':self.set_caption_pixels(rows)
        else:self.raw=encode_sheet(rows,len(self.raw))

    def set_caption_pixels(self,rows):
        data=bytearray(self.raw)
        for c in range(64):
            t=(int.from_bytes(self.map[c*2:c*2+2],'little')&1023)-128
            tile=[row[c%32*8:c%32*8+8] for row in rows[c//32*8:c//32*8+8]]
            data[t*32:t*32+32]=encode_tile(tile)
        self.raw=bytes(data)

    def text(self,text):
        from names import ALPHABET
        d=memoryview(self.rom.data)[self.rom.header:];glyphs=[];width=0
        for char in text:
            if char==' ':glyphs.append((None,4));width+=4;continue
            if char not in ALPHABET:raise ValueError('Use English letters, digits and supported punctuation.')
            i=ALPHABET.index(char);advance=d[0x119971+i]
            if not 1<=advance<=8:raise ValueError('Unsupported font width table.')
            tile=i//8*32+i%8*2;glyph=[]
            for y in range(16):
                row=[]
                for x in range(16):
                    o=0x128000+(tile+y//8*16+x//8)*16+y%8*2;v=((d[o]>>(7-x%8))&1)+2*((d[o+1]>>(7-x%8))&1);row.append(15 if v==3 else 12 if v else 0)
                glyph.append(row)
            glyphs.append((glyph,advance));width+=advance
        if width>248:raise ValueError('This caption is wider than 248 pixels; shorten the line.')
        rows=[[0]*256 for _ in range(16)];cursor=(256-width)//2
        for glyph,advance in glyphs:
            if glyph:
                for y in range(16):
                    for x,v in enumerate(glyph[y]):
                        if v and 0<=cursor+x<256:rows[y][cursor+x]=v
            cursor+=advance
        self.set_caption_pixels(rows)

    def import_screen(self,pixels,master,image):
        e=self.entry;shift=e.get('scroll_y',0);capacity=e['tile_capacity'];palette=self.full_colors();previous=self.screen();newmap=bytearray(self.map);tiles=[];ids={}
        for c in range(len(self.map)//2):
            v=int.from_bytes(self.map[c*2:c*2+2],'little');pal=(v>>10)&7;cy=(c-e.get('map_page',0)*1024)//32*8-shift;cx=c%32*8
            if cy<0 or cy>=len(pixels):
                t=v&1023;source=self.original[t*32:t*32+32]
                tile=[]
                for y in range(8):
                    sy=7-y if v&32768 else y
                    tile.append([sum(((source[sy*2+p//2*16+p%2]>>(7-(7-x if v&16384 else x)))&1)<<p for p in range(4)) for x in range(8)])
            else:
                colors=palette[pal*16:pal*16+16];colors[0]=palette[0]
                tile=[]
                for y in range(8):
                    line=[]
                    for x in range(8):
                        rgb=pixels[cy+y][cx+x];old=previous[cy+y][cx+x]
                        value=old%16 if rgb==palette[old] else min(range(16),key=lambda i:sum((a-b)**2 for a,b in zip(rgb,colors[i])))
                        line.append(0 if image.transparency_get(cx+x,cy+y) else value)
                    tile.append(line)
            # The SNES can reuse a tile with horizontal/vertical flips. Keep
            # that sharing when rebuilding, rather than exhausting VRAM slots.
            variants=[]
            for flip in (0,0x4000,0x8000,0xc000):
                oriented=tile[::-1] if flip&0x8000 else tile
                if flip&0x4000:oriented=[row[::-1] for row in oriented]
                variants.append((encode_tile(oriented),flip))
            raw,flip=min(variants)
            if raw not in ids:
                if len(tiles)>=capacity:raise ValueError(f'This image needs more than {capacity} unique 8x8 tiles. Simplify it or reuse more tiles.')
                ids[raw]=len(tiles);tiles.append(raw)
            newmap[c*2:c*2+2]=((v&0x3c00)|flip|ids[raw]).to_bytes(2,'little')
        self.raw=b''.join(tiles).ljust(capacity*32,b'\0')+self.original[capacity*32:];self.map=bytes(newmap)

    @property
    def dirty(self):return self.raw!=self.original or self.map!=self.original_map

    def apply(self):
        if not self.dirty:return []
        e=self.entry;before=bytes(self.rom.data)
        try:
            if e['kind']=='raw_palette':
                a=e['address']+self.rom.header
                if bytes(self.rom.data[a:a+len(self.original)])!=self.original:raise ValueError('The palette changed; reload before writing.')
                self.rom.data[a:a+len(self.raw)]=self.raw
            else:
                current,_,_=read_stream(self.rom,e['refs'])
                if current!=self.original:raise ValueError('This resource changed; reload before writing.')
                if self.raw!=self.original:write_stream(self.rom,e['refs'],self.raw)
                if e.get('map_refs') and self.map!=self.original_map:
                    if read_stream(self.rom,e['map_refs'])[0]!=self.original_map:raise ValueError('The tilemap changed; reload before writing.')
                    write_stream(self.rom,e['map_refs'],self.map)
            updated=IntroAsset(self.rom,e)
            if updated.raw!=self.raw or updated.map!=self.map:raise ValueError('Saved scene resource verification failed.')
        except Exception:
            self.rom.data[:]=before;raise
        return [e['name']+' graphics/palette updated; scene choreography retained.']
