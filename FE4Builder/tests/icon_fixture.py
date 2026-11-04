"""Synthetic native icon loaders/data; no game artwork or ROM required."""
from pathlib import Path
from icons import (LOADERS, NEIGHBORS, TABLES, COMPACT_BITS, ITEM_LOOKUP,
                   ITEM_GRAPHICS, SKILL_GRAPHICS, join_atlas, dma, tile)


def icon(value):
    return bytes([value, value ^ 0xFF, value >> 4, value & 15]) + bytes(124)


def fixture(directory, header=False):
    data = bytearray(0x800000)
    data[0xFFC0:0xFFD5] = b'FIREEMBLEM4'.ljust(21, b' ')
    data[0xFFD5] = 0x25
    def put(at, raw):data[at:at + len(raw)] = raw
    put(0xCDEC, b'\x22\xBD\xA4\x80' + dma(0xD84000, 0x4000, 0x4200))
    for at, raw in ((0xD187, 'BF AE D1 80'), (0x9A397, 'BF FE 92 89'),
                    (0x9A519, 'BF 2D A5 89'), (0xBDB5A, 'BF 7E DB 8B')):put(at, bytes.fromhex(raw))
    for at, raw in ((0x9BE49, '01 00 00 C2 FE 20 36'), (0x992F7, '01 00 00 C2 00 80 3E'),
                    (0x9A56B, '01 00 14 C2 60 80 3E'), (0xBDB77, '01 00 96 C2 20 20 36')):put(at, bytes.fromhex(raw))
    for mirror in (0, 0x400000):
        for at, destination in LOADERS:put(at - 4 + mirror, b'\x22\xBD\xA4\x80' + dma(0xDE34C0, 0xC00, destination))
        for at, raw in NEIGHBORS:put(at + mirror, bytes.fromhex(raw))
    put(ITEM_GRAPHICS, join_atlas([icon(i + 1) for i in range(111)] + [bytes(128)] * 17))
    put(SKILL_GRAPHICS, join_atlas([icon(i + 160) for i in range(24)]))
    put(ITEM_LOOKUP, b''.join(tile(i % 111).to_bytes(2, 'little') for i in range(138)))
    for at, count in zip(TABLES, (29, 29, 18)):put(at, b''.join(tile(i % 24).to_bytes(2, 'little') for i in range(count)))
    for at in (0x1E0160, 0x1E01E0):
        put(at, b''.join((i + (i << 5) + (i << 10)).to_bytes(2, 'little') for i in range(16)))
    path = Path(directory) / ('icons.smc' if header else 'icons.sfc')
    path.write_bytes((bytes([43]) * 512 if header else b'') + data)
    return path
