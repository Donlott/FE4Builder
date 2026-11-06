"""Generated Project Naga-compatible hooks and item data; no game ROM required."""
from rom import Rom
from bonus_profile_fixture import fixture as bonus_fixture
from item_expansion import put, update_checksum
from weapon_skills import GUARDS, ARENA, SIZE


def fixture(directory, header=False, fill=0):
    path=bonus_fixture(directory,header);rom=Rom(path)
    for at,raw in GUARDS.items():put(rom,at,raw)
    native=(0,0x1000,0,0,0x800,0,1,0,0,0,2,0,0,0,0,8,16,0,0,0,0,0,0,0,32,64,128,256,512,1024)
    put(rom,0x7A280,b''.join(v.to_bytes(2,'little') for v in native))
    put(rom,ARENA,bytes([fill])*SIZE);update_checksum(rom)
    path.write_bytes(rom.data)
    return path
