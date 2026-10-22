"""In-place name editing for Project Naga beta v7's 63 playable name IDs.

Layout verified against Miacidae/Project-Naga-beta-v7 build definitions and
the supplied ROM. Menu names are graphics, not ASCII strings.
"""

ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,?!\'-"·:;()0123456789$%&*+/'
ENCODE = {character: 0x10 + i for i, character in enumerate(ALPHABET)}
DECODE = {value: key for key, value in ENCODE.items()}

class NameNeedsSpace(ValueError):
    pass

def tile_bytes(rows, tile_x, tile_y):
    output = bytearray()
    for y in range(tile_y*8, tile_y*8+8):
        low = high = 0
        for x in range(tile_x*8, tile_x*8+8):
            pixel = rows[y][x] if x < len(rows[y]) else 0
            low = (low << 1) | (pixel & 1)
            high = (high << 1) | ((pixel >> 1) & 1)
        output.extend((low, high))
    return bytes(output)

def packed_graphics(rows, tiles, right=False):
    width = tiles*8
    shift = width-len(rows[0]) if right else 0
    canvas = [[0]*width for _ in range(16)]
    for y, row in enumerate(rows):
        canvas[y][shift:shift+len(row)] = row
    data = b''.join(tile_bytes(canvas, x, y) for y in range(2) for x in range(tiles))
    return data.ljust(256, b'\0')

class NameEditor:
    def __init__(self, rom, name_id):
        self.rom, self.name_id = rom, name_id
        if not 0 <= name_id < 63 or len(rom.data)-rom.header != 0x800000:
            raise ValueError('Name editing currently supports the 63 playable names in Project Naga beta v7.')
        self.base = 0x500000+name_id*16
        self.question = 0x508110+name_id*16
        self.graphics = self.read_pointer(self.base+1)
        self.question_graphics = self.read_pointer(self.question+1)
        self.tiles = self.byte(self.base)
        self.question_tiles = self.byte(self.question)
        graphics_id = 4 if name_id == 33 else name_id
        if (self.graphics != 0x520000+graphics_id*512 or
                self.question_graphics != 0x548000+name_id*256 or
                not 1 <= self.tiles <= 8 or not 1 <= self.question_tiles <= 8):
            raise ValueError('This ROM does not match the supported Project Naga name layout.')
        self.menu_base = 0x45d000 if name_id < 24 else 0x45e000
        self.menu_tiles = []
        table = self.read(0x50a000+name_id*16, 16)
        for i in range(0,16,2):
            tile = int.from_bytes(table[i:i+2], 'big')
            if tile:
                if not 0x240 <= tile < 0x400:
                    raise ValueError('Unsupported character-menu tile layout.')
                self.menu_tiles.append(tile-0x240)
        if not self.menu_tiles or len(self.menu_tiles) != self.tiles:
            raise ValueError('The character menu and name widths differ; this layout needs a separate profile.')
        raw = self.read(self.base+8,8).rstrip(b'\0')
        if not raw or any(value not in DECODE for value in raw):
            raise ValueError('The existing name uses an unsupported encoding.')
        self.current = ''.join(DECODE[value] for value in raw)
        self.shared_ids = [4,33] if name_id in (4,33) else [name_id]
        dialogue = self.read(0x505c00+name_id*16,16)
        if dialogue[0] != 9 or 1 not in dialogue:
            raise ValueError('The castle-dialogue name layout is not recognized.')

    def read(self, address, length):
        return bytes(self.rom.data[address+self.rom.header:address+self.rom.header+length])

    def byte(self, address):
        return self.rom.data[address+self.rom.header]

    def read_pointer(self, address):
        return int.from_bytes(self.read(address,3),'little')

    def render(self, text):
        if not text or len(text) > 8:
            raise ValueError('Enter a name of 1–8 characters; the stored name has eight bytes available.')
        if any(character not in ENCODE for character in text):
            raise ValueError('Use English letters, digits, or supported punctuation. Spaces and accents are not supported yet.')
        glyphs = []
        advances = []
        for character in text:
            code = ENCODE[character]
            index = code-0x10
            advance = self.byte(0x119971+index)
            if not 1 <= advance <= 8:
                raise ValueError('The ROM font width table does not match this profile.')
            tile = (index//8)*32+(index%8)*2
            glyph = []
            for y in range(16):
                row = []
                for x in range(16):
                    offset = 0x128000+(tile+(y//8)*16+x//8)*16+(y%8)*2
                    low, high = self.read(offset,2)
                    row.append(((low>>(7-x%8))&1)+2*((high>>(7-x%8))&1))
                glyph.append(row)
            glyphs.append(glyph)
            advances.append(advance)
        width = sum(advances)+1
        rows = [[0]*width for _ in range(16)]
        cursor = 0
        for glyph, advance in zip(glyphs, advances):
            for y in range(16):
                for x in range(min(advance+1,width-cursor)):
                    pixel = glyph[y][x]
                    # Font borders overlap; colored strokes take precedence.
                    if pixel and (rows[y][cursor+x] == 0 or pixel == 2):
                        rows[y][cursor+x] = pixel
            cursor += advance
        return rows

    def plan(self, text, include_shared=True, allow_expand=False):
        rows = self.render(text)
        question_rows = self.render(text+'?') if len(text)<8 else self.render_question(text)
        tiles = max(self.tiles,(len(rows[0])+7)//8)
        question_tiles = max(self.question_tiles,(len(question_rows[0])+7)//8)
        if tiles>8 or question_tiles>8:
            raise ValueError('This name exceeds the game’s eight-tile graphics limit (64 pixels).')
        expanding = tiles>self.tiles or question_tiles>self.question_tiles
        if expanding and not allow_expand:
            raise NameNeedsSpace(f'This name needs {len(rows[0])} pixels; the current allocation has {self.tiles*8}. More name space is required.')
        encoded = bytes(ENCODE[character] for character in text)
        edits = [(self.base+8, encoded.ljust(8,b'\0')),
                 (self.question+7, encoded.ljust(9,b'\0')),
                 (0x505c00+self.name_id*16, (b'\x09'+encoded+b'\x01').ljust(16,b'\0')),
                 (self.graphics, packed_graphics(rows,tiles)),
                 (self.graphics+256, packed_graphics(rows,tiles,right=True)),
                 (self.question_graphics, packed_graphics(question_rows,question_tiles))]
        if expanding:
            edits.extend([(self.base,bytes([tiles])),(self.question,bytes([question_tiles]))])
        if tiles!=self.tiles:
            edits.extend(self.repack_menu(rows,tiles))
        else:
            for column, tile in enumerate(self.menu_tiles):
                for y in range(2):
                    edits.append((self.menu_base+(tile+y*16)*16, tile_bytes(rows,column,y)))
        if include_shared:
            for name_id in self.shared_ids:
                if name_id != self.name_id:
                    _, shared_edits = NameEditor(self.rom,name_id).plan(text,include_shared=False,allow_expand=allow_expand)
                    edits.extend(shared_edits)
        # Validate every slice before the first mutation.
        for offset, data in edits:
            if offset < 0 or offset+len(data) > len(self.rom.data)-self.rom.header:
                raise ValueError('Name data is outside the ROM.')
        return rows, edits

    def repack_menu(self, rows, tiles):
        """Repack one generation's documented name-only 2bpp allocation."""
        ids = range(24) if self.name_id<24 else range(24,63)
        capacity = 256 if self.name_id<24 else 448
        bank = bytearray(self.read(self.menu_base,0x1000 if self.name_id<24 else 0x2000))
        source = bytes(bank)
        cursor=0
        edits=[]
        for name_id in ids:
            entry=NameEditor(self.rom,name_id)
            changed=name_id in self.shared_ids
            width=tiles if changed else entry.tiles
            if cursor%32+width>16:
                cursor=((cursor//32)+1)*32
            if cursor+16+width>capacity:
                raise ValueError('The generation menu has no more safely addressable name tiles. No ROM bytes were changed.')
            tilemap=bytearray(16)
            for column in range(width):
                target=cursor+column
                tilemap[column*2:column*2+2]=(0x240+target).to_bytes(2,'big')
                for y in range(2):
                    offset=(target+y*16)*16
                    if changed:
                        data=tile_bytes(rows,column,y)
                    else:
                        old=(entry.menu_tiles[column]+y*16)*16
                        data=source[old:old+16]
                    bank[offset:offset+16]=data
            edits.append((0x50a000+name_id*16,bytes(tilemap)))
            cursor+=width
        return edits+[(self.menu_base,bytes(bank))]

    def render_question(self, text):
        # A question mark is graphics only; it does not consume a stored-name byte.
        first = self.render(text)
        mark = self.render('?')
        return [a[:-1]+b for a,b in zip(first,mark)]

    def write(self, text, allow_expand=False):
        rows, edits = self.plan(text,allow_expand=allow_expand)
        for offset,data in edits:
            self.rom.data[offset+self.rom.header:offset+self.rom.header+len(data)] = data
        return rows
