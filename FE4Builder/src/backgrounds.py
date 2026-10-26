"""Dialogue background artwork: native descriptors, fixed palettes and private storage."""
import hashlib,json
from rom import DATA_DIR
from portraits import pc_address,pointer_for,decode_palette,png_bytes
from fe4_codec import decompress,compress
from intro_graphics import IntroAsset
from event_commands import BACKGROUNDS

TABLE=0xabacf
ARENA=0x690000
SLOT_SIZE=0x10000
MAGIC=b'FE4BBACKGROUND1'.ljust(16,b'\0')
# Loader verified from the native ROM: descriptor offsets 3/6/12 are
# background 4bpp tiles / raw CGRAM palette / 32x11 picture map.
GUARD_START=0xabb3e

def signature(block):return hashlib.sha256(block[:32]+block[64:]).digest()

def profile(rom):
    metadata=json.loads((DATA_DIR/'backgrounds.json').read_text(encoding='utf-8'))
    if len(rom.data)-rom.header!=0x800000:raise ValueError('Background editing currently requires the 8 MiB Project Naga profile.')
    start=GUARD_START+rom.header
    if hashlib.sha256(rom.data[start:start+metadata['loader_length']]).hexdigest()!=metadata['loader_sha256']:
        raise ValueError('The dialogue background loader differs from the supported profile.')
    return metadata

class Background:
    def __init__(self,rom,index):
        if index not in BACKGROUNDS:raise ValueError('Unknown dialogue background.')
        metadata=profile(rom);self.rom=rom;self.index=index;self.name=BACKGROUNDS[index]
        self.entry=dict(height=88,tile_capacity=512 if index!=5 else 448)
        at=TABLE+index*3+rom.header;self.table_bytes=bytes(rom.data[at:at+3])
        pointer=int.from_bytes(self.table_bytes,'little');self.descriptor_address=pc_address(pointer)
        if self.descriptor_address not in (metadata['descriptors'][index],ARENA+index*SLOT_SIZE+128):raise ValueError('Background descriptor has moved outside the supported layout.')
        start=self.descriptor_address+rom.header;self.descriptor=bytes(rom.data[start:start+15])
        if len(self.descriptor)!=15:raise ValueError('Truncated background descriptor.')
        def ptr(offset):return pc_address(int.from_bytes(self.descriptor[offset:offset+3],'little'))
        data=memoryview(rom.data)[rom.header:]
        self.raw=decompress(data,ptr(3),limit=16384,banked=True)[0]
        self.map=decompress(data,ptr(12),limit=704,banked=True)[0]
        if len(self.raw)!=self.entry['tile_capacity']*32 or len(self.map)!=704:raise ValueError('Unexpected background resource sizes.')
        if any((int.from_bytes(self.map[i:i+2],'little')&1023)>=self.entry['tile_capacity'] for i in range(0,704,2)):raise ValueError('Background map references a tile outside its sheet.')
        at=ptr(6)+rom.header;self.palette_raw=bytes(rom.data[at:at+512])
        if len(self.palette_raw)!=512:raise ValueError('Truncated background palette.')
        self.palette=sum((decode_palette(self.palette_raw[i:i+32]) for i in range(0,512,32)),[])
        self.palette[0]=(0,0,0) # Native loader explicitly clears CGRAM color 0.
        self.original=self.raw;self.original_map=self.map
        self.storage_snapshot=bytes(rom.data[ARENA+index*SLOT_SIZE+rom.header:ARENA+(index+1)*SLOT_SIZE+rom.header])
        if self.descriptor_address>=ARENA:
            if self.storage_snapshot[:16]!=MAGIC or self.storage_snapshot[32:64]!=signature(self.storage_snapshot):raise ValueError('Private background storage is invalid.')
    screen=IntroAsset.screen
    import_screen=IntroAsset.import_screen
    def full_colors(self):return list(self.palette)
    def png(self):return png_bytes(self.screen(),self.palette)
    def palette_png(self):return png_bytes([list(range(i,i+16)) for i in range(0,128,16)],self.palette,16)
    def import_png(self,master,path):
        import tkinter as tk
        image=tk.PhotoImage(master=master,file=str(path))
        if (image.width(),image.height())!=(256,88):raise ValueError('Import a 256 × 88 PNG. Export this background as a template.')
        if any(image.transparency_get(x,y) for y in range(88) for x in range(256)):raise ValueError('Use an opaque PNG; dialogue backgrounds do not support image alpha.')
        pixels=[[image.get(x,y) for x in range(256)] for y in range(88)]
        before=self.screen()
        if all(rgb==self.palette[before[y][x]] for y,line in enumerate(pixels) for x,rgb in enumerate(line)):return
        old_raw,old_map=self.raw,self.map
        try:self.import_screen(pixels,master,image)
        except Exception:self.raw,self.map=old_raw,old_map;raise
    @property
    def dirty(self):return self.raw!=self.original or self.map!=self.original_map
    def apply(self):
        if not self.dirty:return []
        fresh=Background(self.rom,self.index)
        if (fresh.table_bytes,fresh.descriptor,fresh.original,fresh.original_map,fresh.palette_raw,fresh.storage_snapshot)!=(self.table_bytes,self.descriptor,self.original,self.original_map,self.palette_raw,self.storage_snapshot):raise ValueError('Background data changed; reload before saving.')
        block=self.storage_snapshot
        if block[:16]==MAGIC:
            if block[32:64]!=signature(block):raise ValueError('Private background storage was modified.')
            fill=block[16]
        elif len(set(block))==1 and block[0] in (0,255):fill=block[0]
        else:raise ValueError('Reserved background storage is occupied. No ROM data was changed.')
        gfx=compress(self.raw);tilemap=compress(self.map)
        if len(gfx)>0x7f00 or len(tilemap)>0x400:raise ValueError('Compressed background exceeds its private storage capacity.')
        for packed,raw in ((gfx,self.raw),(tilemap,self.map)):
            if decompress(packed,0,limit=16384)[0]!=raw:raise ValueError('Background recompression check failed.')
        base=ARENA+self.index*SLOT_SIZE;new=bytearray([fill])*SLOT_SIZE
        new[:64]=bytes(64);new[:16]=MAGIC;new[16]=fill
        descriptor=bytearray(self.descriptor)
        descriptor[3:6]=pointer_for(base+256).to_bytes(3,'little')
        descriptor[12:15]=pointer_for(base+0x8000).to_bytes(3,'little')
        new[128:143]=descriptor;new[256:256+len(gfx)]=gfx;new[0x8000:0x8000+len(tilemap)]=tilemap
        new[32:64]=signature(new)
        before=bytes(self.rom.data)
        try:
            h=self.rom.header;self.rom.data[base+h:base+h+SLOT_SIZE]=new
            at=TABLE+self.index*3+h;self.rom.data[at:at+3]=pointer_for(base+128).to_bytes(3,'little')
            check=Background(self.rom,self.index)
            if (check.raw,check.map)!=(self.raw,self.map):raise ValueError('Saved background verification failed.')
        except Exception:self.rom.data[:]=before;raise
        return [f'{self.name}: replaced background artwork; shared originals, palette, dialogue and transitions preserved.']
