"""FE4 portraits: character IDs, compressed SNES 4bpp tiles, BGR555 palettes."""
import struct
import zlib
from fe4_codec import decompress,compress

COUNT=248
GRAPHICS_TABLE=0xab4f9
PALETTE_TABLE=0xab7e1
CHARACTER_TABLE=0xb9a88

def pc_address(pointer):
    bank=pointer>>16
    low=pointer&0xffff
    if bank>=0xc0 or (0x80<=bank<=0xbf and low>=0x8000):
        return (pointer&0x3fffff)
    if 0x40<=bank<=0x7d:
        return pointer
    if bank<=0x3f and low>=0x8000:
        return pointer+0x400000
    raise ValueError(f'Unsupported portrait address 0x{pointer:06X}')

def pointer_for(address):
    if address<0x400000:
        return address+0xc00000
    if 0x400000<=address<0x7e0000:
        return address
    raise ValueError('Portrait allocation is outside addressable ExHiROM space.')

def decode_tiles(raw):
    if len(raw)!=2048:
        raise ValueError(f'Unsupported portrait tile size: {len(raw)} bytes (expected 2048).')
    rows=[[0]*128 for _ in range(32)]
    for tile in range(64):
        for y in range(8):
            planes=[raw[tile*32+y*2],raw[tile*32+y*2+1],raw[tile*32+16+y*2],raw[tile*32+17+y*2]]
            for x in range(8):
                rows[(tile//16)*8+y][(tile%16)*8+x]=sum(((plane>>(7-x))&1)<<i for i,plane in enumerate(planes))
    return rows

def encode_tiles(rows):
    if len(rows)!=32 or any(len(row)!=128 for row in rows):
        raise ValueError('Formatted portrait sheets must be exactly 128 × 32 pixels.')
    output=bytearray(2048)
    for tile in range(64):
        for y in range(8):
            for plane in range(4):
                value=0
                for x in range(8):
                    pixel=rows[(tile//16)*8+y][(tile%16)*8+x]
                    if not 0<=pixel<=15:
                        raise ValueError('Portrait pixels must use a 16-color palette.')
                    value=(value<<1)|((pixel>>plane)&1)
                output[tile*32+(plane//2)*16+y*2+plane%2]=value
    return bytes(output)

def decode_palette(raw):
    if len(raw)!=32:
        raise ValueError('Portrait palette must contain 16 colors.')
    colors=[]
    for i in range(0,32,2):
        value=int.from_bytes(raw[i:i+2],'little')
        colors.append(tuple(((value>>shift)&31)*255//31 for shift in (0,5,10)))
    return colors

def encode_palette(colors):
    if len(colors)!=16:
        raise ValueError('Portrait palette must contain 16 colors.')
    return b''.join(sum((round(component*31/255)&31)<<shift for component,shift in zip(color,(0,5,10))).to_bytes(2,'little') for color in colors)

def png_bytes(rows,colors,scale=1):
    width=len(rows[0])*scale
    height=len(rows)*scale
    pixels=[]
    for row in rows:
        line=b''.join(bytes(colors[value])*scale for value in row)
        pixels.extend([b'\0'+line]*scale)
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+
            chunk(b'IDAT',zlib.compress(b''.join(pixels)))+chunk(b'IEND',b''))

def export_png(rows,colors):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',len(rows[0]),len(rows),8,3,0,0,0))+
            chunk(b'PLTE',b''.join(bytes(color) for color in colors))+chunk(b'tRNS',bytes([0]+[255]*15))+
            chunk(b'IDAT',zlib.compress(b''.join(b'\0'+bytes(row) for row in rows)))+chunk(b'IEND',b''))

def face_from_sheet(sheet,frame=0):
    rows=[row[:48] for row in sheet]+[row[48:96] for row in sheet]
    if frame:
        for y in range(16):
            rows[y+32][:32]=sheet[y+(frame-1)*16][96:128]
    return rows

def sheet_from_face(rows):
    if len(rows)!=64 or any(len(row)!=48 for row in rows):
        raise ValueError('Faces must be exactly 48 × 64 pixels.')
    return [rows[y][:]+rows[y+32][:]+rows[32+(y%16)][:32] for y in range(32)]

def editable_sheet(sheet):
    """64x80 artist layout: face above, both native 32x16 mouth frames below."""
    if len(sheet)!=32 or any(len(row)!=128 for row in sheet):
        raise ValueError('Native portrait sheets must be exactly 128 x 32 pixels.')
    rows=[row+[0]*16 for row in face_from_sheet(sheet)]
    rows.extend(sheet[y][96:128]+sheet[y+16][96:128] for y in range(16))
    return rows


def native_sheet_from_editable(rows):
    """Pack all face/mouth pixels; the unused top-right padding is ignored."""
    if len(rows)!=80 or any(len(row)!=64 for row in rows):
        raise ValueError('Editable portrait sheets must be exactly 64 x 80 pixels.')
    return [rows[y][:48]+rows[y+32][:48]+rows[64+y%16][(y//16)*32:(y//16+1)*32] for y in range(32)]


def studio_sheet(sheet):
    """Studio 64x64: face at left, four animation tile columns at right."""
    face=face_from_sheet(sheet)
    return [face[y]+sheet[y%32][96+(y//32)*16:112+(y//32)*16] for y in range(64)]


def native_sheet_from_studio(rows):
    if len(rows)!=64 or any(len(row)!=64 for row in rows):
        raise ValueError('Studio portrait sheets must be exactly 64 x 64 pixels.')
    return [rows[y][:48]+rows[y+32][:48]+rows[y][48:64]+rows[y+32][48:64] for y in range(32)]


class Portrait:
    def __init__(self,rom,portrait_id):
        if not 0<=portrait_id<COUNT:
            raise ValueError('Portrait ID must be between 0 and 247.')
        self.rom=rom
        self.id=portrait_id
        self.graphics=self.read_pointer(GRAPHICS_TABLE+portrait_id*3)
        self.palette=self.read_pointer(PALETTE_TABLE+portrait_id*3)
        self.address=pc_address(self.graphics)
        self.palette_address=pc_address(self.palette)
        if self.palette_address+32>len(rom.data)-rom.header:
            raise ValueError('Portrait palette is outside the ROM.')
        self.read_addresses=set()
        self.raw,self.compressed_size=decompress(memoryview(rom.data)[rom.header:],self.address,limit=4096,banked=True,read_addresses=self.read_addresses)
        self.sheet=decode_tiles(self.raw)
        self.rows=face_from_sheet(self.sheet)
        self.colors=decode_palette(bytes(rom.data[self.palette_address+rom.header:self.palette_address+rom.header+32]))

    def read_pointer(self,address):
        return int.from_bytes(self.rom.data[address+self.rom.header:address+self.rom.header+3],'little')

    def plan_import(self,sheet,colors):
        raw=encode_tiles(sheet)
        palette=encode_palette(colors)
        normalized=decode_palette(palette)
        if all((old==0)==(new==0) and self.colors[old]==normalized[new]
               for a,b in zip(self.sheet,sheet) for old,new in zip(a,b)):
            return [],'Image already matches the ROM.'
        compressed=compress(raw)
        if decompress(compressed,0)[0]!=raw:
            raise ValueError('Portrait compression verification failed.')
        span={banked_position(self.address,i) for i in range(self.compressed_size)}
        others=[Portrait(self.rom,i) for i in range(COUNT) if i!=self.id]
        in_place=len(compressed)<=self.compressed_size and not any(span.intersection(p.read_addresses) for p in others)
        shared_palette=any(p.palette_address==self.palette_address for p in others)
        palette_changed=palette!=bytes(self.rom.data[self.palette_address+self.rom.header:self.palette_address+self.rom.header+32])
        sizes=[]
        if not in_place:
            sizes.append(len(compressed))
        if shared_palette and palette_changed:
            sizes.append(32)
        allocations,arena_edits=allocate(self.rom,sizes) if sizes else ([],[])
        edits=arena_edits[:]
        if in_place:
            # Preserve the decompressor's 32 KiB half-bank traversal.
            for i,value in enumerate(compressed):
                edits.append((banked_position(self.address,i),bytes([value])))
            description='Reuses the existing graphics allocation.'
        else:
            address=allocations.pop(0)
            edits.extend([(address,compressed),(GRAPHICS_TABLE+self.id*3,pointer_for(address).to_bytes(3,'little'))])
            description='Relocates graphics into the reserved portrait area; ROM size stays unchanged.'
        if palette_changed:
            if shared_palette:
                address=allocations.pop(0)
                edits.extend([(address,palette),(PALETTE_TABLE+self.id*3,pointer_for(address).to_bytes(3,'little'))])
                description+=' Creates a private palette to preserve other portrait IDs.'
            else:
                edits.append((self.palette_address,palette))
        if any(address<0 or address+len(data)>len(self.rom.data)-self.rom.header for address,data in edits):
            raise ValueError('Portrait data is outside the ROM.')
        return edits,description

    def import_sheet(self,sheet,colors):
        edits,description=self.plan_import(sheet,colors)
        before=bytes(self.rom.data)
        try:
            for address,data in edits:
                self.rom.data[address+self.rom.header:address+self.rom.header+len(data)]=data
            updated=Portrait(self.rom,self.id)
            if edits and (updated.raw!=encode_tiles(sheet) or updated.colors!=decode_palette(encode_palette(colors))):
                raise ValueError('Imported portrait verification failed.')
        except ValueError:
            self.rom.data[:]=before
            raise
        return description

def banked_position(start,index):
    chunk=(start&0x7fff)+index
    return (start&~0xffff)+(start&0x8000)+(chunk//0x8000)*0x10000+(chunk%0x8000)

ARENA=0x7c0000
ARENA_SIZE=0x10000
MAGIC=b'FE4BPORTRAITSv1!'

def allocate(rom,sizes):
    if len(rom.data)-rom.header!=0x800000:
        raise ValueError('Relocating portraits currently requires an 8 MiB ExHiROM ROM.')
    block=bytes(rom.data[ARENA+rom.header:ARENA+rom.header+ARENA_SIZE])
    if block.startswith(MAGIC):
        cursor=int.from_bytes(block[16:20],'little')
        fill=block[20]
        if not 32<=cursor<=ARENA_SIZE or fill not in (0,255):
            raise ValueError('The portrait allocator metadata is invalid.')
    else:
        if len(set(block))!=1 or block[0] not in (0,255):
            raise ValueError('The reserved portrait area contains other data; import was cancelled.')
        for table in (GRAPHICS_TABLE,PALETTE_TABLE):
            for i in range(COUNT):
                offset=table+i*3+rom.header
                address=pc_address(int.from_bytes(rom.data[offset:offset+3],'little'))
                if ARENA<=address<ARENA+ARENA_SIZE:
                    raise ValueError('Existing portrait data references the reserved area.')
        cursor,fill=32,block[0]
    addresses=[]
    for size in sizes:
        cursor=(cursor+31)&~31
        if (cursor&0x7fff)+size>0x8000:
            cursor=(cursor+0x7fff)&~0x7fff
        if cursor+size>ARENA_SIZE or any(value!=fill for value in block[cursor:cursor+size]):
            raise ValueError('The reserved portrait area is full or occupied. No ROM data was changed.')
        for table,extent in ((GRAPHICS_TABLE,1),(PALETTE_TABLE,32)):
            for i in range(COUNT):
                offset=table+i*3+rom.header
                address=pc_address(int.from_bytes(rom.data[offset:offset+3],'little'))
                if address<ARENA+cursor+size and address+extent>ARENA+cursor:
                    raise ValueError('A portrait references the proposed allocation; import was cancelled.')
        addresses.append(ARENA+cursor)
        cursor+=size
    header=MAGIC.ljust(16,b'\0')+cursor.to_bytes(4,'little')+bytes([fill])+bytes(11)
    return addresses,[(ARENA,header)]

def character_portrait_id(rom,character_id,class_id=None):
    if not 1<=character_id<=696:
        raise ValueError('Character ID is outside the portrait assignment table.')
    offset=CHARACTER_TABLE+rom.header+(character_id-1)*2
    portrait=int.from_bytes(rom.data[offset:offset+2],'little')
    if portrait==0xf3 and class_id is None:
        raise ValueError('This character uses a class portrait; its class is needed to resolve the image.')
    if portrait==0xf3 and class_id is not None:
        if not 0<=class_id<72:
            raise ValueError('Invalid class portrait index.')
        offset=0xb9ff8+rom.header+class_id*2
        portrait=int.from_bytes(rom.data[offset:offset+2],'little')
    return portrait
