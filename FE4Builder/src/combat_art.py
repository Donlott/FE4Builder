"""Per-item physical combat animation aliases; keep stats and artwork intact.

Native item slots also select battle poses, spell effects and map weapons.
Changing their stats or inventory icons does not change these selections.
Aliases affect only those three presentation lookups, never the combat item ID.
"""
import hashlib

from growth_patch import Assembler
from item_art import ItemArt, ASSIGNMENTS, ITEM_COUNT

ARENA = 0x6FE000
SIZE = 0x1000
LOOKUP = ARENA + 0x100
CODE = ARENA + 0x200
MAGIC = b'FE4BCOMBATv1'.ljust(16, b'\0')
STYLES = 0x1983BA
STYLE_TYPES = {0x00: 0, 0x12: 1, 0x23: 2, 0x34: 3, 0x52: 1, 0x63: 2}


def program():
    a = Assembler()
    a.mark('alias')
    a.emit('C9');a.word(ITEM_COUNT);a.branch('B0', 'return')
    a.emit('DA 48 AA BF');a.long(LOOKUP)
    a.emit('29 FF 00 C9 FF 00');a.branch('F0', 'original')
    a.emit('83 01')                 # replace saved A only for configured items
    a.mark('original');a.emit('68 FA')
    a.mark('return');a.emit('6B')
    a.mark('style')
    a.call(CODE + a.labels['alias'])
    a.emit('DA 1A C9 7F 00 5C');a.long(0x95A1F2)
    a.mark('effect')
    a.emit('BD 52 0D')             # caller selected attacker/defender in X
    a.call(CODE + a.labels['alias'])
    a.emit('48 5C');a.long(0x96DC8E)
    a.mark('map')
    a.emit('DA 5A')
    a.call(CODE + a.labels['alias'])
    a.emit('C9 FF FF 5C');a.long(0x9E8E06)
    code = a.finish()
    hooks = {}
    for at, old, label in ((0x15A1ED, 'DA 1A C9 7F 00', 'style'),
                           (0x16DC8A, 'BD 52 0D 48', 'effect'),
                           (0x1E8E01, 'DA 5A C9 FF FF', 'map')):
        old = bytes.fromhex(old)
        hooks[at] = old, b'\x5C' + (CODE + a.labels[label]).to_bytes(3, 'little') + b'\xEA' * (len(old) - 4)
    return code, hooks, {name: CODE + offset for name, offset in a.labels.items()}


def read(rom, at, size):
    if not 0 <= at < at + size <= len(rom.data) - rom.header:
        raise ValueError('Combat animation data points outside this ROM.')
    return bytes(rom.data[at + rom.header:at + rom.header + size])


def digest(block):
    return hashlib.sha256(block[:32] + block[64:]).digest()


class CombatArtwork:
    def __init__(self, rom):
        self.rom, self.snapshot = rom, bytes(rom.data)
        if len(rom.data) - rom.header != 0x800000 or read(rom, 0xFFD5, 1)[0] & 0x2F != 0x25:
            raise ValueError('Combat animation repair requires the supported 8 MiB ExHiROM layout.')
        self.code, self.hooks, _ = program()
        self.block = read(rom, ARENA, SIZE)
        self.installed = self.block[:16] == MAGIC
        if self.installed:
            b = self.block
            if (b[16] not in (0, 255) or b[17] != 1 or any(b[18:32]) or b[32:64] != digest(b) or
                    b[0x200:0x200 + len(self.code)] != self.code):
                raise ValueError('Combat animation repair data changed. Restore a backup.')
            self.aliases = list(b[0x100:0x100 + ITEM_COUNT])
        else:
            if len(set(self.block)) != 1 or self.block[0] not in (0, 255):
                raise ValueError('Combat animation repair storage at PC 6FE000–6FEFFF is occupied.')
            self.aliases = [255] * ITEM_COUNT
        for at, (old, new) in self.hooks.items():
            if read(rom, at, len(old)) != (new if self.installed else old):
                raise ValueError(f'The combat animation selector at PC {at:06X} has custom code.')
        guards = ((0x15A1F5, 'BF B9 83 99'), (0x16DC7C, 'DA E0 00 00 D0 05 A2 00 00 80 03 A2 0E 00'),
                  (0x16DC91, 'BF 2D 83 99'), (0x16DCB6, 'BF 2E 83 99'), (0x16DCBC, 'BF 2F 83 99'),
                  (0x1E8E36, 'BF C4 8E 9E'), (0x1E8E8F, 'BF C4 8E 9E'),
                  (0x1586BB, 'BF 25 87 99'))
        for at, raw in guards:
            raw = bytes.fromhex(raw)
            if read(rom, at, len(raw)) != raw:
                raise ValueError(f'The combat artwork loader at PC {at:06X} has custom code.')
        if any(v != 255 and not self.native_donor(v) for v in self.aliases):
            raise ValueError('Combat animation repair contains an unsupported base weapon.')
        self.art = ItemArt(rom)

    def native_donor(self, item):
        return (0 <= item < 0x3A or 0x7A <= item <= 0x7C) and read(self.rom, STYLES + item, 1)[0] in STYLE_TYPES

    def candidates(self, item):
        stats = self.art.stats(item)
        kind = stats.get('Weapon Type')
        if stats.get('Type') != 0 or kind not in range(4):return []
        minimum, maximum = stats['Minimum Range'], stats['Maximum Range']
        result = []
        for donor in range(0x7D):
            if not self.native_donor(donor):continue
            style = read(self.rom, STYLES + donor, 1)[0]
            if STYLE_TYPES[style] != kind:continue
            if style == 0x34:
                if (minimum, maximum) != (2, 2):continue
            elif not 1 <= minimum <= maximum <= (2 if style in (0x52, 0x63) else 1):continue
            # A repurposed donor can itself lack compatible artwork/semantics.
            donor_stats = self.art.stats(donor)
            if donor_stats.get('Type') != 0 or donor_stats.get('Weapon Type') != kind:continue
            sprite = read(self.rom, ASSIGNMENTS + donor * 2, 1)[0]
            if sprite >= 65:continue
            result.append(donor)
        sprite = read(self.rom, ASSIGNMENTS + item * 2, 1)[0] if item < 125 else 255
        return sorted(result, key=lambda d: (read(self.rom, ASSIGNMENTS + d * 2, 1)[0] != sprite,
                                            self.art.stats(d).get('Rank') == 255, d))

    def plan(self, item, donor):
        if bytes(self.rom.data) != self.snapshot:
            raise ValueError('The ROM changed. Reopen combat animations before writing.')
        if type(item) is not int or not 0 <= item < min(125, ITEM_COUNT):
            raise ValueError('This item has no supported held-weapon sprite assignment.')
        if donor == item:donor = None
        if donor is not None and donor not in self.candidates(item):
            raise ValueError('Choose a compatible physical weapon with animations for this attack range.')
        if donor is not None:
            sprite, palette = read(self.rom, ASSIGNMENTS + item * 2, 2)
            if sprite >= 65 or palette >= 36:
                raise ValueError('Assign a valid held-weapon Sprite and Palette in the Item Sprite Editor first.')
        aliases = self.aliases.copy();aliases[item] = 255 if donor is None else donor
        if aliases == self.aliases:return []
        enabled = any(v != 255 for v in aliases)
        fill = self.block[16] if self.installed else self.block[0]
        block = bytearray([fill]) * SIZE
        if enabled:
            block[:64] = bytes(64);block[:16] = MAGIC;block[16:18] = bytes([fill, 1])
            block[0x100:0x100 + ITEM_COUNT] = bytes(aliases)
            block[0x200:0x200 + len(self.code)] = self.code
            block[32:64] = digest(block)
        edits = [(ARENA, bytes(block))]
        edits += [(at, new if enabled else old) for at, (old, new) in self.hooks.items()]
        return [(at, raw) for at, raw in edits if read(self.rom, at, len(raw)) != raw]

    def commit(self, item, donor):
        edits = self.plan(item, donor)
        if not edits:return False
        before = bytes(self.rom.data)
        try:
            for at, raw in edits:self.rom.data[at + self.rom.header:at + self.rom.header + len(raw)] = raw
            CombatArtwork(self.rom)
            self.rom.save_original('Combat animations', [f'Item {item:02X}: ' + ('original slot animations' if donor is None else f'physical animations from item {donor:02X}'),
                                                       'Preserved item stats, inventory icons, held-weapon artwork and palettes.'])
        except Exception:
            self.rom.data[:] = before
            raise
        return True
