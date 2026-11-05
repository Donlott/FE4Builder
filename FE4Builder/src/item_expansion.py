"""Optional byte-ID item expansion for the supported Project Naga ExHiROM.

IDs never move. FF remains Nothing; player ID 00 remains reserved. The native
item bank holds copy-on-write records, while presentation tables live in a
guarded private arena. Every new save uses 254 item records, including disabled
IDs, so changing the enabled set does not change the save format again.
"""
from functools import wraps
import hashlib

from growth_patch import Assembler

BASE_ITEMS = 138
MAX_ITEMS = 255
MAX_SLOTS = 254
ARENA = 0x7E8000
SIZE = 0x5000                    # mapped through CPU 3E8000, never WRAM bank 7E
MAGIC = b'FE4BITEMSv1'.ljust(16, b'\0')
CODE = ARENA + 0x400
POINTERS = ARENA + 0x1000
DONORS = ARENA + 0x1200
ORIGINS = ARENA + 0x1300
ICONS = ARENA + 0x1400
STATUS_ICONS = ARENA + 0x1600
HELD = ARENA + 0x1800
PLAYERS = ARENA + 0x1A00
SLOT_FLAGS = ARENA + 0x1C00
NAMES = ARENA + 0x2000
DESCRIPTIONS = ARENA + 0x3000
MESSAGES = ARENA + 0x4000
OLD_POINTERS = 0x3E9D0
OLD_PLAYERS = 0x3F489
RECORD_REGIONS = ((0x3F7C4, 0x40000), (OLD_POINTERS, OLD_POINTERS + BASE_ITEMS * 2))
ITEM_MODULE = 'FE4 Expanded Item Editor'
PLAYER_MODULE = 'FE4 Player Weapon Editor'


def read(rom, at, size):
    if not 0 <= at <= at + size <= len(rom.data) - rom.header:
        raise ValueError('Expanded item data points outside the ROM.')
    return bytes(rom.data[at + rom.header:at + rom.header + size])


def cpu_address(pc):
    """The last ExHiROM banks' upper halves use low-bank ROM aliases."""
    return pc - 0x400000 if ARENA <= pc < ARENA + SIZE else pc


def put(rom, at, raw):
    rom.data[at + rom.header:at + rom.header + len(raw)] = raw


def update_checksum(rom):
    for at in (0xFFDC, 0x40FFDC):put(rom, at, bytes.fromhex('FF FF 00 00'))
    checksum = sum(rom.data[rom.header:]) & 65535
    raw = (checksum ^ 65535).to_bytes(2, 'little') + checksum.to_bytes(2, 'little')
    for at in (0xFFDC, 0x40FFDC):put(rom, at, raw)


def installed(rom):
    return read(rom, ARENA, 16) == MAGIC if len(rom.data) - rom.header >= ARENA + SIZE else False


def enabled(rom, kind):
    if installed(rom):
        at, first, stop = (0x80, 0, MAX_ITEMS) if kind == 'items' else (0xA0, 1, MAX_SLOTS + 1)
        bits = int.from_bytes(read(rom, ARENA + at, 32), 'little')
        return [i for i in range(first, stop) if bits >> i & 1]
    if kind == 'items':return list(range(BASE_ITEMS))
    # The original table has a two-byte sentinel, not two extra usable slots.
    raw = read(rom, OLD_PLAYERS, 256)
    count = raw.find(b'\xff\xff')
    return list(range(1, min(142 if count <= 0 else count, MAX_SLOTS) + 1))


def table(rom, kind):
    return ({'players': PLAYERS, 'icons': ICONS, 'status_icons': STATUS_ICONS,
             'held': HELD}[kind] if installed(rom) else
            {'players': OLD_PLAYERS, 'icons': 0xD1AE, 'status_icons': 0xBBED5,
             'held': 0x198725}[kind])


def item_pointer(rom, item):
    if item not in enabled(rom, 'items'):raise ValueError(f'Item {item:02X} is disabled.')
    if installed(rom):return 0x30000 + int.from_bytes(read(rom, POINTERS + item * 2, 2), 'little')
    return OLD_POINTERS + int.from_bytes(read(rom, OLD_POINTERS + item * 2, 2), 'little')


def record(rom, item):
    at = item_pointer(rom, item)
    return read(rom, at, 10 if read(rom, at + 1, 1) == b'\x02' else 19)


def digest(block):
    # Other editors own the icon, text and sprite fields. Their ordinary writes
    # must not invalidate our immutable code/directory integrity check.
    return hashlib.sha256(block[:32] + block[64:0x1200]).digest()


def atomic(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        before = bytes(self.rom.data)
        try:return method(self, *args, **kwargs)
        except Exception:
            self.rom.data[:] = before
            self.__init__(self.rom)
            raise
    return run


def program():
    class ItemAssembler(Assembler):
        def long(self, value):super().long(cpu_address(value))
    a = ItemAssembler()
    a.mark('pointer')
    a.emit('DA C9 FF 00');a.branch('B0', 'no_pointer')
    a.emit('0A AA BF');a.long(POINTERS);a.emit('FA 6B')
    a.mark('no_pointer');a.emit('A9 00 00 FA 6B')
    a.mark('get_pointer');a.emit('08')
    a.call(CODE + a.labels['pointer']);a.emit('8F 83 05 00 28 6B')
    # The only native caller of the short pointer helper compares holy-weapon
    # identities to select a blood requirement. Added holy items inherit their
    # source's requirement while retaining their independent stats and name.
    a.mark('holy_pointer');a.emit('C9 8A 00');a.branch('B0', 'holy_plain')
    a.emit('48 DA A2 14 01')
    a.mark('holy_scan');a.emit('BF');a.long(POINTERS)
    a.emit('CF 83 05 00');a.branch('F0', 'holy_match')
    a.emit('E8 E8 E0 FE 01');a.branch('90', 'holy_scan')
    a.mark('holy_fallback');a.emit('FA 68')
    a.mark('holy_plain');a.emit('5C');a.long(CODE + a.labels['pointer'])
    a.mark('holy_match');a.emit('8A 4A AA BF');a.long(ORIGINS)
    a.emit('29 FF 00 C3 03');a.branch('D0', 'holy_fallback')
    a.emit('AF 83 05 00 83 03 FA 68 6B')
    a.mark('inheritance');a.call(0x87E088)
    a.emit('C9 8A 00');a.branch('90', 'inheritance_return')
    a.emit('C9 FF 00');a.branch('B0', 'inheritance_return')
    a.emit('DA AA BF');a.long(ORIGINS);a.emit('29 FF 00 FA')
    a.mark('inheritance_return');a.emit('6B')
    a.mark('sanitize_slots');a.emit('08 C2 30 48 DA 5A A2 00 00 A0 01 00')
    a.mark('sanitize_loop');a.emit('DA 98 AA BF');a.long(SLOT_FLAGS)
    a.emit('29 FF 00 FA 09 00 00');a.branch('D0', 'sanitize_next')
    a.emit('A9 07 00 9F 8D 3D 7E A9 00 00 9F 8E 3D 7E')
    a.mark('sanitize_next');a.emit('8A 18 69 06 00 AA C8 C0 FF 00');a.branch('90', 'sanitize_loop')
    a.emit('7A FA 68 28 6B')
    a.mark('alias');a.emit('C9 FF 00');a.branch('B0', 'alias_return')
    a.emit('DA 48 AA BF');a.long(DONORS)
    a.emit('29 FF 00 C9 FF 00');a.branch('F0', 'alias_original')
    a.emit('83 01')
    a.mark('alias_original');a.emit('68 FA')
    a.mark('alias_return');a.emit('6B')
    a.mark('style');a.call(CODE + a.labels['alias'])
    a.emit('DA 1A C9 7F 00 5C');a.long(0x95A1F2)
    a.mark('effect');a.emit('BD 52 0D');a.call(CODE + a.labels['alias'])
    a.emit('48 5C');a.long(0x96DC8E)
    a.mark('map');a.emit('DA 5A');a.call(CODE + a.labels['alias'])
    a.emit('C9 FF FF 5C');a.long(0x9E8E06)
    for offset in range(3):
        label = f'name{offset}';a.mark(label);a.emit('08')
        a.emit('E0 A0 48');a.branch('90', label + '_native')
        a.emit('E0 F0 4F');a.branch('B0', label + '_native')
        a.emit('BF');a.long(cpu_address(NAMES) - 0x4000 + offset);a.branch('80',label + '_done')
        a.mark(label + '_native');a.emit('BF');a.long(0x500000 + offset)
        a.mark(label + '_done');a.emit('28 09 00 00 6B')
    for offset in range(3):
        label = f'description{offset}';a.mark(label);a.emit('08')
        a.emit('E0 A0 08');a.branch('90', label + '_native')
        a.emit('BF');a.long(DESCRIPTIONS + offset);a.branch('80', label + '_done')
        a.mark(label + '_native');a.emit('BF');a.long(0x507000 + offset)
        a.mark(label + '_done')
        if offset == 0:a.emit('29 FF 00')
        a.emit('28 09 00 00 6B')
    a.mark('message')
    a.emit('AD B1 18 C9 8A 00');a.branch('90', 'message_native')
    a.emit('C9 FF 00');a.branch('B0', 'message_empty')
    a.emit('0A 0A 0A 0A 18 69');a.word(MESSAGES & 0xFFFF)
    a.emit('48 A9');a.word((cpu_address(MESSAGES) >> 16) << 8)
    a.emit('85 25 68 85 24');a.branch('80','message_push')
    a.mark('message_empty');a.emit('A9 00 00')
    a.mark('message_native')
    a.emit('C9 89 00');a.branch('90', 'message_index')
    a.emit('A9 00 00')
    a.mark('message_index');a.emit('0A AA A9 00 50 85 25 BF 02 94 8D 85 24')
    a.mark('message_push');a.call(0x918E6E);a.emit('6B')
    code = a.finish()
    if len(code) > 0xC00:raise ValueError('Expanded item code exceeds its reservation.')
    labels = {name: cpu_address(CODE + offset) for name, offset in a.labels.items()}
    hooks = {}
    def call(at, old, name, jump=False):
        old = bytes.fromhex(old)
        hooks[at] = old, bytes([0x5C if jump else 0x22]) + labels[name].to_bytes(3, 'little') + b'\xEA' * (len(old) - 4)
    call(0x7E31D, '8B 08 4B AB', 'get_pointer', True)
    # This JSR helper must not overwrite the equipped item's pointer: holy
    # weapon eligibility compares the returned pointer against that value.
    hooks[0x4F6A8] = bytes.fromhex('DA 0A 18 6F 10'), b'\x22' + labels['holy_pointer'].to_bytes(3, 'little') + b'\x60'
    call(0x7AB51, '22 88 E0 87', 'inheritance')
    call(0x15A1ED, 'DA 1A C9 7F 00', 'style', True)
    call(0x16DC8A, 'BD 52 0D 48', 'effect', True)
    call(0x1E8E01, 'DA 5A C9 FF FF', 'map', True)
    for at, offset in ((0x511321, 0), (0x511332, 2), (0x511338, 1),
                       (0x511365, 0), (0x511374, 1), (0x51137C, 2)):
        call(at, 'BF ' + (0x500000 + offset).to_bytes(3, 'little').hex(' '), f'name{offset}')
    for at in (0x51231D, 0x51271A, 0x512912, 0x512A18, 0x51341D):
        call(at, 'BF 00 70 50', 'description0')
        # Two pointer words are read in opposite orders on different screens.
        for location, offset in ((at + 7, 1), (at + 13, 2)) if at in (0x51231D, 0x51271A, 0x51341D) else ((at + 11, 2), (at + 18, 1)):
            call(location, 'BF ' + (0x507000 + offset).to_bytes(3, 'little').hex(' '), f'description{offset}')
    call(0x118DF1, 'A2 00 50 86 25 AD', 'message')
    # The replacement is a complete JSR routine, not a fallthrough into the
    # middle of the displaced instruction stream.
    old, new = hooks[0x118DF1];hooks[0x118DF1] = old, new[:4] + b'\x18\x60'
    for at, old, new in ((0x480D0, 'A9 00 83', b'\xA9' + ((cpu_address(PLAYERS) >> 16) << 8).to_bytes(2, 'little')),
                         (0x480D6, 'A9 89 F4', b'\xA9' + (PLAYERS & 65535).to_bytes(2, 'little')),
                         (0xD187, 'BF AE D1 80', b'\xBF' + cpu_address(ICONS).to_bytes(3, 'little')),
                         (0xBBEA3, 'BF D5 BE 8B', b'\xBF' + cpu_address(STATUS_ICONS).to_bytes(3, 'little')),
                         (0x1586BB, 'BF 25 87 99', b'\xBF' + cpu_address(HELD).to_bytes(3, 'little'))):
        hooks[at] = bytes.fromhex(old), new
    for at in (0x11F2DB, 0x11F31B, 0x11F345):
        hooks[at] = bytes.fromhex('C9 91 00'), bytes.fromhex('C9 FF 00')
    for at in (0x11EA0B, 0x11EA9B, 0x11F2E7, 0x11F619):
        hooks[at] = bytes.fromhex('C9 07 92'), bytes.fromhex('C9 08 92')
    hooks[0x11EECF] = bytes.fromhex('A9 07 92'), bytes.fromhex('A9 08 92')
    hooks[0x11EA10] = bytes.fromhex('C9 06 12'), bytes.fromhex('C9 08 92')
    # New-format loads finish here. The following four displaced bytes belong
    # to the obsolete save-ID remapper, which the new magic never selects.
    hooks[0x11F34A] = bytes.fromhex('60 8D 27 1B AA'), b'\x22' + labels['sanitize_slots'].to_bytes(3, 'little') + b'\x60'
    return code, hooks, labels


def text_entries():
    entries = []
    for item in range(BASE_ITEMS, MAX_ITEMS):
        common = dict(id=item, expanded_item=item)
        entries += [dict(common, key=710 + len(entries), category='Item names', kind='name', table=NAMES + item * 16,
                         pool=[0x572000, 0x580000], variants=[[0, 1, 'left'], [4, 5, 'right']])]
        entries += [dict(common, key=710 + len(entries), category='Item descriptions', kind='description', table=DESCRIPTIONS + item * 16,
                         pool=[0x5A0000, 0x5B0000], variants=[[0, 1, 'left']])]
        entries += [dict(common, key=710 + len(entries), category='Item names — messages', kind='encoded', address=MESSAGES + item * 16)]
    return entries


def entry_available(rom, entry):
    return 'expanded_item' not in entry or entry['expanded_item'] in enabled(rom, 'items')


class ItemExpansion:
    def __init__(self, rom):
        self.rom, self.snapshot = rom, bytes(rom.data)
        self.installed = installed(rom)
        self.items, self.slots = enabled(rom, 'items'), enabled(rom, 'slots')
        self.code, self.hooks, self.labels = program()
        if self.installed:
            self.block = bytearray(read(rom, ARENA, SIZE))
            b = self.block
            if b[17] != 1 or b[16] not in (0, 255) or b[32:64] != digest(b) or b[0x400:0x400 + len(self.code)] != self.code:
                raise ValueError('Expanded item storage failed its integrity check. Restore a backup.')
            self.verify_hooks()
            if self.items[:BASE_ITEMS] != list(range(BASE_ITEMS)) or any(i not in self.slots for i in range(1, int.from_bytes(b[18:20], 'little') + 1)):
                raise ValueError('Original item or player slot IDs are missing from the expansion.')
            if b[0x9F] & 0x80 or b[0xA0] & 1 or b[0xBF] & 0x80:
                raise ValueError('Reserved item or player slot IDs were enabled.')
            if read(rom, SLOT_FLAGS, 256) != bytes(int(i in self.slots) for i in range(256)):
                raise ValueError('Expanded slot flags disagree with the enabled IDs.')
            if any(b[0x1300+i] >= BASE_ITEMS for i in self.items):
                raise ValueError('Expanded item blood/inheritance templates are invalid.')
        else:self.block = None
        self.records = {i: record(rom, i) for i in self.items}
        self.assignments = {i: read(rom, table(rom, 'players') + i - 1, 1)[0] for i in self.slots}
        if self.installed and any(i not in self.items for i in self.assignments.values()):
            raise ValueError('A player slot refers to a disabled item type.')

    def verify_hooks(self):
        for at, (_, new) in self.hooks.items():
            if read(self.rom, at, len(new)) != new:
                raise ValueError(f'Expanded item code changed at PC {at:06X}. Restore a backup.')

    def require_current(self):
        if bytes(self.rom.data) != self.snapshot:
            raise ValueError('The ROM changed. Reload the Item Editor before writing.')

    def install(self):
        self.require_current()
        if self.installed:return
        rom = self.rom
        if any(item not in self.items for item in self.assignments.values()):
            raise ValueError('The original player item table contains unsupported item IDs.')
        if len(rom.data) - rom.header != 0x800000 or read(rom, 0xFFD5, 1)[0] & 0x2F != 0x25:
            raise ValueError('Item expansion requires the supported 8 MiB Project Naga ExHiROM layout.')
        b = read(rom, ARENA, SIZE)
        if len(set(b)) != 1 or b[0] not in (0, 255):raise ValueError('Expanded item storage at PC 7E8000–7ECFFF is occupied.')
        padding = read(rom, RECORD_REGIONS[0][0], RECORD_REGIONS[0][1] - RECORD_REGIONS[0][0])
        if len(set(padding)) != 1 or padding[0] not in (0, 255):raise ValueError('The native-bank item record reservation contains custom data.')
        for item, raw in self.records.items():
            at = item_pointer(rom, item)
            if not 0x3EAE4 <= at < at + len(raw) <= OLD_PLAYERS:
                raise ValueError('Original item records were relocated outside the supported native layout.')
        # Validate independently-owned code before composing with it.
        from combat_art import CombatArtwork
        combat = CombatArtwork(rom)
        from menu_text import item_help_plan, ITEM_HELP_CALL, ITEM_HELP_READERS
        item_help_plan(rom)
        combat_hooks = combat.hooks
        for at, (old, _) in self.hooks.items():
            alternatives = [old]
            if combat.installed and at in combat_hooks:alternatives.append(combat_hooks[at][1])
            if at in ITEM_HELP_READERS:alternatives.append(ITEM_HELP_CALL)
            if read(rom, at, len(old)) not in alternatives:
                raise ValueError(f'Item expansion cannot replace custom code at PC {at:06X}.')
        before = bytes(rom.data)
        try:
            self.block = bytearray([b[0]]) * SIZE
            self.block[:0x400] = bytes(0x400)
            self.block[:16] = MAGIC;self.block[16:18] = bytes([b[0], 1])
            self.block[18:20] = len(self.slots).to_bytes(2, 'little')
            self.block[20] = padding[0]
            self.block[0x100:0x100 + 276] = read(rom, OLD_POINTERS, 276)
            self.block[0x220:0x220 + 142] = read(rom, OLD_PLAYERS, 142)
            self.block[0x400:0x400 + len(self.code)] = self.code
            self.block[0x1200:0x1300] = bytes(combat.aliases) + b'\xff' * (256 - len(combat.aliases))
            self.block[0x1300:0x1400] = bytes(range(BASE_ITEMS)) + b'\xff' * (256 - BASE_ITEMS)
            self.block[0x1400:0x1600] = read(rom, 0xD1AE, BASE_ITEMS * 2).ljust(512, b'\0')
            # Always derive status offsets from the same assignments.
            self.block[0x1600:0x1800] = b''.join((int.from_bytes(self.block[0x1400+i*2:0x1402+i*2], 'little') * 32).to_bytes(2, 'little') for i in range(256))
            self.block[0x1800:0x1A00] = read(rom, 0x198725, 125 * 2).ljust(512, b'\xff')
            self.installed = True
            self._pack()
            for at, (_, new) in self.hooks.items():put(rom, at, new)
            # Preserve the declared SRAM capacity used by the signed-stat fix.
            for at in (0xFFD8, 0x40FFD8):put(rom, at, bytes([max(5, read(rom, at, 1)[0])]))
            # New layout, new native magic. Old saves are not offered as usable
            # files, and unit-version branches still follow their current path.
            self.snapshot = bytes(rom.data)
        except Exception:
            rom.data[:] = before;self.__init__(rom);raise

    def _pack(self):
        rom, b = self.rom, self.block
        b[0x80:0xA0] = sum(1 << i for i in self.items).to_bytes(32, 'little')
        b[0xA0:0xC0] = sum(1 << i for i in self.slots).to_bytes(32, 'little')
        b[0x1000:0x1200] = bytes(512)
        original = b[0x100:0x100 + 276]
        for i in range(BASE_ITEMS):
            pointer = (OLD_POINTERS + int.from_bytes(original[i*2:i*2+2], 'little')) & 65535
            b[0x1000+i*2:0x1002+i*2] = pointer.to_bytes(2, 'little')
        # Rebuild the arena from live records: compaction and identical-record
        # sharing reclaim bytes without changing IDs. Native original records
        # keep their addresses (holy-weapon comparisons depend on them).
        put(rom, OLD_POINTERS, original)
        low, high = RECORD_REGIONS[0]
        put(rom, low, bytes([b[20]]) * (high - low))
        region, cursor, unique = 0, low, {}
        for item in sorted(i for i in self.items if i >= BASE_ITEMS):
            raw = self.records[item]
            key = (raw, b[0x1300+item] if raw[7] & 0x80 else None)
            if key not in unique:
                if cursor + len(raw) > RECORD_REGIONS[region][1]:
                    region += 1
                    if region >= len(RECORD_REGIONS):raise ValueError('Native-bank item storage is full.')
                    cursor = RECORD_REGIONS[region][0]
                unique[key] = cursor;put(rom, cursor, raw);cursor += len(raw)
            b[0x1000+item*2:0x1002+item*2] = (unique[key] & 65535).to_bytes(2, 'little')
        b[0x1A00:0x1B02] = bytes(254) + b'\xff\xff\0\0'
        for slot, item in self.assignments.items():b[0x1A00 + slot - 1] = item
        b[0x1C00:0x1D00] = bytes(int(i in self.slots) for i in range(256))
        b[32:64] = digest(b)
        put(rom, ARENA, b)

    @atomic
    def add_item(self, donor=0, item=None):
        self.require_current()
        if donor not in self.items:raise ValueError('Choose an enabled item to copy.')
        item = next((i for i in range(BASE_ITEMS, MAX_ITEMS) if i not in self.items), None) if item is None else item
        if item is None:raise ValueError('All 255 item type IDs are enabled.')
        if not BASE_ITEMS <= item < MAX_ITEMS or item in self.items:raise ValueError('Choose a disabled item ID from 8A through FE.')
        # Read source descriptors before enabling the new entry.
        name = self.records[donor][0]
        from menu_text import MenuText, storage_entries
        sources = {}
        for category in ('Item names', 'Item descriptions'):
            entry = next((e for e in storage_entries() if e['category'] == category and e['id'] == name), None)
            if entry is None:raise ValueError('The template item has no supported name/description descriptor.')
            sources[category] = MenuText(self.rom, entry)
        self.install()
        raw = bytearray(self.records[donor]);raw[0] = item
        self.records[item] = bytes(raw);self.items.append(item);self.items.sort()
        b = self.block
        b[0x1200 + item] = b[0x1200 + donor] if b[0x1200 + donor] != 255 else donor
        b[0x1300 + item] = b[0x1300 + donor]
        for base, size in ((0x1400, 2), (0x1600, 2), (0x1800, 2)):
            b[base+item*size:base+(item+1)*size] = b[base+donor*size:base+(donor+1)*size]
        self._pack()
        for entry in text_entries():
            if entry['id'] != item or entry['kind'] == 'encoded':continue
            source = sources[entry['category']]
            descriptor = bytearray(read(self.rom, source.entry['table'], 16))
            if any(0x5B0000 <= a.pointer < 0x600000 for a in source.artwork):
                from menu_text import allocate, text_record
                # Give private artwork its own allocation, so future text edits
                # and deletion can reclaim it without affecting the donor.
                text = source.text
                if text is None:raise ValueError('Recognize or name the copied private artwork before duplicating it.')
                payload = b''.join(a.raw for a in source.artwork) + text_record(text)
                address, edit = allocate(self.rom, entry['key'], payload)
                put(self.rom, *edit)
                offset = 0
                for art, (_, pointer_at, _) in zip(source.artwork, entry['variants']):
                    descriptor[pointer_at:pointer_at+3] = (address + offset).to_bytes(3, 'little');offset += len(art.raw)
            put(self.rom, entry['table'], descriptor)
        # Native message-name indices differ from menu IDs. Resolve the donor
        # through the actual ROM mapping, then store an independent byte string.
        if donor >= BASE_ITEMS:message = read(self.rom, MESSAGES + donor * 16, 16)
        else:
            pointer = int.from_bytes(read(self.rom, 0xD9402 + (donor if donor < 0x89 else 0) * 2, 2), 'little')
            message = read(self.rom, 0x500000 + pointer, 16)
        put(self.rom, MESSAGES + item * 16, message)
        self.__init__(self.rom)
        return item

    @atomic
    def add_slot(self, item=0, slot=None):
        self.require_current()
        if item not in self.items:raise ValueError('Assign an enabled item type to the new slot.')
        slot = next((i for i in range(1, MAX_SLOTS + 1) if i not in self.slots), None) if slot is None else slot
        if slot is None:raise ValueError('All 254 player item slot IDs are enabled.')
        if not 1 <= slot <= MAX_SLOTS or slot in self.slots:raise ValueError('Choose a disabled player slot ID from 01 through FE.')
        self.install();self.slots.append(slot);self.slots.sort();self.assignments[slot] = item
        self._pack();self.__init__(self.rom);return slot

    @atomic
    def write_record(self, item, raw, origin=None):
        self.require_current()
        if item not in self.items:raise ValueError('This item is disabled.')
        expected = 10 if raw[1] == 2 else 19
        if raw[1] not in (0, 1, 2):raise ValueError('Choose weapon, staff or ring as the item type.')
        if raw[1]!=2:
            from bonus_profiles import require_profile
            require_profile(self.rom,raw[5])
        if raw[0] not in self.items:raise ValueError('Choose an enabled item name/description ID.')
        if len(raw) != expected:raise ValueError('Item record size does not match its equipment type.')
        if origin is not None:
            if item < BASE_ITEMS or not 0 <= origin < BASE_ITEMS:
                raise ValueError('Choose an original item as the added item’s blood/inheritance template.')
            self.block[0x1300+item] = origin
        self.records[item] = bytes(raw)
        if item < BASE_ITEMS:
            if len(raw) != len(record(self.rom, item)):raise ValueError('Changing the record size of an original item is unsupported; add a new item instead.')
            put(self.rom, item_pointer(self.rom, item), raw)
        else:self._pack()
        self.__init__(self.rom)

    @atomic
    def assign(self, slot, item):
        self.require_current()
        if slot not in self.slots or item not in self.items:raise ValueError('Choose an enabled player slot and item.')
        self.assignments[slot] = item
        if self.installed:self._pack()
        else:put(self.rom, OLD_PLAYERS + slot - 1, bytes([item]))
        self.__init__(self.rom)

    def references(self, kind, value):
        if kind == 'slots':
            from player_items import SlotLocations
            return [row.title for row in SlotLocations(self.rom).rows[value] if row.kind != 'inheritance']
        result = [f'Player item slot {slot:02X}' for slot, item in self.assignments.items() if item == value]
        from rom import character_modules, category_modules
        for module in character_modules() + category_modules('Enemy Editor') + category_modules('Holy Character Editor'):
            for index in range(module.count):
                for field, stored in zip(module.fields, self.rom.values(module, index)):
                    if field.reference == 'FE4 Weapon List.txt' and stored == value:
                        result.append(f'{module.name}, record {index:02X}, {field.name}')
        result += [f'Item {item:02X} uses this name/description ID' for item, raw in self.records.items() if item != value and raw[0] == value]
        if self.installed:
            result += [f'Item {item:02X} uses these combat animations' for item in self.items if item != value and self.block[0x1200 + item] == value]
        return result

    @atomic
    def remove(self, kind, value):
        self.require_current()
        if kind not in ('items', 'slots'):raise ValueError('Choose items or player slots.')
        if not self.installed:raise ValueError('Only entries added with item expansion can be removed.')
        original_slots = int.from_bytes(self.block[18:20], 'little')
        if kind == 'items' and value < BASE_ITEMS or kind == 'slots' and value <= original_slots:
            raise ValueError('Original entries keep their IDs and cannot be removed.')
        values = self.items if kind == 'items' else self.slots
        if value not in values:raise ValueError('This entry is already disabled.')
        refs = self.references(kind, value)
        if refs:raise ValueError('Reassign or clear these references before removing the entry:\n' + '\n'.join(refs[:30]))
        values.remove(value)
        if kind == 'slots':del self.assignments[value]
        else:
            del self.records[value]
            for base, size in ((0x1200, 1), (0x1300, 1), (0x1400, 2), (0x1600, 2), (0x1800, 2), (0x2000, 16), (0x3000, 16), (0x4000, 16)):
                self.block[base+value*size:base+(value+1)*size] = bytes([255 if base in (0x1200, 0x1300, 0x1800) else 0]) * size
        self._pack()
        if kind == 'items':
            from menu_text import release
            for entry in text_entries():
                if entry['id'] == value:release(self.rom, entry['key'])
        self.__init__(self.rom)

    def sizes(self):
        unique = {(raw, self.block[0x1300+item] if raw[7] & 0x80 else None) for item, raw in self.records.items() if item >= BASE_ITEMS}
        return dict(items=len(self.items), slots=len(self.slots), record_bytes=sum(len(raw) for raw, _ in unique),
                    record_capacity=sum(high-low for low, high in RECORD_REGIONS),
                    save_item_bytes=(MAX_SLOTS * 25 + 7) // 8 if self.installed else 450,
                    fixed_patch_bytes=0x2000 if self.installed else 0)


def expanded_module(rom, item=None):
    """A module view for linked forms; writes use copy-on-write in Rom.write."""
    from rom import Module, MODULES, load_module
    fields = load_module(MODULES / 'Item Editors' / ('FE4 Ring Editor.nmm' if item is not None and record(rom, item)[1] == 2 else 'FE4 Weapon Editor.nmm')).fields
    addresses = [(item_pointer(rom, i) if i in enabled(rom, 'items') else 0) for i in range(MAX_ITEMS)]
    return Module(ITEM_MODULE, 0, MAX_ITEMS, len(record(rom, item)) if item is not None else 19,
                  [f'Item {i:02X}' for i in range(MAX_ITEMS)], fields, addresses)
