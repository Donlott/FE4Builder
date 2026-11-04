"""Project Naga menu text: read the ROM's bitmap font, preserve native layouts.

Names/descriptions are 2bpp artwork, not ordinary strings. Changed pointer-based
entries receive private artwork; shared originals are never overwritten. The
verified, originally empty $5B0000–$5FFFFF region is independent of maps,
portraits, dialogue, backgrounds and the signed-stat patch.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json

from rom import DATA_DIR
from names import tile_bytes
from dialogue import GLYPHS, ALIASES

ARENA = 0x5B0000
SIZE = 0x50000
START = 0x3000
MAX_ENTRIES = 1024
MAGIC = b'FE4BMENUTEXTv1'.ljust(16, b'\0')
SKILL_IDS = (0, 1, 2, 3, 4, 6, 10, 12, 13, 14, 15, 16, 17, 18, 19, 22, 23, 26)


@lru_cache(None)
def catalogue():
    return json.loads((DATA_DIR / 'menu_text.json').read_text(encoding='utf-8'))


@lru_cache(None)
def reference_hints():
    path = DATA_DIR / 'menu_text_hints.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


@lru_cache(None)
def catalogue_fingerprint():
    return hashlib.sha256(json.dumps(catalogue()['entries'], sort_keys=True).encode()).digest()[:16]


def read(rom, at, size):
    if at < 0 or at + size > len(rom.data) - rom.header:
        raise ValueError('Menu text points outside the ROM.')
    return bytes(rom.data[at + rom.header:at + rom.header + size])


def unpack(raw, tiles, lines=1):
    if len(raw) != tiles * lines * 32:
        raise ValueError('Incomplete menu text artwork.')
    rows = [[0] * (tiles * 8) for _ in range(lines * 16)]
    for y, row in enumerate(rows):
        for x in range(len(row)):
            at = ((y // 16) * tiles * 2 + (y % 16 // 8) * tiles + x // 8) * 16 + y % 8 * 2
            row[x] = (raw[at] >> (7 - x % 8) & 1) | ((raw[at + 1] >> (7 - x % 8) & 1) << 1)
    return rows


def pack(rows, tiles, lines=1, align='left'):
    canvas = [[0] * (tiles * 8) for _ in range(lines * 16)]
    for line in range(lines):
        source = rows[line * 16:(line + 1) * 16]
        width = len(source[0]) if source else 0
        if width > tiles * 8:
            raise ValueError(f'Text needs {width} pixels; this field has {tiles * 8}.')
        shift = tiles * 8 - width if align == 'right' else (tiles * 8 - width) // 2 if align == 'center' else 0
        for y, row in enumerate(source):
            canvas[line * 16 + y][shift:shift + len(row)] = row
    return b''.join(tile_bytes(canvas, x, line * 2 + y)
                    for line in range(lines) for y in range(2) for x in range(tiles))


class MenuFont:
    """Render and recognize text with the actual variable-width ROM font.

    Recognition matches complete foreground columns, not a guessed translation
    or a static list. Artwork which cannot be recognized stays visible and is
    explicitly reported as such. Merely opening/writing unchanged text is a no-op.
    """
    def __init__(self, rom):
        self.rom = rom
        self.snapshot = [(0x119971, read(rom, 0x119971, 0xB0)),
                         (0x128000, read(rom, 0x128000, 0x3000))]
        self.glyphs = {}
        for code, char in GLYPHS.items():
            if not (0x10 <= code <= 0xA5 and len(char) == 1):
                continue
            width = read(rom, 0x119961 + code, 1)[0]
            if not 1 <= width <= 16:
                continue
            index = code - 0x10
            tile = index // 8 * 32 + index % 8 * 2
            rows = []
            for y in range(16):
                row = []
                for x in range(16):
                    at = 0x128000 + (tile + y // 8 * 16 + x // 8) * 16 + y % 8 * 2
                    low, high = read(rom, at, 2)
                    row.append((low >> (7 - x % 8) & 1) | ((high >> (7 - x % 8) & 1) << 1))
                rows.append(row)
            if any(2 in row for row in rows):
                self.glyphs[char] = (width, rows, code)
        if 'A' not in self.glyphs:
            raise ValueError('The ROM menu font is not recognized.')
        self.space = read(rom, 0x119A20, 1)[0]
        if not 1 <= self.space <= 16:
            raise ValueError('The ROM space width is not recognized.')
        self.templates = []
        for char, (width, rows, _) in self.glyphs.items():
            columns = tuple(sum((rows[y][x] == 2) << y for y in range(16)) for x in range(width))
            if any(columns):
                self.templates.append((char, width, columns))

    def normalize(self, text):
        return ''.join(ALIASES.get(c, c) for c in text.replace('\r\n', '\n'))

    def render_line(self, text, limit=None):
        text = self.normalize(text)
        widths = []
        total = 1 if text else 0
        for char in text:
            if char == ' ':
                width = self.space
            elif char in self.glyphs:
                width = self.glyphs[char][0]
            else:
                raise ValueError(f'{char!r} is not available in this ROM’s menu font.')
            total += width
            if limit is not None and total > limit:
                raise ValueError(f'Text exceeds the {limit}-pixel line limit.')
            widths.append(width)
        rows = [[0] * (sum(widths) + (1 if text else 0)) for _ in range(16)]
        cursor = 0
        for char, width in zip(text, widths):
            if char != ' ':
                glyph = self.glyphs[char][1]
                for y in range(16):
                    for x in range(min(width + 1, 16, len(rows[0]) - cursor)):
                        pixel = glyph[y][x]
                        if pixel and (not rows[y][cursor + x] or pixel == 2):
                            rows[y][cursor + x] = pixel
            cursor += width
        return rows

    def recognize_line(self, rows):
        columns = tuple(sum((rows[y][x] == 2) << y for y in range(16)) for x in range(len(rows[0])))
        end = len(columns)
        while end and not columns[end - 1]:
            end -= 1
        if not end:
            return '' if not any(any(row) for row in rows) else None

        @lru_cache(None)
        def visit(x):
            if x >= end:
                return ''
            for char, width, template in self.templates:
                if columns[x:x + width] == template:
                    tail = visit(x + width)
                    if tail is not None:
                        return char + tail
            # Some original artwork uses custom-width spacing/justification.
            # Match blank columns without inventing visible characters.
            stop = x
            while stop < end and columns[stop] == 0:
                stop += 1
            if stop > x:
                for gap in range(stop - x, 0, -1):
                    tail = visit(x + gap)
                    if tail is not None:
                        return ' ' + tail
            return None

        text = visit(0)
        return text.strip() if text is not None else None

    def recognize(self, rows):
        lines = [self.recognize_line(rows[i:i + 16]) for i in range(0, len(rows), 16)]
        return None if None in lines else '\n'.join(lines).rstrip('\n')

    def encode(self, text):
        return bytes(0xBF if c == ' ' else self.glyphs[c][2] for c in self.normalize(text))


def check_profile(rom):
    if len(rom.data) - rom.header != 0x800000 or read(rom, 0x484FF, 4) != bytes.fromhex('22 00 0C 51'):
        raise ValueError('Menu text editing requires the supported 8 MiB Project Naga beta 7 layout.')


@dataclass
class Artwork:
    pointer_at: int
    count_at: int | None
    pointer: int
    tiles: int
    lines: int
    align: str
    raw: bytes


class MenuText:
    def __init__(self, rom, entry, font=None):
        check_profile(rom)
        self.rom, self.entry = rom, entry
        self.font = font or MenuFont(rom)
        self.snapshot = list(self.font.snapshot)
        self.artwork = []
        kind = entry['kind']
        if kind == 'encoded':
            raw = read(rom, entry['address'], 16)
            self.snapshot.append((entry['address'], raw))
            end = raw.find(b'\x01')
            if end < 0 or any(value not in GLYPHS for value in raw[:end]):
                raise ValueError('This message name uses an unsupported text encoding.')
            self.text = ''.join(GLYPHS[value] for value in raw[:end])
            self.capacity = 1
            self.original_rows = self.font.render_line(self.text)
            self.recognition = 'Stored message text'
            return
        if kind in ('name', 'description'):
            self.snapshot.append((entry['table'], read(rom, entry['table'], 16)))
            for count_offset, pointer_offset, align in entry['variants']:
                count_at = entry['table'] + count_offset
                count = read(rom, count_at, 1)[0]
                if kind == 'description':
                    if count not in (16, 48):
                        raise ValueError('This item description uses an unsupported line layout.')
                    tiles, lines = 16, count // 16
                else:
                    if not 1 <= count <= 8:
                        raise ValueError('Menu name width is outside the supported 1–8 tile range.')
                    tiles, lines = count, 1
                self.add_artwork(entry['table'] + pointer_offset, count_at, tiles, lines, align)
        elif kind == 'skill':
            self.snapshot.append((entry['pointer'], read(rom, entry['pointer'], 3)))
            self.add_artwork(entry['pointer'], None, 16, 4, 'left')
        else:
            raw = read(rom, entry['graphics'], 512)
            self.artwork.append(Artwork(0, None, entry['graphics'], 16, 1, 'left', raw))
            self.snapshot.append((entry['graphics'], raw))
        self.original_rows = unpack(self.artwork[0].raw, self.artwork[0].tiles, self.artwork[0].lines)
        self.text = self.font.recognize(self.original_rows)
        self.capacity = self.artwork[0].lines
        self.recognition = 'ROM font'
        hint = reference_hints().get(str(entry['key']))
        if hint and hashlib.sha256(self.artwork[0].raw).hexdigest() == hint['sha256']:
            self.text, self.recognition = hint['text'], 'Verified reference artwork'
        saved = private_text(self)
        if saved is not None:
            self.text, self.recognition = saved, 'Saved menu text'

    def add_artwork(self, at, count_at, tiles, lines, align):
        pointer = int.from_bytes(read(self.rom, at, 3), 'little')
        low, high = self.entry['pool']
        if not (low <= pointer and pointer + tiles * lines * 32 <= high or
                ARENA + START <= pointer and pointer + tiles * lines * 32 <= ARENA + SIZE):
            raise ValueError('Text artwork was relocated outside its supported storage.')
        if pointer >> 16 != (pointer + tiles * lines * 32 - 1) >> 16:
            raise ValueError('Text artwork crosses a ROM bank boundary.')
        raw = read(self.rom, pointer, tiles * lines * 32)
        self.artwork.append(Artwork(at, count_at, pointer, tiles, lines, align, raw))
        self.snapshot.append((pointer, raw))

    def render(self, text):
        text = self.font.normalize(text)
        lines = text.split('\n')
        if len(lines) > self.capacity:
            raise ValueError(f'This entry has room for {self.capacity} line(s).')
        if self.entry['kind'] in ('name', 'skill', 'encoded') and not lines[0].strip():
            raise ValueError('Enter a name on the first line.')
        if self.entry['kind'] == 'encoded' and len(self.font.encode(text)) > 15:
            raise ValueError('This message name has room for 15 characters.')
        rows = []
        widths = []
        for i, line in enumerate(lines + [''] * (self.capacity - len(lines))):
            limit = 56 if self.entry['kind'] == 'skill' and i == 0 else 64 if self.entry['kind'] == 'name' else 128
            try:
                rendered = self.font.render_line(line, limit)
            except ValueError as error:
                raise ValueError(f'Line {i + 1}: {error}') from error
            widths.append(len(rendered[0]))
            rows.extend(rendered)
        width = max(widths)
        rows = [row + [0] * (width - len(row)) for row in rows]
        return text, rows, widths

    def plan(self, text):
        if any(read(self.rom, at, len(raw)) != raw for at, raw in self.snapshot):
            raise ValueError('This text or its font changed in another editor. Reload before writing.')
        text = self.font.normalize(text)
        if text == self.text:
            return self.original_rows, []
        text, rows, widths = self.render(text)
        kind = self.entry['kind']
        if kind == 'encoded':
            return rows, [(self.entry['address'], (self.font.encode(text) + b'\x01').ljust(16, b'\0'))]
        if kind == 'effect':
            raw = pack(rows, 16)
            _, pool_edit = allocate(self.rom, self.entry['key'], raw + text_record(text))
            return rows, [pool_edit, (self.entry['graphics'], raw)]
        payload = bytearray()
        updates = []
        for art in self.artwork:
            tiles = max(1, (widths[0] + 7) // 8) if kind == 'name' and art.align != 'center' else 8 if kind == 'name' else 16
            raw = pack(rows, tiles, art.lines, art.align)
            updates.append((art.pointer_at, art.count_at, len(payload), tiles * art.lines))
            payload += raw
        address, pool_edit = allocate(self.rom, self.entry['key'], bytes(payload) + text_record(text))
        edits = [pool_edit]
        for pointer_at, count_at, offset, count in updates:
            edits.append((pointer_at, (address + offset).to_bytes(3, 'little')))
            if count_at is not None:
                edits.append((count_at, bytes([count])))
        if kind == 'skill':
            edits += skill_menu_plan(self.rom, self.entry['slot'], self.font.render_line(text.split('\n')[0]))
        return rows, edits

    def write(self, text):
        rows, edits = self.plan(text)
        for at, raw in edits:
            self.rom.data[at + self.rom.header:at + self.rom.header + len(raw)] = raw
        return bool(edits)


def pool_digest(block):
    return hashlib.sha256(block[:64] + block[96:]).digest()


def text_record(text):
    raw = text.encode('utf-8')
    return b'TXT1' + len(raw).to_bytes(2, 'little') + raw


def private_text(model):
    rom, entry = model.rom, model.entry
    private = any(ARENA <= a.pointer < ARENA + SIZE for a in model.artwork)
    if read(rom, ARENA, 16) != MAGIC:
        if private:
            raise ValueError('A menu pointer has no valid private storage directory.')
        return None
    block = read(rom, ARENA, SIZE)
    fingerprint = catalogue_fingerprint()
    if block[16:32] != fingerprint or block[64:96] != pool_digest(block):
        raise ValueError('Private menu text storage failed its integrity check.')
    at = 128 + entry['key'] * 8
    offset, size = int.from_bytes(block[at:at + 4], 'little'), int.from_bytes(block[at + 4:at + 8], 'little')
    if not offset and not size:
        if private:
            raise ValueError('A menu pointer has no matching private allocation.')
        return None
    if not START <= offset < offset + size <= SIZE:
        raise ValueError('Invalid saved menu text allocation.')
    payload = block[offset:offset + size]
    cursor = 0
    for art in model.artwork:
        if entry['kind'] != 'effect' and art.pointer != ARENA + offset + cursor:
            raise ValueError('A menu pointer no longer matches its saved text.')
        if payload[cursor:cursor + len(art.raw)] != art.raw:
            # Fixed effect artwork can also be changed by a separate ROM tool.
            if entry['kind'] == 'effect':
                return None
            raise ValueError('Saved menu artwork no longer matches its text.')
        cursor += len(art.raw)
    record = payload[cursor:]
    if len(record) < 6 or record[:4] != b'TXT1' or int.from_bytes(record[4:6], 'little') != len(record) - 6:
        raise ValueError('Invalid saved menu text record.')
    try:
        return record[6:].decode('utf-8')
    except UnicodeError as error:
        raise ValueError('Saved menu text is not valid UTF-8.') from error


def allocate(rom, key, payload):
    entries = catalogue()['entries']
    fingerprint = catalogue_fingerprint()
    block = bytearray(read(rom, ARENA, SIZE))
    if block[:16] == MAGIC:
        if block[16:32] != fingerprint or block[32] not in (0, 255) or block[64:96] != pool_digest(block):
            raise ValueError('Private menu text storage failed its integrity check. Restore a backup.')
    else:
        if len(set(block)) != 1 or block[0] not in (0, 255):
            raise ValueError('The reserved menu text area contains other data. No text was changed.')
        fill = block[0]
        block[:START] = bytes(START)
        block[:16], block[16:32], block[32] = MAGIC, fingerprint, fill
    if len(entries) > MAX_ENTRIES or not 0 <= key < len(entries):
        raise ValueError('Menu text catalogue is too large or inconsistent.')
    used = []
    for i in range(len(entries)):
        at = 128 + i * 8
        offset, size = int.from_bytes(block[at:at + 4], 'little'), int.from_bytes(block[at + 4:at + 8], 'little')
        if not offset and not size:
            continue
        if not START <= offset < offset + size <= SIZE or (ARENA + offset) >> 16 != (ARENA + offset + size - 1) >> 16:
            raise ValueError('Invalid menu text allocation.')
        used.append((offset, offset + size, i))
    used.sort()
    if any(a[1] > b[0] for a, b in zip(used, used[1:])):
        raise ValueError('Private menu text allocations overlap.')
    own = next((a for a in used if a[2] == key), None)
    # Verify every private pointer before reclaiming an old allocation. Other
    # text editors may have deliberately introduced aliases or interior refs.
    for entry in entries:
        for pointer_at in pointer_fields(entry):
            pointer = int.from_bytes(read(rom, pointer_at, 3), 'little')
            if not ARENA <= pointer < ARENA + SIZE:
                continue
            owner = next((a for a in used if ARENA + a[0] <= pointer < ARENA + a[1]), None)
            if owner is None or owner[2] != entry['key']:
                raise ValueError('A private menu pointer is shared or no longer matches its allocation. Reload/restore before writing.')
    other = [a for a in used if a[2] != key]
    chosen = None
    for bank in range(5):
        low, high = max(START, bank * 0x10000), (bank + 1) * 0x10000
        cursor = low
        for begin, end, _ in other + [(high, high, -1)]:
            if end <= low:
                continue
            begin = min(begin, high)
            if begin - cursor >= len(payload):
                chosen = cursor
                break
            cursor = max(cursor, end)
            if cursor >= high:
                break
        if chosen is not None:
            break
    if chosen is None:
        raise ValueError('Private menu text storage is full. Shorten text or restore a backup.')
    if own:
        block[own[0]:own[1]] = bytes([block[32]]) * (own[1] - own[0])
    block[chosen:chosen + len(payload)] = payload
    at = 128 + key * 8
    block[at:at + 8] = chosen.to_bytes(4, 'little') + len(payload).to_bytes(4, 'little')
    block[64:96] = pool_digest(block)
    return ARENA + chosen, (ARENA, bytes(block))


def pointer_fields(entry):
    if entry['kind'] in ('name', 'description'):
        return [entry['table'] + v[1] for v in entry['variants']]
    return [entry['pointer']] if entry['kind'] == 'skill' else []


def skill_menu_plan(rom, selected, rows):
    """Repack only the skill-name tiles; retain headings and type labels."""
    tables = read(rom, 0x507A00, 18 * 32)
    original = read(rom, 0x450000, 0x1000)
    graphics = bytearray(original)
    names = []
    for i in range(18):
        values = [int.from_bytes(tables[i * 32 + j:i * 32 + j + 2], 'big') for j in range(0, 14, 2)]
        tiles = [v - 0x100 for v in values if v not in (0x8140, 0)]
        allowed = set(range(0x20, 0x30)) | set(range(0x40, 0x50)) | set(range(0x60, 0x70)) | set(range(0x80, 0x90)) | set(range(0xA0, 0xAA)) | set(range(0xE0, 0xF0))
        if not tiles or len(tiles) > 7 or any(t not in allowed for t in tiles):
            raise ValueError('The compact skill-name tilemap is not recognized.')
        raw = b''.join(original[(t + y * 16) * 16:(t + y * 16 + 1) * 16] for y in range(2) for t in tiles)
        names.append((tiles, raw))
    occupied = {t for tiles, _ in names for t in tiles}
    extra = all(t in occupied or not any(original[t * 16:(t + 1) * 16] + original[(t + 16) * 16:(t + 17) * 16]) for t in range(0xE0, 0xF0))
    slots = [t for low, high in ((0x20, 0x30), (0x40, 0x50), (0x60, 0x70), (0x80, 0x90), (0xA0, 0xAA)) for t in range(low, high)]
    if extra:
        slots += list(range(0xE0, 0xF0))
    widths = [len(t) for t, _ in names]
    widths[selected] = max(1, (len(rows[0]) + 7) // 8)
    if sum(widths) > len(slots):
        raise ValueError('The compact Skills menu has no room for this name. Shorten it.')
    edits, cursor = [], 0
    for i, width in enumerate(widths):
        tilemap = bytearray(b'\x81\x40' * 7)
        for column in range(width):
            target = slots[cursor + column]
            tilemap[column * 2:column * 2 + 2] = (0x100 + target).to_bytes(2, 'big')
            for y in range(2):
                raw = tile_bytes(rows, column, y) if i == selected else names[i][1][(y * width + column) * 16:(y * width + column + 1) * 16]
                at = (target + y * 16) * 16
                graphics[at:at + 16] = raw
        edits.append((0x507A00 + i * 32, bytes(tilemap)))
        cursor += width
    return edits + [(0x450000, bytes(graphics))]


def name_labels(rom, category):
    """Live dropdown/list labels, cached against tables, artwork and font data."""
    try:
        check_profile(rom)
    except ValueError:
        return {}
    if category == 'Item names':
        table, count, pool, size = 0x504000, 138, 0x572000, 0xE000
    elif category == 'Class names':
        table, count, pool, size = 0x502400, 72, 0x568000, 0x9000
    else:
        return {}
    stamp = hashlib.sha256(read(rom, table, count * 16) + read(rom, pool, size) +
                           read(rom, ARENA + 64, 32) + read(rom, 0x119971, 0xB0) +
                           read(rom, 0x128000, 0x3000)).digest()
    cache = getattr(rom, '_menu_name_cache', {})
    if category not in cache or cache[category][0] != stamp:
        try:
            font = MenuFont(rom)
        except ValueError:
            return {}
        labels = {}
        for entry in catalogue()['entries']:
            if entry['category'] != category:
                continue
            try:
                model = MenuText(rom, entry, font)
                if model.text is not None:
                    labels[entry['id']] = model.text
            except ValueError:
                continue
        cache[category] = stamp, labels
        rom._menu_name_cache = cache
    return cache[category][1]
