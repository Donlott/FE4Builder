"""Generated menu/icon/combat tables for expansion tests; no game ROM needed."""
from pathlib import Path
from tempfile import TemporaryDirectory

from rom import Rom
from item_art import ItemArt
from item_expansion import OLD_POINTERS, OLD_PLAYERS, program, put
from test_combat_art import combat_fixture
from menu_text_fixture import make_text_rom


def fixture(directory, header=False):
    path = combat_fixture(directory, header);rom = Rom(path)
    with TemporaryDirectory() as folder:
        text = Rom(make_text_rom(folder))
        for at, size in ((0x119961, 0xC0), (0x128000, 0x3000), (0x500000, 0x10000),
                         (0x568000, 0x9000), (0x572000, 0xE000), (0x580000, 0xA000),
                         (0x594000, 0x9000), (0x5A0000, 0x10000), (0x484FF, 4),
                         (0x511A11, 5), (0x9A3F6, 16)):
            put(rom, at, bytes(text.data[at:at+size]))
    from menu_text import ITEM_HELP_PREFIX, ITEM_HELP_READERS
    for at in ITEM_HELP_READERS:put(rom, at-len(ITEM_HELP_PREFIX), ITEM_HELP_PREFIX)
    for at, (old, _) in program()[1].items():put(rom, at, old)
    art = ItemArt(rom)
    for item in range(138):
        module, index = art.record(item);at = rom.address(module, index)-rom.header
        raw = bytearray(rom.data[at+rom.header:at+rom.header+(10 if 0x6A<=item<0x7A or item==0x89 else 19)])
        raw[0] = item;raw[1] = 2 if len(raw)==10 else 0
        if len(raw)==19:
            raw[2] = 50
            if not raw[14]:raw[14] = 1
            if not raw[15]:raw[15] = 1
        put(rom,at,raw);put(rom,OLD_POINTERS+item*2,(at-OLD_POINTERS).to_bytes(2,'little'))
        put(rom,0xD9402+item*2,(0x6700+(item%110)*16).to_bytes(2,'little'))
    put(rom,OLD_PLAYERS,bytes(140)+b'\xff\xff')
    path.write_bytes(rom.data)
    return path
