"""Native held-weapon previews and explicit type-symbol fallbacks."""
from rom import MODULES,load_module,category_modules
from linked_editors import field_target
from portraits import pc_address,decode_palette
from fe4_codec import decompress

ITEM_COUNT=0x8a
ASSIGNMENTS=0x198725
GRAPHICS=0x19881f
PALETTES=0x200f30
INVENTORY_LOOKUP=0x00d1ae
INVENTORY_GRAPHICS=0x184000
INVENTORY_PALETTE=0x1e0160
TYPE_NAMES=['Sword','Lance','Axe','Bow','Staff','Fire','Thunder','Wind','Light','Dark']

def decode_object(raw,block):
    """Native 16x16 OBJ tile layout: sixteen 8x8 tiles per VRAM row."""
    rows=[[0]*16 for _ in range(16)]
    for y in range(16):
        for x in range(16):
            tile=block*2+x//8+(y//8)*16
            offset=tile*32+y%8*2
            rows[y][x]=sum(((raw[offset+(16 if p>=2 else 0)+p%2]>>(7-x%8))&1)<<p for p in range(4))
    return rows

def held_pose(raw,staff=False):
    if len(raw)!=1024:raise ValueError('Unsupported held-weapon graphics size.')
    if staff:
        # Upright staff head and shaft occupy separate OBJ slots.
        return decode_object(raw,4)+decode_object(raw,0)
    a,b=decode_object(raw,0),decode_object(raw,1)
    return [left+right for left,right in zip(a,b)]

class ItemArt:
    def __init__(self,rom):
        self.rom=rom
        self.modules={m.name:m for m in category_modules('Item Editor')}
        self.player=load_module(MODULES/'Item Editors'/'FE4 Player Weapon Editor.nmm')
        self.cache={}
        self.icon_cache={}

    @property
    def data(self):
        # Do not keep a buffer export alive: history/name edits can resize ROMs.
        return memoryview(self.rom.data)[self.rom.header:]

    def resolve(self,field,value):
        if value==255:return None
        if field.reference=='FE4 Player Equipment.txt':
            if not 1<=value<=142:raise ValueError('Unsupported inventory slot.')
            value=self.rom.data[self.rom.address(self.player,0)+value-1]
        if value==255:return None
        if not 0<=value<ITEM_COUNT:raise ValueError('Unsupported item ID.')
        return value

    def record(self,item):
        target=field_target(self.rom,self.player.fields[0],item)
        if target is None:return None
        return self.modules[target[1]],target[2]

    def stats(self,item):
        module,index=self.record(item)
        return dict(zip((f.name for f in module.fields),self.rom.values(module,index)))

    def name(self,item,stats=None):
        stats=self.stats(item) if stats is None else stats
        module,_=self.record(item)
        name=next(f for f in module.fields if f.name=='Name')
        return name.options.get(stats.get('Name'),self.player.fields[0].options.get(item,f'Item {item:02X}')).replace('El Wind','Elwind')

    def kind(self,item,stats=None):
        stats=self.stats(item) if stats is None else stats
        if stats.get('Type')==2:return 'Ring'
        if stats.get('Type')==1:return 'Staff'
        value=stats.get('Weapon Type',255)
        return TYPE_NAMES[value] if 0<=value<len(TYPE_NAMES) else 'Weapon'

    def art(self,item,overrides=None):
        if not 0<=item<ITEM_COUNT:raise ValueError('Unsupported item ID.')
        kind=self.kind(item)
        if item>=125:
            rows,colors=self.icon(item)
            return rows,colors,'Native inventory icon (no held-weapon artwork)'
        sprite,palette=self.data[ASSIGNMENTS+item*2:ASSIGNMENTS+item*2+2]
        if overrides is not None:sprite,palette=overrides
        if sprite==255:
            rows,colors=self.icon(item)
            return rows,colors,'Native inventory icon (no held-weapon artwork)'
        if not 0<=sprite<65 or not 0<=palette<36:
            raise ValueError('Unsupported weapon sprite or palette reference.')
        key=(sprite,palette,kind=='Staff')
        if key not in self.cache:
            pointer=int.from_bytes(self.data[GRAPHICS+sprite*3:GRAPHICS+sprite*3+3],'little')
            raw,_=decompress(self.data,pc_address(pointer),limit=4096,banked=True)
            rows=held_pose(raw,kind=='Staff')
            start=PALETTES+palette*30
            colors=decode_palette(bytes(2)+bytes(self.data[start:start+30]))
            self.cache[key]=(rows,colors)
        rows,colors=self.cache[key]
        return rows,colors,'Native held-weapon preview'

    def icon(self,item):
        """The real 16x16 inventory icon, including tomes, rings and broken items."""
        if not 0<=item<ITEM_COUNT:raise ValueError('Unsupported item ID.')
        # The game maps item IDs to top-left tile numbers; several items share
        # one icon. SNES 8x8 tile rows have a sixteen-tile stride.
        data=self.data
        lookup=bytes(data[INVENTORY_LOOKUP+item*2:INVENTORY_LOOKUP+item*2+2])
        if len(lookup)!=2:raise ValueError('Inventory icon lookup is outside the ROM.')
        tile=int.from_bytes(lookup,'little')
        if tile>0x1ee or tile%16>14:
            raise ValueError('Unsupported inventory icon tile reference.')
        start=INVENTORY_GRAPHICS+tile*32
        raw=bytes(data[start:start+64])+bytes(data[start+0x200:start+0x240])
        palette=bytes(data[INVENTORY_PALETTE:INVENTORY_PALETTE+32])
        if len(raw)!=128 or len(palette)!=32:raise ValueError('Inventory icon data is outside the ROM.')
        key=(tile,raw,palette)
        if key not in self.icon_cache:
            rows=[[0]*16 for _ in range(16)]
            for y in range(16):
                for x in range(16):
                    source=(y//8*2+x//8)*32+y%8*2
                    rows[y][x]=sum(((raw[source+(16 if p>=2 else 0)+p%2]>>(7-x%8))&1)<<p for p in range(4))
            # Native inventory rips use 5-bit channel values shifted left by 3.
            colors=[tuple(((int.from_bytes(palette[i:i+2],'little')>>shift)&31)<<3 for shift in (0,5,10)) for i in range(0,32,2)]
            self.icon_cache[key]=(rows,colors)
        return self.icon_cache[key]

    def summary(self,item,stats=None):
        stats=self.stats(item) if stats is None else stats
        fields=[f'{self.kind(item,stats)} | Item {item:02X}']
        if 'Rank' in stats:fields.append('Rank '+{0:'A',1:'B',2:'C',255:'S / Holy'}.get(stats['Rank'],str(stats['Rank'])))
        for name,label in (('Power','Might'),('Accuracy','Hit'),('Weight','Weight'),('Max Uses','Uses'),('Price','Price')):
            if name in stats:fields.append(f'{label} {stats[name]}')
        if 'Minimum Range' in stats:fields.append(f'Range {stats["Minimum Range"]}-{stats["Maximum Range"]}')
        return ' | '.join(fields)

def item_for_record(module,index):
    bases={'FE4 Weapon/Staff Editor 1':0,'FE4 Weapon/Staff Editor 2':0x7a,'FE4 Ring Editor':0x6a,'FE4 Item Editor by Camus':0x6a,'FE4 Circlet Editor':0x89,'FE4 Item Sprite Editor by Lorena':0}
    if module.name not in bases:return None
    item=bases[module.name]+index
    return item if 0<=item<ITEM_COUNT else None
