"""Native title-map / captured sprite arrangements with reversible pixel edits."""
import json
from rom import DATA_DIR
from portraits import decode_palette

KEYS=('title_english','title_logo')
PALETTES={1:0x2026e1,2:0x2026ff,3:0x2026c3,10:0x20271d,12:0x202769}

def layout(key,size,rom=None):
    spec=json.loads((DATA_DIR/'logo_layouts.json').read_text(encoding='utf-8'))[key]
    if 'map_refs' in spec:
        if rom is None:raise ValueError('The native logo tilemap needs the current ROM.')
        from intro_graphics import read_stream
        tilemap,_,_=read_stream(rom,spec['map_refs'])
        if len(tilemap)!=2048:raise ValueError('Unsupported English title tilemap size.')
        tiles=[]
        for cell in range(1024):
            value=int.from_bytes(tilemap[cell*2:cell*2+2],'little');pal=value>>10&7
            y=cell//32*8-spec['crop_y'];tile=value&1023
            if pal and -8<y<spec['height']:tiles.append([tile,cell%32*8,y,(value>>14)&3,pal])
        spec['tiles']=tiles
    occupied=set()
    for tile,x,y,flip,pal in spec['tiles']:
        if not 0<=tile<size//32 or flip not in range(4) or pal not in range(16):
            raise ValueError('Invalid native logo tile reference.')
        occupied.update((x+dx,y+dy) for dx in range(8) for dy in range(8) if 0<=x+dx<spec['width'] and 0<=y+dy<spec['height'])
    return spec,occupied

def colors(rom):
    result=[(0,0,0)]*256
    for pal,address in PALETTES.items():
        a=address+rom.header
        result[pal*16:pal*16+16]=decode_palette(bytes(2)+bytes(rom.data[a:a+30]))
    a=0x202759+rom.header
    result[64:74]=decode_palette(bytes(2)+bytes(rom.data[a:a+18])+bytes(12))[:10]
    return result

def projection(raw,key,rom):
    from intro_graphics import decode_tiles
    spec,occupied=layout(key,len(raw),rom);sheet=decode_tiles(raw)
    rows=[[0]*spec['width'] for _ in range(spec['height'])];owners={};layers={}
    for tile,x,y,flip,pal in spec['tiles']:
        for dy in range(8):
            for dx in range(8):
                sx=x+(7-dx if flip&1 else dx);sy=y+(7-dy if flip&2 else dy)
                if not (0<=sx<spec['width'] and 0<=sy<spec['height']):continue
                value=sheet[tile//16*8+dy][tile%16*8+dx];owner=(tile,dx,dy,pal)
                layers.setdefault((sx,sy),[]).append(owner)
                if value or rows[sy][sx]==0:owners[sx,sy]=owner
                if value:rows[sy][sx]=pal*16+value
    return rows,owners,layers,occupied

def render(raw,key,palette,rom):return projection(raw,key,rom)[0],palette

def import_pixels(raw,key,palette,pixels,image,indexed,rom):
    from intro_graphics import decode_tiles,encode_sheet
    previous,owners,layers,occupied=projection(raw,key,rom);writes={}
    def assign(owner,value):
        tile,dx,dy,pal=owner;at=(tile,dx,dy)
        if at in writes and writes[at]!=value:
            raise ValueError('Two edited copies of a shared logo pixel disagree. Edit one copy or use matching edits; its other copies update automatically.')
        writes[at]=value
    for y,line in enumerate(pixels):
        for x,rgb in enumerate(line):
            old=previous[y][x];transparent=image.transparency_get(x,y)
            if indexed is not None:transparent=transparent or indexed[y][x]==0
            elif rgb==(0,0,0) and old==0:transparent=True
            if rgb==palette[old] and transparent==(old==0):continue
            if (x,y) not in occupied:
                if transparent:continue
                raise ValueError('Paint inside the logo artwork area. This gap has no native tile; use Raw tiles for auxiliary graphics.')
            owner=owners[x,y];pal=owner[3]
            if transparent:
                for source in layers[x,y]:assign(source,0)
                continue
            value=indexed[y][x] if indexed is not None else None
            if value is not None and value//16==pal:value%=16
            else:
                choices=palette[pal*16:pal*16+16];choices[0]=(0,0,0)
                value=min(range(16),key=lambda i:sum((a-b)**2 for a,b in zip(rgb,choices[i])))
            assign(owner,value)
    sheet=decode_tiles(raw)
    for (tile,x,y),value in writes.items():sheet[tile//16*8+y][tile%16*8+x]=value
    return encode_sheet(sheet,len(raw))
