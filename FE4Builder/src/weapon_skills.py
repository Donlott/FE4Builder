"""Project Naga weapon-granted Adept, Accost, Vantage, Luna and Sol.

Keep the native 16-bit item flags intact. A separate byte per item type also
keeps shared item-definition pointers from accidentally sharing extra skills.
"""
import hashlib

from growth_patch import Assembler

ARENA = 0x7ED800
SIZE = 0x800
FLAGS = ARENA + 0x40
CODE = ARENA + 0x140
MAGIC = b'FE4BWSKILLS1'.ljust(16, b'\0')
SKILLS = ((1, 5, 'Adept'), (2, 18, 'Charge / Accost'), (4, 17, 'Vantage'),
          (8, 20, 'Luna'), (16, 21, 'Sol'))
GUARDS = {
    0x7A2EF: bytes.fromhex('8B 08 4B AB DA 5A 0A AA A0 01 00 98 22 B5 F3 84 AD 83 05 F0 1C 22 8E E3 87 C9 00 00 D0 07 98 22 2A F4 84 90 09 22 44 E4 87 3C 80 A2 D0 09 C8 80 DA 7A FA 28 AB 18 6B 7A FA 28 AB 38 6B'),
    0x7A32C: bytes.fromhex('8B 08 4B AB DA A9 00 00 8F 00 20 7E A2 1D 00 A9 00 00 9F 02 20 7E CA 10 F9 20 73 A3 20 9C A3 20 CD A3 FA 28 AB 6B'),
    0x4E231: bytes.fromhex('20 3B DF 90 14 A9 11 00 22 9D A1 87 90 0B BD 12 00 4A DD 10 00 90 02 38 60 18 60'),
    0x4E106: bytes.fromhex('A9 00 00 9D 3E 00 BD 00 00 10 04 5C 66 E1 84 BD 22 00 C9 08 00 F0 49 20 3B DF 90 44 20 D7 E4 90 3F B9 06 00 8D 6F 05 A9 0E 00 22 9D A1 87 B0 30 BD 28 00 22 1D E3 87 22 8D E4 87 C9 00 00 D0 20 BD 06 00 8D 6F 05 A0 13 00 98 22 9D A1 87 90 0A 22 CB 9B 84 22 9C EF 84 90 07 C8 C0 18 00 90 E9 60 C0 16 00 F0 14 C0 17 00 F0 0F AF E8 CC 7E CF D6 CC 7E D0 EB 8C DC CC 80 06 A9 14 00 9D 3E 00 98 EB 09 FE 00 8D 4A 05 A9 00 7E 8D 5D 05 A9 81 4F 8D 5C 05 22 65 E4 82 60'),
    0x4F38B: bytes.fromhex('8B 4B AB 8D 85 05 22 61 94 84 C9 02 00 B0 0F AD 85 05 22 78 F3 84 B0 04 22 63 E0 87 AB 6B 9C 87 05 AD 85 05 22 E6 F3 84 80 F2'),
    0x4F42A: bytes.fromhex('8B 4B AB DA 5A A6 00 DA 3A A8 B9 55 F4 29 FF 00 85 00 22 D4 EF 84 BD 00 00 29 FF 00 24 00 F0 08 38 FA 86 00 7A FA AB 6B 18 80 F6'),
}


def cpu(address):
    return address - 0x400000 if ARENA <= address < ARENA + SIZE else address


def program():
    a = Assembler()
    def jump(address):a.emit('5C');a.long(cpu(address))
    def call(label):a.call(cpu(CODE + a.labels[label]))
    # Preserve the caller's P across dispatch. Native skills still execute the
    # original checker with its original bank-$87 prologue, not PHK in bank 3E.
    a.mark('inventory');a.emit('08')
    for bit, identity, _ in SKILLS:
        a.emit('C9');a.word(identity);a.branch('F0', f'skill{bit}')
    a.emit('28')
    a.mark('native_inventory');a.emit('8B 08 F4 87 87 AB AB');jump(0x87A2F3)
    for bit, _, _ in SKILLS:
        a.mark(f'skill{bit}');a.emit('A9');a.word(bit);a.branch('80', 'scan')
    a.mark('scan');a.emit('8B DA 5A 48 F4 87 87 AB AB A0 01 00')
    a.mark('next_slot');a.emit('98');a.call(0x84F3B5)
    a.emit('AD 83 05');a.branch('F0', 'absent')
    a.call(0x87E38E);a.emit('C9 00 00');a.branch('D0', 'skip_slot')
    a.emit('98');a.call(0x84F42A);a.branch('90', 'skip_slot')
    a.emit('98');a.call(0x84F38B);a.branch('B0', 'skip_slot')
    a.emit('C9 FF 00');a.branch('B0', 'skip_slot')
    a.emit('AA BF');a.long(cpu(FLAGS));a.emit('29 1F 00 23 01')
    a.branch('D0', 'present')
    a.mark('skip_slot');a.emit('C8');a.branch('80', 'next_slot')
    a.mark('absent');a.emit('68 7A FA AB 28 18 6B')
    a.mark('present');a.emit('68 7A FA AB 28 38 6B')
    # Only these activation checks gain an item source. Other sword procs,
    # personal/class skills, Nihil checks and native eligibility stay native.
    a.mark('activation');a.emit('08 48');a.call(0x87A19D)
    a.branch('B0', 'personal');a.emit('68')
    for identity in (17, 20, 21):
        a.emit('C9');a.word(identity);a.branch('F0', 'item_activation')
    a.emit('28 18 6B')
    a.mark('item_activation');a.emit('28');jump(0x87A2EF)
    a.mark('personal');a.emit('83 01 68 28 38 6B')
    # Also extend the native skill-list builder without allocating icons or
    # granting duplicates when the unit already has a personal/class skill.
    a.mark('native_list');a.emit('8B 08 F4 87 87 AB AB');jump(0x87A330)
    a.mark('skill_list');call('native_list');a.emit('08 8B DA 5A 48')
    for _, identity, _ in SKILLS:
        a.emit('A9');a.word(identity);a.call(0x87A2EF)
        a.branch('90', f'list_next{identity}')
        a.emit('AF');a.long(0x7E2002 + identity);a.emit('29 FF 00')
        a.branch('D0', f'list_next{identity}')
        a.emit('E2 20 A9 01 8F');a.long(0x7E2002 + identity);a.emit('C2 20')
        a.emit('AF 00 20 7E 1A 8F 00 20 7E')
        a.mark(f'list_next{identity}')
    a.emit('68 7A FA AB 28 6B')
    code = a.finish()
    if len(code) > ARENA + SIZE - CODE:raise ValueError('Weapon skill code exceeds its ROM reservation.')
    hooks = {}
    for at, old, label, opcode in ((0x7A2EF, '8B 08 4B AB', 'inventory', 0x5C),
                                   (0x7A32C, '8B 08 4B AB', 'skill_list', 0x5C),
                                   (0x4E239, '22 9D A1 87', 'activation', 0x22),
                                   (0x4E150, '22 9D A1 87', 'activation', 0x22)):
        hooks[at] = bytes.fromhex(old), bytes([opcode]) + cpu(CODE + a.labels[label]).to_bytes(3, 'little')
    return code, hooks


def read(rom, at, size):
    if not 0 <= at <= at + size <= len(rom.data) - rom.header:
        raise ValueError('Additional weapon skill data points outside the ROM.')
    return bytes(rom.data[rom.header + at:rom.header + at + size])


def installed(rom):
    return len(rom.data) - rom.header >= ARENA + SIZE and read(rom, ARENA, 16) == MAGIC


def payload(flags, fill):
    code, _ = program();block = bytearray(SIZE)
    block[:16] = MAGIC;block[16:18] = bytes([fill, 1]);block[0x40:0x140] = flags
    block[0x140:0x140 + len(code)] = code
    block[32:64] = hashlib.sha256(block[:32] + block[64:]).digest()
    return bytes(block)


def verify(rom, active):
    _, hooks = program()
    for at, native in GUARDS.items():
        expected = bytearray(native)
        if active:
            for hook, (_, new) in hooks.items():
                if at <= hook < at + len(expected):expected[hook-at:hook-at+len(new)] = new
        if read(rom, at, len(expected)) != expected:
            raise ValueError(f'Unsupported or modified weapon skill code at PC {at:06X}. No code was changed.')
    for _, identity, name in SKILLS:
        if read(rom, 0x7A280 + identity * 2, 2) != bytes(2):
            raise ValueError(f'{name} already has a custom native item mapping. No code was changed.')


class WeaponSkills:
    def __init__(self, rom):
        self.rom, self.snapshot = rom, bytes(rom.data)
        self.installed = installed(rom);self.flags = bytes(256)
        self.block = read(rom, ARENA, SIZE) if len(rom.data)-rom.header >= ARENA+SIZE else b''
        if not self.installed:
            if read(rom, 0x7A2EF, 4) == program()[1][0x7A2EF][1]:
                raise ValueError('Additional weapon skill metadata is missing or damaged. Restore a backup.')
            return
        b = self.block;self.flags = b[0x40:0x140]
        if (b[16] not in (0, 255) or self.flags[255] or any(v & ~31 for v in self.flags) or
                b != payload(self.flags, b[16])):
            raise ValueError('Additional weapon skill storage failed its integrity check. Restore a backup.')
        verify(rom, True)

    def require_current(self):
        if bytes(self.rom.data) != self.snapshot:
            raise ValueError('The ROM changed in another editor. Reload additional weapon skills before writing.')

    def get(self, item):
        if type(item) is not int or not 0 <= item < 255:raise ValueError('Choose an item ID from 00 through FE.')
        return self.flags[item]

    def validate(self, item, value, raw=None):
        from item_expansion import enabled, record
        if type(item) is not int or item not in enabled(self.rom, 'items'):raise ValueError('This item type is disabled.')
        if type(value) is not int or not 0 <= value <= 31:raise ValueError('Choose only the five supported additional weapon skills.')
        raw = record(self.rom, item) if raw is None else raw
        if value and raw[1] != 0:raise ValueError('Additional weapon skills require a weapon, not a staff or ring.')
        if value & 24 and raw[10] != 0:raise ValueError('Luna and Sol require a sword with this patch. Clear those skills before changing its weapon type.')
        if value and not self.installed:raise ValueError('Install Additional weapon skills from Patches before assigning them.')

    def assign(self, item, value):
        self.require_current()
        if not self.installed:raise ValueError('Install Additional weapon skills from Patches first.')
        self.validate(item, value)
        flags = bytearray(self.flags);flags[item] = value
        from item_expansion import put, update_checksum
        put(self.rom, ARENA, payload(flags, self.block[16]));update_checksum(self.rom)
        self.__init__(self.rom)

    def users(self):
        from item_expansion import enabled
        from item_art import ItemArt
        art = ItemArt(self.rom);live = set(enabled(self.rom, 'items'));result = []
        for item, value in enumerate(self.flags):
            if not value:continue
            name = art.name(item) if item in live else 'Disabled item'
            result.append(f'{item:02X} {name}: ' + ', '.join(name for bit, _, name in SKILLS if value & bit))
        return result


def install(rom):
    if len(rom.data)-rom.header != 0x800000 or read(rom, 0xFFD5, 1)[0] & 0x2F != 0x25:
        raise ValueError('Additional weapon skills requires an 8 MiB Project Naga-compatible ExHiROM ROM.')
    model = WeaponSkills(rom)
    if model.installed:raise ValueError('Additional weapon skills is already installed.')
    verify(rom, False)
    if len(set(model.block)) != 1 or model.block[0] not in (0, 255):
        raise ValueError('Weapon skill storage at PC 7ED800–7EDFFF is occupied. No data was changed.')
    from item_expansion import put, update_checksum
    put(rom, ARENA, payload(bytes(256), model.block[0]))
    for at, (_, new) in program()[1].items():put(rom, at, new)
    update_checksum(rom)


def uninstall(rom):
    model = WeaponSkills(rom)
    if not model.installed:raise ValueError('Additional weapon skills is not installed.')
    users = model.users()
    if users:raise ValueError('Clear additional skills from these items before removing the patch:\n' + '\n'.join(users[:40]))
    from item_expansion import put, update_checksum
    for at, (old, _) in program()[1].items():put(rom, at, old)
    put(rom, ARENA, bytes([model.block[16]]) * SIZE);update_checksum(rom)


def require_record(rom, item, raw, value=None):
    if installed(rom):
        model = WeaponSkills(rom);model.validate(item, model.get(item) if value is None else value, raw)
    elif value:raise ValueError('Install Additional weapon skills from Patches first.')
