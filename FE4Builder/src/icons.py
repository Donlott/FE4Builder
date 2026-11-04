"""Native 16x16 inventory/skill artwork, assignments and bounded atlas packing.

All offsets exclude a copier header. Icons remain raw 4bpp for the game's DMA
loaders. Optimization shares whole identical icons; it does not claim to shrink
a fixed VRAM upload or the ROM file. No new item types or skill effects are made.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

from portraits import export_png, pointer_for, pc_address

ITEM_GRAPHICS = 0x184000
ITEM_LOOKUP = 0xD1AE
# Item sprites add $20 to the atlas tile. The final physical sheet row would
# overflow the nine-bit OBJ tile number into palette bits; retain it as padding.
ITEM_CAPACITY = 120
SKILL_GRAPHICS = 0x1E34C0
ARENA = 0x6FC000
SIZE = 0x2000
PRIVATE_GRAPHICS = ARENA + 0x100
MAGIC = b'FE4BICONSv1'.ljust(16, b'\0')
TABLES = (0x99300, 0x9A52F, 0xBDB7E)
COMPACT_BITS = (1, 2, 3, 4, 5, 7, 11, 13, 14, 15, 16, 17, 18, 19, 20, 23, 24, 27)
SKILLS = ('Canto', 'Pavise', 'Wrath', 'Pursuit', 'Adept', 'Steal',
          'Unused 1', 'Dance', 'Unused 2', 'Valkyrie music', 'Dismount',
          'Charm', 'Unused 4', 'Nihil', 'Miracle', 'Critical', 'Vantage',
          'Accost', 'Astra', 'Luna', 'Sol', 'Light Sword', 'Dark Sword',
          'Renewal', 'Paragon', 'Escape', 'Recover', 'Bargain', 'Return')
CONTEXTS = ('Stat screen', 'Stat screen help', 'Skill list help')
# Source, byte length, VMAIN and destination are checked as one DMA descriptor.
LOADERS = ((0xBD70, 0x6800), (0xC57A, 0), (0xD39A, 0x4200))
NEIGHBORS = ((0xBD63, '02 00 02 DE 00 08 80 00 70'),
             (0xBD7D, '02 00 0A DE 00 0C 80 00 74'),
             (0xC56D, '02 00 02 DE 00 08 80 00 64'),
             (0xD38D, '02 C0 44 DE 00 04 80 00 40'))
# The menus overwrite their initial OBJ palettes after loading the graphics.
# These indexed-long copy loops load the skill palette into OBJ bank 7 (stats)
# or bank 3 (Skills menu). Their source operand points two bytes before color 0.
SKILL_PALETTE_LOADERS = ((0xBE0A, 0x02DE), (0xD3D8, 0x025E))


def read(rom, at, size):
    if at < 0 or at + size > len(rom.data) - rom.header:
        raise ValueError('Icon data points outside this ROM.')
    return bytes(rom.data[at + rom.header:at + rom.header + size])


def tile(slot):
    return slot // 8 * 32 + slot % 8 * 2


def slot(value, capacity):
    if value < 0 or value % 2 or value % 32 > 14:
        raise ValueError(f'Unsupported icon tile reference {value:04X}.')
    result = value // 32 * 8 + value % 32 // 2
    if result >= capacity:
        raise ValueError(f'Icon tile {value:04X} exceeds the loaded atlas.')
    return result


def unpack(raw):
    if len(raw) != 128:
        raise ValueError('An icon must contain four 4bpp tiles.')
    rows = [[0] * 16 for _ in range(16)]
    for y, row in enumerate(rows):
        for x in range(16):
            at = (y // 8 * 2 + x // 8) * 32 + y % 8 * 2
            row[x] = sum(((raw[at + p // 2 * 16 + p % 2] >> (7 - x % 8)) & 1) << p for p in range(4))
    return rows


def pack(rows):
    if len(rows) != 16 or any(len(row) != 16 for row in rows):
        raise ValueError('Use a 16 x 16 icon; no resizing is performed.')
    if any(type(v) is not int or not 0 <= v < 16 for row in rows for v in row):
        raise ValueError('Icon pixels must use palette indices 0 through 15.')
    raw = bytearray(128)
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            at = (y // 8 * 2 + x // 8) * 32 + y % 8 * 2
            for p in range(4):
                raw[at + p // 2 * 16 + p % 2] |= ((value >> p) & 1) << (7 - x % 8)
    return bytes(raw)


def split_atlas(raw):
    if len(raw) % 1024:
        raise ValueError('Incomplete icon atlas row.')
    return [raw[tile(i) * 32:tile(i) * 32 + 64] +
            raw[tile(i) * 32 + 512:tile(i) * 32 + 576] for i in range(len(raw) // 128)]


def join_atlas(icons):
    if len(icons) % 8 or any(len(icon) != 128 for icon in icons):
        raise ValueError('Incomplete icon atlas.')
    raw = bytearray(len(icons) * 128)
    for i, icon in enumerate(icons):
        at = tile(i) * 32
        raw[at:at + 64] = icon[:64]
        raw[at + 512:at + 576] = icon[64:]
    return bytes(raw)


def dma(pointer, length, destination):
    return b'\x02' + pointer.to_bytes(3, 'little') + length.to_bytes(2, 'little') + b'\x80' + destination.to_bytes(2, 'little')


def digest(block):
    return hashlib.sha256(block[:64] + block[96:]).digest()


def skill_palette_address(rom, context=0):
    if context not in (0, 1, 2):raise ValueError('Unknown skill display context.')
    at, destination = SKILL_PALETTE_LOADERS[context == 2]
    code = read(rom, at, 14)
    if (code[:4] != bytes.fromhex('A2 20 00 BF') or code[7:10] != b'\x9D' + destination.to_bytes(2, 'little') or
            code[10:] != bytes.fromhex('CA CA D0 F5')):
        raise ValueError('The skill icon palette loader differs from the supported layout.')
    source = pc_address(int.from_bytes(code[4:7], 'little') + 2)
    read(rom, source, 32)
    return source


def profile(rom, expanded):
    if len(rom.data) - rom.header != 0x800000 or read(rom, 0xFFD5, 1)[0] & 0x2F != 0x25:
        raise ValueError('Icon editing requires the supported 8 MiB ExHiROM layout.')
    expected = bytes.fromhex('22 BD A4 80') + dma(0xD84000, 0x4000, 0x4200)
    if read(rom, 0xCDEC, len(expected)) != expected:
        raise ValueError('The inventory icon loader has custom code. No icons were changed.')
    for context in (0, 2):skill_palette_address(rom, context)
    guards = ((0xD187, 'BF AE D1 80'), (0x9A397, 'BF FE 92 89'),
              (0x9A519, 'BF 2D A5 89'), (0xBDB5A, 'BF 7E DB 8B'))
    for at, sequence in guards:
        if read(rom, at, len(bytes.fromhex(sequence))) != bytes.fromhex(sequence):
            raise ValueError(f'The icon assignment reader at PC {at:06X} has custom code.')
    for at, sequence in ((0x9BE49, '01 00 00 C2 FE 20 36'),
                         (0x992F7, '01 00 00 C2 00 80 3E'),
                         (0x9A56B, '01 00 14 C2 60 80 3E'),
                         (0xBDB77, '01 00 96 C2 20 20 36')):
        expected = bytes.fromhex(sequence)
        if read(rom, at, len(expected)) != expected:
            raise ValueError('Icon sprite positioning or palette layout changed; tile capacity cannot be verified.')
    # Keep both copies of bank-$80 code consistent. The ExHiROM low-bank
    # mirror can be reached by other game paths, and is never silently ignored.
    for mirror in (0, 0x400000):
        for at, destination in LOADERS:
            source = pointer_for(PRIVATE_GRAPHICS) if expanded else 0xDE34C0
            expected = b'\x22\xBD\xA4\x80' + dma(source, 0x1000 if expanded else 0xC00, destination)
            if read(rom, at - 4 + mirror, len(expected)) != expected:
                raise ValueError(f'The skill icon loader at PC {at + mirror:06X} differs from the supported layout.')
        for at, sequence in NEIGHBORS:
            expected = bytes.fromhex(sequence)
            if read(rom, at + mirror, len(expected)) != expected:
                raise ValueError('Neighboring menu graphics changed; skill atlas capacity cannot be verified.')


class IconDocument:
    def __init__(self, rom):
        self.rom = rom
        self.snapshot = bytes(rom.data)
        self.storage = read(rom, ARENA, SIZE)
        owned = self.storage[:16] == MAGIC
        self.expanded = False
        self.flags = {'items': set(), 'skills': set()}
        self.baseline = None
        self.storage_error = None
        if owned:
            b = self.storage
            if (b[16] not in (0, 255) or b[17] != 1 or b[18] not in (0, 1) or
                    b[19] != 0 or b[48:64] != bytes(16) or b[96:256] != bytes(160) or b[64:96] != digest(b)):
                raise ValueError('Private icon storage is invalid. Restore a backup or reopen the correct ROM.')
            self.expanded = bool(b[18])
            for kind, start, count in (('items', 20, 128), ('skills', 36, 32)):
                bits = int.from_bytes(b[start:start + count // 8], 'little')
                self.flags[kind] = {i for i in range(count) if bits & (1 << i)}
            self.baseline = dict(items=int.from_bytes(b[40:42], 'little'), skills=int.from_bytes(b[42:44], 'little'),
                                 loaded=int.from_bytes(b[44:48], 'little'))
            if not 0 <= self.baseline['items'] <= ITEM_CAPACITY or not 0 <= self.baseline['skills'] <= 32 or self.baseline['loaded'] not in (19456, 20480):
                raise ValueError('Invalid original icon size record.')
        elif len(set(self.storage)) != 1 or self.storage[0] not in (0, 255):
            self.storage_error = 'Reserved icon storage at PC 6FC000-6FDFFF is occupied; writing is disabled.'
        profile(rom, self.expanded)
        self.art = {'items': split_atlas(read(rom, ITEM_GRAPHICS, ITEM_CAPACITY * 128)),
                    'skills': split_atlas(read(rom, PRIVATE_GRAPHICS if self.expanded else SKILL_GRAPHICS,
                                               0x1000 if self.expanded else 0xC00))}
        self.refs = {'items': [slot(int.from_bytes(read(rom, ITEM_LOOKUP + i * 2, 2), 'little'), ITEM_CAPACITY) for i in range(138)],
                     'skills': []}
        for context, (at, count) in enumerate(zip(TABLES, (29, 29, 18))):
            values = []
            for i in range(count):
                v = int.from_bytes(read(rom, at + i * 2, 2), 'little')
                values.append(None if context == 0 and v == 0xFFFF else slot(v, len(self.art['skills'])))
            self.refs['skills'].append(values)
        if any(i >= len(self.art[kind]) for kind in self.flags for i in self.flags[kind]):
            raise ValueError('Icon library references an unavailable atlas row.')
        self.original = deepcopy((self.art, self.refs, self.flags))

    @property
    def dirty(self):
        return (self.art, self.refs, self.flags) != self.original

    def references(self, kind):
        return self.refs[kind] if kind == 'items' else [s for group in self.refs['skills'] for s in group if s is not None]

    def active(self, kind):
        return sorted(set(self.references(kind)) | self.flags[kind] | {i for i, raw in enumerate(self.art[kind]) if any(raw)})

    def free(self, kind):
        return sorted(set(range(len(self.art[kind]))) - set(self.active(kind)))

    def colors(self, kind, context=0):
        at = skill_palette_address(self.rom, context) if kind == 'skills' else 0x1E0160
        # Match the existing native inventory preview's 5-bit channel scaling.
        return [tuple(((int.from_bytes(read(self.rom, at + i * 2, 2), 'little') >> shift) & 31) << 3
                      for shift in (0, 5, 10)) for i in range(16)]

    def png(self, kind, index, context=0):
        return export_png(unpack(self.art[kind][index]), self.colors(kind, context))

    def add(self, kind, raw):
        if kind not in self.art or len(raw) != 128:
            raise ValueError('Choose a valid 16 x 16 icon.')
        free = self.free(kind)
        if not free:
            if kind == 'skills' and len(self.art[kind]) == 24:
                free = list(range(24, 32))
                self.art[kind].extend([bytes(128)] * 8)
            else:
                raise ValueError(f'The {kind} atlas is full ({len(self.art[kind])} slots). Optimize duplicates or replace an existing icon.')
        index = free[0]
        self.art[kind][index] = bytes(raw)
        self.flags[kind].add(index)
        return index

    def replace(self, kind, index, rows):
        raw = pack(rows)
        if not 0 <= index < len(self.art[kind]):
            raise ValueError('Icon slot is outside the loaded sheet.')
        self.art[kind][index] = raw

    def assign(self, kind, record, index, context=0, linked=True):
        if type(index) is not int or not 0 <= index < len(self.art[kind]):
            raise ValueError('Select an existing icon.')
        if kind == 'items':
            if not 0 <= record < 138:raise ValueError('Unknown item.')
            self.refs[kind][record] = index
            return
        if not 0 <= record < 29 or not 0 <= context < 3:
            raise ValueError('Unknown skill or display context.')
        if context == 2 and record not in COMPACT_BITS:
            raise ValueError('This skill has no entry in the compact Skills menu.')
        for c in range(3) if linked else (context,):
            if c == 2:
                if record in COMPACT_BITS:self.refs[kind][c][COMPACT_BITS.index(record)] = index
            else:self.refs[kind][c][record] = index

    def selected(self, kind, record, context=0):
        if kind == 'items':return self.refs[kind][record]
        if context == 2:
            return self.refs[kind][2][COMPACT_BITS.index(record)] if record in COMPACT_BITS else None
        return self.refs[kind][context][record]

    def users(self, kind, index):
        if kind == 'items':return [(i, None) for i, v in enumerate(self.refs[kind]) if v == index]
        return [(COMPACT_BITS[i] if c == 2 else i, c) for c, group in enumerate(self.refs[kind]) for i, v in enumerate(group) if v == index]

    def optimized(self):
        clone = object.__new__(IconDocument)
        clone.__dict__ = dict(self.__dict__)
        clone.art, clone.refs, clone.flags = deepcopy((self.art, self.refs, self.flags))
        for kind in ('items', 'skills'):
            unique, mapping, packed = {}, {}, []
            for i in self.active(kind):
                raw = self.art[kind][i]
                if raw not in unique:
                    unique[raw] = len(packed);packed.append(raw)
                mapping[i] = unique[raw]
            capacity = ITEM_CAPACITY if kind == 'items' else 24 if len(packed) <= 24 else 32
            clone.art[kind] = packed + [bytes(128)] * (capacity - len(packed))
            clone.flags[kind] = {mapping[i] for i in self.flags[kind]}
            if kind == 'items':clone.refs[kind] = [mapping[v] for v in self.refs[kind]]
            else:clone.refs[kind] = [[mapping[v] if v is not None else None for v in group] for group in self.refs[kind]]
        return clone

    def sizes(self):
        return dict(items=len(self.active('items')), skills=len(self.active('skills')),
                    loaded=0x4000 + len(self.art['skills']) * 128)

    def plan(self, optimize=False, baseline=None):
        if bytes(self.rom.data) != self.snapshot:
            raise ValueError('The ROM changed while this icon editor was open. Reload before writing.')
        target = self.optimized() if optimize else self
        if (target.art, target.refs, target.flags) == self.original:return [], target
        if self.storage_error:raise ValueError(self.storage_error)
        baseline = baseline or self.baseline or self.sizes_original()
        edits = [(ITEM_GRAPHICS, join_atlas(target.art['items']))]
        edits.append((ITEM_LOOKUP, b''.join(tile(v).to_bytes(2, 'little') for v in target.refs['items'])))
        for at, group in zip(TABLES, target.refs['skills']):
            edits.append((at, b''.join((0xFFFF if v is None else tile(v)).to_bytes(2, 'little') for v in group)))
        expanded = len(target.art['skills']) == 32
        block = bytearray([self.storage[16] if self.storage[:16] == MAGIC else self.storage[0]]) * SIZE
        fill = block[0]
        block[:256] = bytes(256)
        block[:16] = MAGIC
        block[16:19] = bytes([fill, 1, int(expanded)])
        for kind, at, count in (('items', 20, 128), ('skills', 36, 32)):
            block[at:at + count // 8] = sum(1 << i for i in target.flags[kind]).to_bytes(count // 8, 'little')
        block[40:42] = baseline['items'].to_bytes(2, 'little')
        block[42:44] = baseline['skills'].to_bytes(2, 'little')
        block[44:48] = baseline['loaded'].to_bytes(4, 'little')
        raw = join_atlas(target.art['skills'])
        if expanded:block[256:256 + len(raw)] = raw
        else:edits.append((SKILL_GRAPHICS, raw))
        for mirror in (0, 0x400000):
            for at, destination in LOADERS:
                edits.append((at + mirror, dma(pointer_for(PRIVATE_GRAPHICS) if expanded else 0xDE34C0, len(raw), destination)))
        block[64:96] = digest(block)
        edits.append((ARENA, bytes(block)))
        return [(at, raw) for at, raw in edits if read(self.rom, at, len(raw)) != raw], target

    def sizes_original(self):
        clone = object.__new__(IconDocument);clone.__dict__ = dict(self.__dict__)
        clone.art, clone.refs, clone.flags = self.original
        return clone.sizes()

    def commit(self, optimize=False, baseline=None):
        edits, target = self.plan(optimize, baseline)
        if not edits:return False
        before = bytes(self.rom.data)
        sizes = target.sizes()
        try:
            for at, raw in edits:self.rom.data[at + self.rom.header:at + self.rom.header + len(raw)] = raw
            # Reopen all pointers/metadata before any disk write.
            IconDocument(self.rom)
            self.rom.save_original('Icon editor', [f'{sizes["items"]} item icons; {sizes["skills"]} skill icons; {sizes["loaded"]:,} loaded bytes.',
                                                  'Shared identical icons and repacked sheets.' if optimize else 'Saved staged artwork and icon assignments.'])
        except Exception:
            self.rom.data[:] = before
            raise
        return True


def import_png(master, path, colors, reduce=False):
    """Fixed native palette; preserve indexed exports, including duplicate RGBs."""
    import tkinter as tk
    from intro_graphics import indexed_png
    from portrait_window import _check_png_alpha
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or data[16:24] != bytes.fromhex('00 00 00 10 00 00 00 10'):
        raise ValueError('Import a 16 x 16 PNG. Export an icon as a template.')
    image = tk.PhotoImage(master=master, file=str(path))
    _check_png_alpha(data)
    indexed = indexed_png(path)
    if indexed and indexed[1] == colors and all(0 <= v < 16 for line in indexed[0] for v in line):
        rows = indexed[0]
        if all(image.transparency_get(x, y) == (v == 0) for y, row in enumerate(rows) for x, v in enumerate(row)):
            return pack(rows), False
    rows, reduced = [], False
    for y in range(16):
        row = []
        for x in range(16):
            if image.transparency_get(x, y):row.append(0);continue
            rgb = image.get(x, y)
            if rgb in colors[1:]:row.append(1 + colors[1:].index(rgb));continue
            if not reduce:raise ValueError('This PNG uses colors outside the native icon palette. Enable color reduction to preview the closest available colors.')
            row.append(min(range(1, 16), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, colors[i]))))
            reduced = True
        rows.append(row)
    return pack(rows), reduced
