"""Synthetic Project Naga text layout; no commercial ROM/font is required."""
from pathlib import Path
from types import SimpleNamespace
from menu_text import MenuFont, catalogue, pack, SKILL_IDS
from names import tile_bytes


def make_text_rom(directory, header=False):
    raw = bytearray(0x800000)
    raw[0xFFC0:0xFFD5] = b'FIREEMBLEM4'.ljust(21, b' ')
    raw[0x484FF:0x48503] = bytes.fromhex('22 00 0C 51')
    for code in range(0x10, 0xA6):
        width = 8 if code == 0x26 else 2 if code in (0x18, 0x32, 0x35) else 6
        raw[0x119961 + code] = width
        rows = [[0] * 16 for _ in range(16)]
        rows[2][1] = rows[12][1] = 2
        for bit in range(8):
            if code & 1 << bit:
                rows[3 + bit][1] = 2
        index = code - 0x10
        tile = index // 8 * 32 + index % 8 * 2
        for y in range(2):
            for x in range(2):
                at = 0x128000 + (tile + y * 16 + x) * 16
                raw[at:at + 16] = tile_bytes(rows, x, y)
    raw[0x119A20] = 3
    rom = SimpleNamespace(data=raw, header=0)
    font = MenuFont(rom)
    for entry in catalogue()['entries']:
        kind = entry['kind']
        if kind in ('name', 'description'):
            for count_at, pointer_at, align in entry['variants']:
                lines = 3 if kind == 'description' and entry['id'] == 1 else 1
                tiles = 16 if kind == 'description' else 8 if align == 'center' else 1
                base = entry['pool'][0]
                pointer = base + (0x8000 + (0x1000 if lines == 3 else 0) if kind == 'description' else
                                  0x100 if align == 'right' else 0x200 if align == 'center' else 0)
                text = font.render_line('A') + [[0] * 7 for _ in range((lines - 1) * 16)]
                gfx = pack(text, tiles, lines, align)
                raw[pointer:pointer + len(gfx)] = gfx
                raw[entry['table'] + count_at] = tiles * lines
                at = entry['table'] + pointer_at
                raw[at:at + 3] = pointer.to_bytes(3, 'little')
        elif kind == 'skill':
            pointer = 0x594000 + entry['slot'] * 0x800
            raw[entry['pointer']:entry['pointer'] + 3] = pointer.to_bytes(3, 'little')
            gfx = pack(font.render_line('A') + [[0] * 7 for _ in range(48)], 16, 4)
            raw[pointer:pointer + len(gfx)] = gfx
        elif kind == 'effect':
            raw[entry['graphics']:entry['graphics'] + 512] = pack(font.render_line('A'), 16)
        else:
            raw[entry['address']:entry['address'] + 16] = bytes([0x10, 1]) + bytes(14)
    for i, _ in enumerate(SKILL_IDS):
        tile = 0x20 + i % 16 + i // 16 * 0x20
        at = 0x507A00 + i * 32
        raw[at:at + 14] = (0x100 + tile).to_bytes(2, 'big') + b'\x81\x40' * 6
        rows = font.render_line('A')
        for y in range(2):
            target = 0x450000 + (tile + y * 16) * 16
            raw[target:target + 16] = tile_bytes(rows, 0, y)
    path = Path(directory) / ('text.smc' if header else 'text.sfc')
    path.write_bytes((bytes(512) if header else b'') + raw)
    return path
