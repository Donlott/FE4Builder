"""Generated weapon bonus reader, tables and original single-stat effects."""
from rom import Rom
from item_expansion import put, record, item_pointer
from item_expansion_fixture import fixture as item_fixture
from item_bonuses import CODE_EFFECTS
from bonus_profiles import READER, NATIVE


def fixture(directory, header=False):
    path=item_fixture(directory,header);rom=Rom(path)
    put(rom,READER,NATIVE)
    boosts=((0,0,10,10,0,20),(0,0,20,20,20,20),(10,0,0,10,10,0),
            (10,0,10,0,10,0),(0,0,10,20,0,0),(10,0,0,10,0,0),
            (0,0,0,0,20,10),(0,10,0,0,10,10),(0,0,20,10,0,0),
            (0,0,10,20,0,0),(0,0,0,0,0,0),(0,0,20,0,0,10),(0,0,0,0,0,5))
    for i,values in enumerate(boosts):
        relative=26+i*16
        put(rom,0x389C9+i*2,relative.to_bytes(2,'little'))
        put(rom,0x389C9+relative,bytes([i+1])*10+bytes(values))
        raw=bytearray(record(rom,i));raw[5]=i+1;put(rom,item_pointer(rom,i),raw)
    for key,(_,offsets,prefix,suffix) in CODE_EFFECTS.items():
        for at in offsets:put(rom,at-len(prefix),prefix+(3 if key==('ring',6) else 5).to_bytes(2,'little')+suffix)
    path.write_bytes(rom.data)
    return path
