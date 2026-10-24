"""FE4 module-backed character records. All module offsets include a copier header."""
from dataclasses import dataclass
from pathlib import Path
import os
import tempfile
import json
import re
from history import History,apply_entry

BUILDER_DIR = Path(__file__).resolve().parents[1]
ROOT = BUILDER_DIR.parent
DATA_DIR = BUILDER_DIR / 'data'
MODULES = ROOT / 'Nightmare Modules' / 'FE4 Nightmare modules'

def number(text):
    return int(text, 16) if text.lower().startswith('0x') else int(text)

def lines(path):
    return [s.strip() for s in path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
            if s.strip() and not s.lstrip().startswith(('#', '//'))]

def skill_combinations(options, size):
    """Skill fields are bitmasks, not mutually exclusive skill identifiers."""
    bits = {1 << i: options.get(1 << i, '').strip() for i in range(size * 8)}
    result = {0: options.get(0, 'None') or 'None'}
    for value in range(1, 1 << (size * 8)):
        labels = []
        for bit, label in bits.items():
            if value & bit:
                labels.append(label if label and label.lower() != 'unused'
                              else f'{label or "Unknown flag"} (0x{bit:02X})')
        result[value] = ' + '.join(labels)
    return result

@dataclass
class Field:
    name: str
    offset: int
    size: int
    options: dict
    signed: bool = False
    reference: str = ''

@dataclass
class Module:
    name: str
    offset: int
    count: int
    stride: int
    names: list
    fields: list
    addresses: list = None

def load_module(path):
    data = lines(path)
    names = (lines(path.parent / data[5]) if data[5] != 'NULL'
             else [f'Record {i:03X}' for i in range(number(data[3]))])
    fields = []
    for i in range(7, len(data), 5):
        label, offset, size, kind, reference = data[i:i+5]
        options = {}
        if reference != 'NULL':
            for line in lines(path.parent / reference)[1:]:
                parts = line.split(maxsplit=1)
                try:
                    options[number(parts[0])] = parts[1] if len(parts) > 1 else ''
                except ValueError:
                    continue
        if reference == 'FE4 Character Skills 3.txt':
            # SAFEGUARD/Characters.h: UnitSkill3Escape = $04; battle code
            # routes it to rlActionStructSetUnitDefeatedEscape, not normal death.
            options[0x04] = 'Escape (retreat on defeat)'
            # Native personal-skill lookup and consumers also accept these
            # ring effects directly; Canto has no personal mask in that table.
            options[0x08] = 'Recover'
            options[0x20] = 'Return'
        if label.startswith(('Skills', 'Class Skills')):
            options = skill_combinations(options, number(size))
        if path.parent.name=='Item Editors' and label in ('Stat Bonus','Stat Bonuses'):
            from item_bonuses import WEAPON_NAMES,RING_BONUSES
            if path.name in ('FE4 Weapon Editor.nmm','FE4 Weapon Editor 2.nmm'):
                reference='FE4 Weapon Bonus.txt'
                options=dict(enumerate(WEAPON_NAMES))
            else:
                options=dict(RING_BONUSES)
        fields.append(Field(label, number(offset), number(size), options, kind.endswith('S'), reference))
    count = number(data[3])
    names = (names + [f'Record {i:03X}' for i in range(len(names), count)])[:count]
    module = Module(data[1], number(data[2]), number(data[3]), number(data[4]), names, fields)
    if len(names) != module.count or any(f.offset + f.size > module.stride for f in fields):
        raise ValueError(f'Invalid module: {path}')
    return module

def character_modules():
    paths = [MODULES / 'Character Editors' / 'FE4 1st Gen Character Editor.nmm']
    paths += [MODULES / 'Character Editors' / f'FE4 2nd Gen Character Editor {i}.nmm' for i in range(1, 4)]
    paths += [MODULES / 'Children Editors' / f'FE4 Children Editor {i}.nmm' for i in range(1, 4)]
    return [load_module(p) for p in paths]

def class_modules():
    return [load_module(MODULES / 'Class Editors' / 'FE4 Class Editor.nmm')]

EDITOR_CATEGORIES = {
    'Item Editor': 'Item Editors',
    'Shop Editor': 'Shop Editors',
    'Enemy Editor': 'Enemy Editors',
    'Holy Character Editor': 'Holy Character Editors',
    'Love Editor': 'Love Editors',
    'Character Settings': 'Character Editors',
    'Children Settings': 'Children Editors',
    'Class Settings': 'Class Editors',
    'Music & Other Tables': '',
}

def category_modules(mode):
    folder = MODULES / EDITOR_CATEGORIES[mode]
    # Compare numeric runs as numbers: Editor 2 belongs before Editor 10.
    modules = [load_module(path) for path in sorted(folder.glob('*.nmm'),
               key=lambda p: tuple(int(part) if part.isdigit() else part.casefold()
                                   for part in re.split(r'(\d+)', p.name)))]
    if mode == 'Item Editor':
        priority = {'FE4 Weapon/Staff Editor 1': 0, 'FE4 Weapon/Staff Editor 2': 1}
        modules.sort(key=lambda module: priority.get(module.name, 2))
    return modules

def army_modules(rom=None):
    """Expose the two 8-byte unit entries in each upstream 16-byte row."""
    units = load_module(MODULES / 'Army Editors' / 'FE4 Army Editor.nmm')
    units.stride = 8
    units.count *= 2
    units.fields = units.fields[:6]
    units.fields[0].name = 'Character'
    units.names = [f'Unit {i:03X}' for i in range(units.count)]
    pointers = load_module(MODULES / 'Army Editors' / 'FE4 Army Pointer Editor.nmm')
    pointers.count = len(pointers.fields)
    pointers.stride = 2
    pointers.fields = [Field('Army pointer', 0, 2, {})]
    pointers.names = [f'Army {i:02X}' for i in range(pointers.count)]
    if rom is not None:
        return chapter_army_modules(rom, units.fields)
    return [units, pointers]

def chapter_army_modules(rom, fields):
    fields = fields[:4] + [Field('AI', 5, 1, {}), Field('Faction slot', 6, 1, {}),
                          Field('Formation ID', 7, 1, {})]
    metadata = json.loads((DATA_DIR / 'army_groups.json').read_text())
    base = 0x1c000 + rom.header
    offsets = [int.from_bytes(rom.data[base+i*2:base+i*2+2], 'little') for i in range(len(metadata))]
    result = [Module('Prologue' if i == 0 else 'Final Chapter' if i == 11 else f'Chapter {i}',
                     0, 0, 8, [], fields, []) for i in range(12)]
    for group_id, (info, offset) in enumerate(zip(metadata, offsets)):
        if offset < len(metadata)*2 or offset >= 0x4000 or (offset-116) % 8:
            raise ValueError(f'Army group {group_id:02X}: invalid deployment pointer 0x{offset:04X}')
        start = base + offset
        # Bound scanning by the next distinct group or end of this ROM bank.
        end = base + min([p for p in offsets if p > offset] + [0x4000])
        # The disassembly's final unused group has 13 entries and no sentinel.
        unused = group_id == 57
        if unused:
            end = min(end, start + 13*8)
        module = result[info['chapter']]
        terminated = False
        for address in range(start, end, 8):
            if address + 8 > end:
                break
            character = int.from_bytes(rom.data[address:address+2], 'little')
            if character == 0xffff:
                terminated = True
                break
            name = fields[0].options.get(character, f'Character 0x{character:04X}')
            module.names.append(f'{group_id:02X} {info["group"]} / {name}')
            module.addresses.append(address - rom.header)
        if not terminated and not (unused and end == start + 13*8):
            raise ValueError(f'Army group {group_id:02X}: missing end marker before the next group')
    for module in result:
        module.count = len(module.names)
    pointers = Module('Army pointers (advanced)', base - rom.header + 512, len(metadata), 2,
                      [f'{i:02X} / {result[g["chapter"]].name} / {g["group"]}' for i, g in enumerate(metadata)],
                      [Field('Relative group pointer', 0, 2, {})])
    return result + [pointers]

class Rom:
    def __init__(self, path):
        self.path = Path(path)
        self.data = bytearray(self.path.read_bytes())
        remainder = len(self.data) % 0x8000
        if remainder not in (0, 512) or len(self.data) < 0x400000:
            raise ValueError('Expected a FE4 SNES ROM, with or without a 512-byte copier header.')
        self.header = remainder
        title = bytes(self.data[0xffc0 + remainder:0xffd5 + remainder])
        if not title.startswith(b'FIREEMBLEM4'):
            raise ValueError('The internal ROM title does not identify Fire Emblem 4.')
        self.original = bytes(self.data)
        self.history=History(self.path,self.original)
        self.last_backup=None

    def address(self, module, index):
        if not 0 <= index < module.count:
            raise ValueError('Character index out of range')
        address = (module.addresses[index] + self.header if module.addresses is not None
                   else module.offset - 512 + self.header + module.stride * index)
        if address < 0 or address + module.stride > len(self.data):
            raise ValueError('Character record is outside the ROM')
        return address

    def values(self, module, index):
        address = self.address(module, index)
        return [int.from_bytes(self.data[address+f.offset:address+f.offset+f.size], 'little', signed=f.signed) for f in module.fields]

    def field_options(self, field):
        if field.reference in ('FE4 Ring Bonuses.txt','FE4 Item Bonuses.txt'):
            from item_bonuses import ring_bonuses
            return ring_bonuses(self)
        if field.reference=='FE4 Weapon Bonus.txt':
            from item_bonuses import weapon_bonuses
            return weapon_bonuses(self)
        if field.reference == 'FE4 Character Name Numbers.txt':
            result = dict(field.options)
            from names import NameEditor
            for name_id in range(63):
                try:
                    result[name_id] = NameEditor(self,name_id).current
                except ValueError:
                    break
            return result
        if field.reference != 'FE4 Player Equipment.txt':
            return field.options
        player_items = load_module(MODULES / 'Item Editors' / 'FE4 Player Weapon Editor.nmm')
        item_names = player_items.fields[0].options
        start = self.address(player_items, 0)
        result = {}
        for slot in field.options:
            if slot == 255:
                result[slot] = 'Nothing'
            elif 1 <= slot <= 142:
                item_id = self.data[start + slot - 1]
                name = item_names.get(item_id) or f'Unknown item 0x{item_id:02X}'
                result[slot] = {'El Wind': 'Elwind', 'None': 'Nothing'}.get(name, name)
            else:
                result[slot] = f'Unknown slot 0x{slot:02X}'
        return result

    def write(self, module, index, values):
        if len(values) != len(module.fields):
            raise ValueError('Wrong field count')
        chunks = []
        for field, value in zip(module.fields, values):
            minimum = -(1 << (8 * field.size - 1)) if field.signed else 0
            maximum = (1 << (8 * field.size - int(field.signed))) - 1
            if not minimum <= value <= maximum:
                raise ValueError(f'{field.name}: value must be between {minimum} and {maximum}')
            chunks.append(value.to_bytes(field.size, 'little', signed=field.signed))
        address = self.address(module, index)
        for field, chunk in zip(module.fields, chunks):
            self.data[address+field.offset:address+field.offset+field.size] = chunk

    @property
    def dirty(self):
        return self.data != self.original

    def save_copy(self, path):
        target = Path(path).resolve()
        if target == self.path.resolve():
            raise ValueError('Choose a new filename to preserve the source ROM.')
        if target.exists():
            self.last_backup=History(target,target.read_bytes()).backup(target,target.read_bytes())
        self._save(target)

    def save_original(self,description='ROM edit',details=None):
        target = self.path.resolve()
        if target.read_bytes() != self.original:
            raise ValueError('The ROM was changed outside FE4Builder. Reopen it before writing.')
        if not self.dirty:
            return
        state,backup=self.history.prepare(self.original,bytes(self.data),description,details)
        self._save(target)
        self.last_backup=backup
        self.history.finish(state)

    def undo(self):
        return self._history_step(False)

    def redo(self):
        return self._history_step(True)

    def restore_backup(self,path):
        path=Path(path).resolve()
        try:
            path.relative_to(self.history.folder.resolve())
        except ValueError:
            raise ValueError('Choose a backup belonging to this ROM.')
        backup=Rom(path)
        event=next((e for e in self.history.state['audit'] if e['backup']==path.name),None)
        if event and event.get('before_hash'):
            from history import digest
            if digest(backup.data)!=event['before_hash']:
                raise ValueError('This backup failed its integrity check; the ROM was not changed.')
        if backup.header!=self.header:
            raise ValueError('The backup copier-header format differs from the opened ROM.')
        if self.dirty:
            raise ValueError('Save or discard staged ROM changes before restoring a backup.')
        before=bytes(self.data)
        self.data[:]=backup.data
        try:
            self.save_original(f'Restore backup: {path.name}')
        except (OSError,ValueError):
            self.data[:]=before
            raise

    def _history_step(self,redo):
        if self.dirty:
            raise ValueError('Save or discard staged ROM changes before undo/redo.')
        if not (self.history.can_redo if redo else self.history.can_undo):
            return False
        if self.path.read_bytes()!=self.original:
            raise ValueError('The ROM was changed outside FE4Builder. Reopen it before undo/redo.')
        cursor=self.history.state['cursor']
        entry=self.history.state['entries'][cursor if redo else cursor-1]
        output=apply_entry(self.original,entry,redo)
        state,backup=self.history.prepare(self.original,bytes(output),entry['description'],entry['details'],
                                         action='Redo' if redo else 'Undo',cursor=cursor+(1 if redo else -1))
        before=bytes(self.data)
        self.data[:]=output
        try:
            self._save(self.path.resolve())
        except (OSError,ValueError):
            self.data[:]=before
            raise
        self.last_backup=backup
        self.history.finish(state)
        return True

    def _save(self, target):
        fd, temporary = tempfile.mkstemp(dir=target.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(self.data)
                stream.flush()
                os.fsync(stream.fileno())
            if target==self.path.resolve() and target.read_bytes()!=self.original:
                raise ValueError('The ROM changed during the save. Reopen it before writing.')
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        if target == self.path.resolve():
            self.original = bytes(self.data)
