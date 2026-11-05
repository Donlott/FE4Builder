"""Optional six-stat weapon profiles; native bonuses and save layouts stay intact."""
import hashlib

from growth_patch import Assembler

FIRST = 0x10
LIMIT = 0x100
ARENA = 0x7ED000
SIZE = 0x800
CODE = ARENA + 0x40
FLAGS = ARENA + 0x100
VALUES = ARENA + 0x200
MAGIC = b'FE4BBONUSES1'.ljust(16, b'\0')
READER = 0x4A6B6
HOOK = 0x4A6CC
NATIVE = bytes.fromhex(
    '8B 08 4B AB DA AE 74 05 DA 3A 8D 74 05 22 00 98 84 09 00 00 '
    'F0 18 C9 0E 00 B0 1B 3A 0A AA BF C9 89 83 18 6D 74 05 AA '
    'BF D3 89 83 29 FF 00 FA 8E 74 05 FA 28 AB 6B A9 00 00 80 F3')


def cpu(address):
    # PC bank 7E is ROM here; CPU bank 7E is WRAM. Use its ExHiROM alias.
    return address - 0x400000


def program():
    a = Assembler()
    # Enter inside 84:A6B6, after the native prologue saves P/DBR/X and
    # converts the requested stat (1..6) to a zero-based index in $0574.
    a.emit('C9 10 00');a.branch('90', 'native')
    a.emit('DA AA BF');a.long(cpu(FLAGS));a.emit('29 FF 00')
    a.branch('F0', 'zero')
    a.emit('AD 74 05 C9 06 00');a.branch('B0', 'zero')
    a.emit('8A 38 E9 10 00 0A 48 0A 18 63 01 18 6D 74 05 AA BF')
    a.long(cpu(VALUES));a.emit('29 FF 00 83 01 68 FA 5C');a.long(0x84A6E4)
    a.mark('zero');a.emit('A9 00 00 FA 5C');a.long(0x84A6E4)
    a.mark('native');a.emit('C9 0E 00');a.branch('B0', 'special')
    a.emit('5C');a.long(0x84A6D1)
    a.mark('special');a.emit('5C');a.long(0x84A6EC)
    code = a.finish()
    assert len(code) <= FLAGS - CODE
    hook = b'\x5C' + cpu(CODE).to_bytes(3, 'little') + b'\xEA'
    return code, hook


def read(rom, address, size):
    if not 0 <= address <= address + size <= len(rom.data) - rom.header:
        raise ValueError('Weapon bonus data points outside the ROM.')
    return bytes(rom.data[rom.header + address:rom.header + address + size])


def installed(rom):
    return len(rom.data) - rom.header >= ARENA + SIZE and read(rom, ARENA, 16) == MAGIC


def block_for(profiles, fill):
    code, _ = program()
    block = bytearray(SIZE)
    block[:16] = MAGIC;block[16:18] = bytes([fill, 1])
    block[0x40:0x40 + len(code)] = code
    for value, bonuses in profiles.items():
        block[0x100 + value] = 1
        at = 0x200 + (value - FIRST) * 6
        block[at:at + 6] = bytes(bonuses)
    block[32:64] = hashlib.sha256(block[:32] + block[64:]).digest()
    return bytes(block)


class BonusProfiles:
    def __init__(self, rom):
        self.rom, self.snapshot = rom, bytes(rom.data)
        self.installed = installed(rom);self.profiles = {}
        self.block = read(rom, ARENA, SIZE) if len(rom.data) - rom.header >= ARENA + SIZE else b''
        if not self.installed:
            if read(rom, HOOK, 5) == program()[1]:
                raise ValueError('Custom weapon bonus metadata is missing or damaged. Restore a backup.')
            return
        b = self.block
        if b[16] not in (0, 255) or any(v not in (0, 1) for v in b[0x110:0x200]):
            raise ValueError('Custom weapon bonus metadata changed. Restore a backup.')
        for value in range(FIRST, LIMIT):
            if b[0x100 + value]:
                at = 0x200 + (value - FIRST) * 6
                self.profiles[value] = tuple(b[at:at + 6])
        if b != block_for(self.profiles, b[16]) or not self.profiles:
            raise ValueError('Custom weapon bonus storage failed its integrity check. Restore a backup.')
        self.verify_reader()

    def verify_reader(self):
        expected = bytearray(NATIVE)
        if self.installed:expected[HOOK - READER:HOOK - READER + 5] = program()[1]
        if read(self.rom, READER, len(expected)) != expected:
            raise ValueError('The weapon stat bonus routine has unsupported custom code. No data was changed.')

    def require_current(self):
        if bytes(self.rom.data) != self.snapshot:
            raise ValueError('The ROM changed in another editor. Reload bonus profiles before writing.')

    def apply(self, profiles):
        self.require_current();self.verify_reader()
        if len(self.rom.data) - self.rom.header != 0x800000 or read(self.rom, 0xFFD5, 1)[0] & 0x2F != 0x25:
            raise ValueError('New weapon bonuses require the supported 8 MiB ExHiROM layout.')
        if not self.installed:
            if len(set(self.block)) != 1 or self.block[0] not in (0, 255):
                raise ValueError('Custom bonus storage at PC 7ED000–7ED7FF is occupied. No data was changed.')
        fill = self.block[16] if self.installed else self.block[0]
        block = block_for(profiles, fill) if profiles else bytes([fill]) * SIZE
        hook = program()[1] if profiles else NATIVE[HOOK - READER:HOOK - READER + 5]
        before = bytes(self.rom.data)
        try:
            from item_expansion import put, update_checksum
            put(self.rom, ARENA, block);put(self.rom, HOOK, hook)
            BonusProfiles(self.rom)
            update_checksum(self.rom)
        except Exception:
            self.rom.data[:] = before
            raise
        self.__init__(self.rom)

    @staticmethod
    def validate(values):
        if len(values) != 6 or any(type(v) is not int or not 0 <= v <= 255 for v in values):
            raise ValueError('Enter six whole stat bonuses from 0 to 255.')
        return tuple(values)

    def add(self, values=None, *, source=0, profile=None):
        self.require_current()
        profile = next((i for i in range(FIRST, LIMIT) if i not in self.profiles), None) if profile is None else profile
        if type(profile) is not int or not FIRST <= profile < LIMIT or profile in self.profiles:
            raise ValueError('Choose an unused custom bonus ID from 10 through FF (240 available IDs).')
        if self.users(profile):raise ValueError('This bonus ID is already referenced by items. Clear those assignments first.')
        if values is None:
            from item_bonuses import BonusEditor, STATS
            model = BonusEditor(self.rom, 'weapon', source)
            copied = dict(zip(model.fields, model.values))
            values = [copied.get(stat, 0) for stat in STATS]
        profiles = dict(self.profiles);profiles[profile] = self.validate(values)
        self.apply(profiles)
        return profile

    def write(self, profile, values):
        self.require_current()
        if profile not in self.profiles:raise ValueError('This custom bonus profile is disabled.')
        profiles = dict(self.profiles);profiles[profile] = self.validate(values)
        self.apply(profiles)

    def users(self, profile):
        from item_bonuses import profile_users
        return profile_users(self.rom, 'weapon', {profile})

    def remove(self, profile):
        self.require_current()
        if profile not in self.profiles:raise ValueError('Only added custom profiles can be removed.')
        users = self.users(profile)
        if users:raise ValueError('Reassign these items before removing this bonus:\n' + '\n'.join(users))
        profiles = dict(self.profiles);del profiles[profile]
        self.apply(profiles)


def require_profile(rom, value):
    if type(value) is not int or not 0 <= value < LIMIT:
        raise ValueError('Choose a weapon stat bonus ID from 00 through FF.')
    if value >= FIRST and value not in BonusProfiles(rom).profiles:
        raise ValueError(f'Weapon bonus {value:02X} is disabled. Add it in Stat Bonus Editor before assigning it.')
