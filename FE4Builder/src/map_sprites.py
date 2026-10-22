"""Resolve unit class/gender/character overrides and decode a native map frame."""
from fe4_codec import decompress
from portraits import pc_address,decode_palette

def compose_frame(raw,template,tall):
    """Mirror the native OAM templates at $88CC49 (tall) / $88CC5F (short).

    DMA uploads two rows of five or eight tiles. The short template combines
    two 16x16 and two 8x8 pieces; it is not a contiguous 16x16 bitmap.
    """
    columns=8 if tall else 5
    if len(raw)<columns*2*32:
        raise ValueError('Map sprite frame is incomplete.')
    count=int.from_bytes(template[:2],'little')
    if count!=4 or len(template)!=2+count*5:
        raise ValueError('Unsupported map sprite object template.')
    objects=[]
    for i in range(count):
        offset=2+i*5
        flags=int.from_bytes(template[offset:offset+2],'little')
        x=flags&511
        x=x-512 if x>=256 else x
        y=template[offset+2]
        y=y-256 if y>=128 else y
        size=16 if flags&0x4000 else 8
        objects.append((x,y,size,template[offset+3],template[offset+4]))
    min_x=min(o[0] for o in objects)
    min_y=min(o[1] for o in objects)
    width=max(o[0]+o[2] for o in objects)-min_x
    height=max(o[1]+o[2] for o in objects)-min_y
    if width>64 or height>64:
        raise ValueError('Unsupported map sprite bounds.')
    rows=[[0]*width for _ in range(height)]
    # Earlier OAM entries have priority over later entries.
    for ox,oy,size,tile,attributes in reversed(objects):
        for y in range(size):
            sy=size-1-y if attributes&0x80 else y
            for x in range(size):
                sx=size-1-x if attributes&0x40 else x
                column=(tile&15)+sx//8
                row=(tile>>4)-2+sy//8
                if not 0<=column<columns or not 0<=row<2:
                    raise ValueError('Map sprite object references an unavailable tile.')
                source=(row*columns+column)*32+(sy%8)*2
                planes=[raw[source],raw[source+1],raw[source+16],raw[source+17]]
                value=sum(((plane>>(7-sx%8))&1)<<i for i,plane in enumerate(planes))
                if value:
                    rows[oy-min_y+y][ox-min_x+x]=value
    return rows

class MapSprites:
    def __init__(self,rom):
        self.rom=rom
        self.data=memoryview(rom.data)[rom.header:]
        self.cache={}
        self.assignments={}

    def word(self,address):
        if not 0<=address<=len(self.data)-2:
            raise ValueError('Map sprite reference is outside the ROM.')
        return int.from_bytes(self.data[address:address+2],'little')

    def character(self,character_id):
        if not 1<=character_id<=696:
            raise ValueError('Character is outside the FE4 character table.')
        base=0x3adf5
        address=base+self.word(base+(character_id-1)*2)
        kind=self.data[address]
        offsets={0:(9,18),1:(1,8),2:(9,18),3:(5,6)}
        if kind not in offsets:
            raise ValueError('Unsupported character record type.')
        class_offset,gender_offset=offsets[kind]
        class_id,gender=self.data[address+class_offset],self.data[address+gender_offset]
        if not 0<=class_id<72:
            raise ValueError('Unsupported character class.')
        return class_id,gender

    def assignment(self,character_id):
        if character_id in self.assignments:
            return self.assignments[character_id]
        class_id,gender=self.character(character_id)
        base=0x3805e
        start=base+self.word(base+class_id*2)
        starts=[base+self.word(base+i*2) for i in range(72)]
        end=min([value for value in starts if value>start]+[0x3833c])
        for address in range(start,end,5):
            specific=self.word(address)
            required=self.data[address+2]
            if specific in (0,character_id) and required in (255,gender):
                result=self.word(address+3),class_id,gender
                self.assignments[character_id]=result
                return result
        raise ValueError('No matching class map-sprite assignment.')

    def variants(self,class_id):
        """Class assignment entries, including gender and character overrides."""
        if not 0<=class_id<72:
            raise ValueError('Unsupported character class.')
        base=0x3805e
        start=base+self.word(base+class_id*2)
        starts=[base+self.word(base+i*2) for i in range(72)]
        end=min([value for value in starts if value>start]+[0x3833c])
        return [(self.word(a),self.data[a+2],self.word(a+3)) for a in range(start,end,5)]

    def frames(self,assignment,standing=True,palette=0):
        if not 0<=palette<=6:
            raise ValueError('Invalid unit sprite palette.')
        tall=bool(assignment&0x8000)
        index=assignment&0x7fff
        if not 0<=index<(32 if tall else 65):
            raise ValueError('Unsupported map sprite index.')
        key=(assignment,palette,standing)
        if key not in self.cache:
            table=(0x8d5e3 if tall else 0x8d526) if standing else (0x8d428 if tall else 0x8d365)
            offset=table+index*3
            pointer=int.from_bytes(self.data[offset:offset+3],'little')
            address=pc_address(pointer)
            frames=[]
            if standing:
                # Standing graphics are uncompressed, three frames, two tiles wide.
                stride=192 if tall else 128
                if address+stride*3>len(self.data):
                    raise ValueError('Standing sprite data is outside the ROM.')
                for frame in range(3):
                    raw=self.data[address+frame*stride:address+(frame+1)*stride]
                    rows=[[0]*16 for _ in range(24 if tall else 16)]
                    for tile in range(stride//32):
                        for y in range(8):
                            for x in range(8):
                                source=tile*32+y*2
                                rows[tile//2*8+y][tile%2*8+x]=sum(((raw[source+(16 if p>=2 else 0)+p%2]>>(7-x))&1)<<p for p in range(4))
                    # Mounted OAM places the last tile pair above the main 16x16 body.
                    if tall:
                        rows=rows[16:]+rows[:16]
                    frames.append(rows)
            else:
                raw,_=decompress(self.data,address,limit=16384,banked=True)
                stride=512 if tall else 320
                template_address=0x8cc49 if tall else 0x8cc5f
                template=bytes(self.data[template_address:template_address+22])
                if len(raw)<stride*16:
                    raise ValueError('Walking sprite sheet is incomplete.')
                frames=[compose_frame(raw[i*stride:(i+1)*stride],template,tall) for i in range(16)]
            start=0xc9520+palette*32
            colors=decode_palette(bytes(self.data[start:start+32]))
            self.cache[key]=(frames,colors)
        return self.cache[key]

    def sprite(self,character_id,palette=0):
        assignment,_,_=self.assignment(character_id)
        frames,colors=self.frames(assignment,True,palette)
        return frames[0],colors,assignment
