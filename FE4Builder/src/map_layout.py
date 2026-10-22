"""Private compressed chapter layouts in verified empty ExHiROM space."""
from fe4_codec import compress,decompress
from portraits import pc_address,pointer_for

ARENA=0x7a0000
ARENA_SIZE=0x20000
MAGIC=b'FE4BMAPLAYOUTv1!'
SLOT_SIZE=0x2400

def slot(chapter):
    # Three slots per 32 KiB half-bank; streams never cross a half-bank.
    return ARENA+(chapter//3)*0x8000+0x100+(chapter%3)*SLOT_SIZE

def plan_layout(model):
    rom=model.rom
    data=memoryview(rom.data)[rom.header:]
    pointer=pc_address(int.from_bytes(data[model.header:model.header+3],'little'))
    raw,_=decompress(data,pointer,limit=8192,banked=True)
    if raw!=b''.join(value.to_bytes(2,'little') for value in model.original_map):
        raise ValueError('The map layout changed outside this window. Reload before writing.')
    raw=b''.join(value.to_bytes(2,'little') for value in model.map)
    packed=compress(raw)
    if decompress(packed,0,limit=8192)[0]!=raw or len(packed)>SLOT_SIZE:
        raise ValueError('Map compression verification failed.')
    if len(data)!=0x800000:
        raise ValueError('Saving map tiles currently requires an 8 MiB ExHiROM ROM.')
    block=bytes(data[ARENA:ARENA+ARENA_SIZE])
    if block.startswith(MAGIC.ljust(16,b'\0')):
        fill=block[16]
        if fill not in (0,255) or block[17:32]!=bytes(15):
            raise ValueError('Map storage metadata is invalid. No map data was written.')
    else:
        if len(set(block))!=1 or block[0] not in (0,255):
            raise ValueError('The reserved map area contains other data. No map data was written.')
        fill=block[0]
    address=slot(model.chapter)
    own=pointer==address
    if not own and any(v!=fill for v in data[address:address+SLOT_SIZE]):
        raise ValueError('This chapter map storage is occupied. No map data was written.')
    # Inspect compressed reads, including compressed-stream lookbacks, for every
    # chapter resource so a shared or dependent stream cannot be overwritten.
    from chapter_maps import MAP_HEADERS
    for chapter in range(12):
        h=pc_address(int.from_bytes(data[MAP_HEADERS+chapter*3:MAP_HEADERS+chapter*3+3],'little'))
        for offset,limit in ((0,8192),(3,2048),(6,4096),(24,1024)):
            start=pc_address(int.from_bytes(data[h+offset:h+offset+3],'little'))
            if chapter==model.chapter and offset==0 and own:
                continue
            reads=set()
            decompress(data,start,limit=limit,banked=True,read_addresses=reads)
            if any(address<=p<address+SLOT_SIZE for p in reads):
                raise ValueError('Another chapter resource uses this map storage. No data was written.')
        palette=pc_address(int.from_bytes(data[h+9:h+12],'little'))
        if palette<address+SLOT_SIZE and palette+224>address:
            raise ValueError('A chapter palette uses this map storage. No data was written.')
    return [(ARENA,MAGIC.ljust(16,b'\0')+bytes([fill])+bytes(15)),
            (address,packed),
            (model.header,pointer_for(address).to_bytes(3,'little'))]
