"""Clamp signed personal + unsigned class stats before unsigned byte wrapping.

The original getters turn negative totals into large bytes, then cap them at
30. Class changes make this visible when the destination has a lower base.
Native bank-$84 padding holds stack-only helpers; no save layout is changed.
"""
import hashlib

from growth_patch import Assembler

ARENA = 0x04FF20
SIZE = 0xE0
CODE_OFFSET = 0x20
CODE = 0x84FF40
MAGIC = b'FE4BSIGNEDTOTAL1'
HOOKS = (0x49B57, 0x49BB2, 0x49C0D, 0x49C68, 0x49CD4, 0x49D40)
STAT_NAMES = ('Strength', 'Magic', 'Skill', 'Speed', 'Defense', 'Resistance')
FLASH_HOOK = 0x1E95D3


def program():
    """A/X are 16-bit; A=class base, X=personal-data pointer, DBR=its bank."""
    asm = Assembler()
    for index in range(1, 7):
        asm.mark(f'stat{index}')
        asm.emit('48 BD')           # save class base; absolute indexed LDA
        asm.word(index)
        if index != 6:
            asm.branch('80', 'sum')
    asm.mark('sum')
    asm.emit('29 FF 00 C9 80 00')    # isolate the personal byte
    asm.branch('90', 'positive')
    asm.emit('09 00 FF')            # sign-extend -128..-1
    asm.mark('positive')
    asm.emit('18 63 01')            # add the saved, unsigned class base
    asm.branch('30', 'zero')
    asm.emit('C9 1F 00')
    asm.branch('90', 'done')
    asm.emit('A9 1E 00')            # preserve the original base-stat cap
    asm.branch('80', 'done')
    asm.mark('zero')
    asm.emit('A9 00 00')
    asm.mark('done')
    asm.emit('83 01 68 6B')         # replace saved base with result; PLA; RTL
    # A class change can genuinely lower a stat. The native +gain animation
    # uses the gain as an unsigned digit tile, so skip it for zero/decreases.
    # Updated stats and the signed delta buffers remain untouched.
    asm.mark('gain_flash')
    asm.emit('B7 24')
    asm.branch('F0', 'skip_flash')
    asm.branch('30', 'skip_flash')
    asm.emit('5C');asm.long(0x9E95D7)
    asm.mark('skip_flash')
    asm.emit('5C');asm.long(0x9E961D)
    code = asm.finish()
    if CODE_OFFSET + len(code) > SIZE - 32:
        raise ValueError('The signed-stat helper exceeds its reserved space.')
    hooks = {}
    for index, address in enumerate(HOOKS, 1):
        old = bytes([0x18, 0x7D, index, 0, 0x29, 0xFF, 0, 0xC9, 0x1F, 0, 0x90, 3, 0xA9, 0x1E, 0])
        new = b'\x22' + (CODE + asm.labels[f'stat{index}']).to_bytes(3, 'little') + b'\xEA' * 11
        hooks[address] = old, new
    hooks[FLASH_HOOK] = bytes.fromhex('B7 24 F0 46'), b'\x5C' + (CODE + asm.labels['gain_flash']).to_bytes(3, 'little')
    return code, hooks


def read(rom, address, size):
    at = address + rom.header
    return bytes(rom.data[at:at + size])


def installed(rom):
    return read(rom, ARENA, len(MAGIC)) == MAGIC


def verify_callers(rom):
    for index, address in enumerate(HOOKS):
        # These native calls establish the current class pointer, personal-data
        # pointer/DBR and unsigned class base consumed by each helper.
        expected = bytes.fromhex('22 84 A0 84 22 ED 98 84 22') + (0x87A511 + index * 0x18).to_bytes(3, 'little')
        if read(rom, address - len(expected), len(expected)) != expected:
            raise ValueError(f'Unsupported or modified {STAT_NAMES[index]} getter at PC {address:06X}.')
    for address, expected in ((0x1E95CE, bytes.fromhex('BF 4C 96 9E A8')),
                              (0x1E961D, bytes.fromhex('A9 00 00 8F CE 45 7F AF D3 45 7F 1A 8F D3 45 7F'))):
        if read(rom, address, len(expected)) != expected:
            raise ValueError('Unsupported or modified promotion gain animation. No code was changed.')


def install(rom):
    if len(rom.data) - rom.header != 0x800000:
        raise ValueError('Requires the supported 8 MiB FE4 / Project Naga ROM layout.')
    if installed(rom):
        raise ValueError('Negative promotion stats is already installed.')
    code, hooks = program()
    verify_callers(rom)
    for address, (old, _) in hooks.items():
        if read(rom, address, len(old)) != old:
            raise ValueError(f'Incompatible or already patched stat calculation at PC {address:06X}.')
    block = read(rom, ARENA, SIZE)
    if len(block) != SIZE or len(set(block)) != 1 or block[0] not in (0, 255):
        raise ValueError('The signed-stat helper space is occupied. No code was changed.')
    payload = bytearray([block[0]]) * SIZE
    payload[:CODE_OFFSET] = (MAGIC + bytes([block[0], 1])).ljust(CODE_OFFSET, b'\0')
    payload[CODE_OFFSET:CODE_OFFSET + len(code)] = code
    payload[-32:] = hashlib.sha256(payload[:-32]).digest()
    # All profile, range and storage checks finish before the first mutation.
    rom.data[ARENA + rom.header:ARENA + rom.header + SIZE] = payload
    for address, (_, new) in hooks.items():
        rom.data[address + rom.header:address + rom.header + len(new)] = new


def uninstall(rom):
    if not installed(rom):
        raise ValueError('Negative promotion stats is not installed.')
    block = read(rom, ARENA, SIZE)
    code, hooks = program()
    if (len(block) != SIZE or block[16] not in (0, 255) or block[17] != 1 or
            block[18:CODE_OFFSET] != bytes(CODE_OFFSET - 18) or
            block[CODE_OFFSET:CODE_OFFSET + len(code)] != code or
            block[-32:] != hashlib.sha256(block[:-32]).digest()):
        raise ValueError('The signed-stat patch data changed. Restore a backup instead.')
    verify_callers(rom)
    for address, (_, new) in hooks.items():
        if read(rom, address, len(new)) != new:
            raise ValueError('A signed-stat patch hook changed. Restore a backup instead.')
    for address, (old, _) in hooks.items():
        rom.data[address + rom.header:address + rom.header + len(old)] = old
    rom.data[ARENA + rom.header:ARENA + rom.header + SIZE] = bytes([block[16]]) * SIZE
