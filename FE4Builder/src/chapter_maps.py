"""Chapter rendering and staged terrain, camera-bound and deployment edits."""
from fe4_codec import decompress
from portraits import pc_address,decode_palette,png_bytes
from rom import army_modules

MAP_HEADERS=0x89fc3

TERRAIN_NAMES=['Peak','Thicket','Cliff','Plains','Forest','Sea','River','Mountain','Desert','Castle',
               'Fort','House','Castle gate','Rampart','Sand','Bridge','Swamp','Castle gate',
               'Village','Village ruins','Store','Ruins','Church','Shrine','Bragi tower','Road']
TERRAIN_COLORS=[(101,104,102),(50,105,58),(137,129,112),(153,187,109),(65,129,73),(64,123,175),
                (91,155,197),(137,143,119),(209,187,121),(184,158,122),(174,157,132),(195,154,112),
                (167,146,116),(147,140,127),(218,199,146),(177,139,88),(98,144,132),(167,146,116),
                (213,166,104),(136,123,102),(197,160,112),(136,123,102),(218,210,182),(184,191,215),
                (181,170,219),(194,173,135)]+[(113,117,123)]*230

def words(data):
    return [int.from_bytes(data[i:i+2],'little') for i in range(0,len(data),2)]

class ChapterMap:
    def __init__(self,rom,chapter):
        if not 0<=chapter<12:
            raise ValueError('Select a chapter between Prologue and Final Chapter.')
        self.rom,self.chapter=rom,chapter
        data=memoryview(rom.data)[rom.header:]
        offset=MAP_HEADERS+chapter*3
        pointer=int.from_bytes(data[offset:offset+3],'little')
        self.header=pc_address(pointer)
        header=bytes(data[self.header:self.header+27])
        if len(header)!=27 or int.from_bytes(header[12:14],'little')!=4:
            raise ValueError('Unsupported chapter map header or width.')
        pointers=[pc_address(int.from_bytes(header[i:i+3],'little')) for i in (0,3,6,9,24)]
        raw,_=decompress(data,pointers[0],limit=8192,banked=True)
        definitions,_=decompress(data,pointers[1],limit=2048,banked=True)
        graphics,_=decompress(data,pointers[2],limit=4096,banked=True)
        terrain,_=decompress(data,pointers[4],limit=1024,banked=True)
        if (len(raw),len(definitions),len(graphics),len(terrain))!=(8192,2048,4096,1024):
            raise ValueError('Chapter data does not match the supported FE4 map layout.')
        self.map=words(raw)
        self.original_map=self.map[:]
        self.definitions=words(definitions)
        self.graphics=bytes(data[0x190000:0x195000])+graphics
        self.dictionary=words(data[0x195000:0x196800])
        self.terrain=terrain
        self.palette=decode_palette(bytes(data[0xc9d00:0xc9d20]))
        for i in range(7):
            start=pointers[3]+i*32
            self.palette.extend(decode_palette(bytes(data[start:start+32])))
        self.bounds=tuple(int.from_bytes(header[i:i+2],'little')//16 for i in (16,18,20,22))
        self.original_bounds=self.bounds
        self.original_bounds_data=header[16:24]
        self.width=self.height=64
        self.units=army_modules(rom)[chapter]
        self.original_positions=[tuple(rom.values(self.units,i)[1:3]) for i in range(self.units.count)]
        self.positions=self.original_positions[:]

    def tiles(self):
        """The 1,024 assembled 16x16 tiles in map-ID order."""
        tiles=[]
        # 256 chapter-specific metatiles followed by 768 shared metatiles.
        # Each metatile contains TL, BL, TR, BR SNES tile descriptors.
        definitions=self.definitions+self.dictionary
        if len(definitions)!=4096:
            raise ValueError('Unsupported chapter metatile dictionary.')
        for index in range(1024):
            parts=definitions[index*4:index*4+4]
            tile=[[0]*16 for _ in range(16)]
            for part,descriptor in enumerate(parts):
                number=descriptor&1023
                if (number+1)*32>len(self.graphics):
                    raise ValueError('Map graphics reference is outside the supported tileset.')
                palette=(descriptor>>10)&7
                flip_x=bool(descriptor&0x4000)
                flip_y=bool(descriptor&0x8000)
                for y in range(8):
                    source_y=7-y if flip_y else y
                    planes=[self.graphics[number*32+source_y*2],self.graphics[number*32+source_y*2+1],
                            self.graphics[number*32+16+source_y*2],self.graphics[number*32+17+source_y*2]]
                    for x in range(8):
                        bit=x if flip_x else 7-x
                        pixel=sum(((plane>>bit)&1)<<i for i,plane in enumerate(planes))
                        tile[(part%2)*8+y][(part//2)*8+x]=palette*16+pixel
            tiles.append(tile)
        return tiles

    def pixels(self):
        tiles=self.tiles()
        rows=[]
        for map_y in range(64):
            for y in range(16):
                row=[]
                for map_x in range(64):
                    row.extend(tiles[self.map[map_y*64+map_x]&1023][y])
                rows.append(row)
        return rows

    def png(self,terrain=False):
        if not terrain:
            return png_bytes(self.pixels(),self.palette)
        rows=[]
        for y in range(64):
            row=[]
            for x in range(64):
                terrain,_=self.tile_info(x,y)
                row.extend([terrain]*16)
            rows.extend([row]*16)
        return png_bytes(rows,TERRAIN_COLORS)

    def move(self,index,x,y):
        if not 0<=index<self.units.count or not (0<=x<64 and 0<=y<64):
            raise ValueError('Deployment coordinates must be within the 64 × 64 map.')
        self.positions[index]=(x,y)

    def paint(self,x,y,tile):
        if not (0<=x<64 and 0<=y<64 and 0<=tile<1024):
            raise ValueError('Map cells and tile IDs must be within the chapter tileset.')
        index=y*64+x
        # Keep the cell's separate event/blocking bits; terrain comes from tile ID.
        self.map[index]=(self.map[index]&0xfc00)|tile

    @property
    def dirty(self):
        return self.positions!=self.original_positions or self.map!=self.original_map or self.bounds!=self.original_bounds

    @staticmethod
    def resize_bounds(width,height,x=0,y=0):
        if not all(type(value) is int for value in (width,height,x,y)):
            raise ValueError('Enter whole tile counts for size and origin.')
        # The native loader subtracts a 256x224-pixel viewport from the right
        # and bottom edges (CPU 8892D4/8892DF). Smaller regions invert scrolling.
        if not (16<=width<=64 and 14<=height<=64 and 0<=x<=64-width and 0<=y<=64-height):
            raise ValueError('Use width 16–64 and height 14–64, with the entire area inside the 64×64 map.')
        return (x,y,x+width,y+height)

    def resize(self,width,height,x=0,y=0):
        self.bounds=self.resize_bounds(width,height,x,y)

    def outside_deployments(self,bounds=None):
        left,top,right,bottom=bounds or self.bounds
        return [i for i,(x,y) in enumerate(self.positions) if not (left<=x<right and top<=y<bottom)]

    def tile_info(self,x,y):
        tile=self.map[y*64+x]
        return self.terrain[tile&1023],tile>>10

    def write(self):
        details=[]
        # Ensure staged edits still refer to the same deployment records.
        current=army_modules(self.rom)[self.chapter]
        if current.addresses!=self.units.addresses:
            raise ValueError('Army pointers changed; reload the map before writing.')
        for index,(old,new) in enumerate(zip(self.original_positions,self.positions)):
            if old==new:
                continue
            if len(new)!=2 or not all(isinstance(value,int) and 0<=value<64 for value in new):
                raise ValueError('Deployment coordinates must be within the 64 × 64 map.')
            values=self.rom.values(current,index)
            if tuple(values[1:3])!=old:
                raise ValueError('A deployment changed outside the map editor. Reload before writing.')
            details.append((index,old,new))
        edits=[]
        if self.bounds!=self.original_bounds:
            left,top,right,bottom=self.bounds
            self.resize_bounds(right-left,bottom-top,left,top)
            # Header relocation or another window's resize must not overwrite
            # newer bounds. Also reject headers shared by another chapter.
            data=memoryview(self.rom.data)[self.rom.header:]
            headers=[pc_address(int.from_bytes(data[MAP_HEADERS+i*3:MAP_HEADERS+i*3+3],'little')) for i in range(12)]
            if headers[self.chapter]!=self.header or bytes(data[self.header+16:self.header+24])!=self.original_bounds_data:
                raise ValueError('Map bounds changed outside this window. Reload before writing.')
            if headers.count(self.header)>1:
                raise ValueError('This map header is shared by multiple chapters; resizing it requires a private header.')
            edits.append((self.header+16,b''.join((value*16).to_bytes(2,'little') for value in self.bounds)))
        changed=[i for i,(a,b) in enumerate(zip(self.original_map,self.map)) if a!=b]
        if changed:
            from map_layout import plan_layout
            edits.extend(plan_layout(self))
        for address,payload in edits:
            self.rom.data[address+self.rom.header:address+self.rom.header+len(payload)]=payload
        for index,old,new in details:
            address=self.rom.address(current,index)
            self.rom.data[address+2:address+4]=bytes(new)
        descriptions=[f'{current.names[index]}: ({old[0]}, {old[1]}) → ({new[0]}, {new[1]})' for index,old,new in details]
        descriptions.extend(f'Tile ({i%64}, {i//64}): {self.original_map[i]&1023:03X} to {self.map[i]&1023:03X}' for i in changed)
        if self.bounds!=self.original_bounds:
            descriptions.append(f'Chapter camera bounds: {self.original_bounds} → {self.bounds}; terrain and event coordinates retained')
        return descriptions
