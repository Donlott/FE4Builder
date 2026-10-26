"""Live references to persistent player item slots, rather than item-type IDs."""
from dataclasses import dataclass
from bisect import bisect_right
import re
from rom import character_modules, category_modules, army_modules
from item_art import ItemArt
from portraits import pc_address
from item_slot_events import decode

PLAYER_MODULE = 'FE4 Player Weapon Editor'
SLOT_COUNT = 142


@dataclass(frozen=True)
class Appearance:
    kind: str
    generation: int
    chapter: int | None
    label: str
    target: tuple
    address: int | None = None
    note: str = ''

    @property
    def order(self):
        return (self.generation or 99, -1 if self.kind == 'inheritance' else self.chapter if self.chapter is not None else 99,
                self.kind, self.label, self.address or 0)

    @property
    def title(self):
        if self.kind == 'inheritance':return f'Generation 2 · Inheritance · {self.label}'
        chapter = f'Chapter {self.chapter}' if self.chapter not in (None, 0, 11) else {None:'Chapter unknown',0:'Prologue',11:'Final Chapter'}[self.chapter]
        return (f'Generation {self.generation}' if self.generation else 'Generation unknown')+f' · {chapter} · {self.label}'


def record_name(rom, table, index, character_names):
    values = dict(zip((f.name for f in table.fields), rom.values(table, index)))
    character = next((values[k] for k in ('Char no.', 'Chararacter Number', 'Character Number') if k in values), None)
    name = character_names.get(character, table.names[index])
    return name, character


class SlotLocations:
    """Rebuild from live bytes whenever a source editor writes/reloads a ROM."""
    def __init__(self, rom):
        self.rom = rom
        self.rows = {slot: [] for slot in range(1, SLOT_COUNT+1)}
        self.warnings = []
        self.chapters = {}
        from conversations import character_names
        self.names = character_names(rom)
        self._deployments()
        self._events()
        for group,units in self.group_units.items():
            if group not in self.observed_groups and group!=57:
                for character in units:self.chapters.setdefault(character,set()).add(self.group_chapters[group])
        self._characters()
        self._shops()
        self._villages()
        self._inheritance()
        for rows in self.rows.values():
            rows.sort(key=lambda row: row.order)

    def add(self, slot, row):
        if 1 <= slot <= SLOT_COUNT and row not in self.rows[slot]:
            self.rows[slot].append(row)

    def _deployments(self):
        self.group_units={};self.group_chapters={};self.observed_groups=set()
        try:
            for chapter, table in enumerate(army_modules(self.rom)[:12]):
                for record in range(table.count):
                    group=int(table.names[record][:2],16)
                    character = self.rom.values(table, record)[0]
                    self.group_units.setdefault(group,[]).append(character)
                    self.group_chapters[group]=chapter
        except ValueError as error:
            self.warnings.append('Deployment chapters incomplete: '+str(error))

    def _events(self):
        from events import catalogue
        from villages import entries
        village_ids = {e['event_id'] for e in entries()}
        events=catalogue()['events']
        pointers={}
        for entry in events:
            try:
                at=0xfe8bf+entry['id']*3+self.rom.header
                if at+3>len(self.rom.data):raise ValueError('Event pointer outside ROM.')
                pointers[entry['id']]=pc_address(int.from_bytes(self.rom.data[at:at+3],'little'))
            except ValueError as error:self.warnings.append(entry['label']+': '+str(error))
        boundaries=sorted(set(pointers.values()))
        for entry in events:
            if entry['id'] in village_ids:
                continue # Village reader follows private editor relocations too.
            try:
                if entry['id'] not in pointers:continue
                start=pointers[entry['id']]
                next_index=bisect_right(boundaries,start)
                end=boundaries[next_index] if next_index<len(boundaries) else len(self.rom.data)-self.rom.header
                # Live pointers bound relocated/lengthened scripts too. The
                # decoder also caps traversal at 4 KiB and the current bank.
                grants, loads, errors = decode(self.rom, start, end-start)
                self.warnings.extend(entry['label']+': '+e for e in errors)
                for character, group in loads:
                    if group is None:
                        if character is not None and 0<character<0x8000:
                            self.chapters.setdefault(character, set()).add(entry['chapter'])
                    else:
                        self.observed_groups.add(group)
                        units=self.group_units.get(group,[])
                        selected=units if character is None else units[character-1:character] if character>0 else []
                        if not selected:self.warnings.append(f'{entry["label"]}: unresolved deployment group {group:02X}, entry {character}.')
                        for unit in selected:self.chapters.setdefault(unit,set()).add(entry['chapter'])
                for address, slot, actor, condition in grants:
                    recipient = self.names.get(actor, f'Character {actor:04X}') if not actor & 0x8000 else 'current event unit'
                    note = 'Event conditions must execute; inventory capacity can also prevent the grant.'
                    if condition == 0x5b:note = 'Event conditions must execute; this grant can send the last held item to supply.'
                    self.add(slot, Appearance('event', 1 if entry['chapter'] < 6 else 2, entry['chapter'],
                        f'Event reward — {entry["label"]} → {recipient}', ('event',entry['chapter'],entry['id'],address),address,note))
            except (ValueError, IndexError) as error:
                self.warnings.append(entry['label']+': '+str(error))

    def _characters(self):
        seen = set()
        groups = [('Character Editor', character_modules()),
                  ('Enemy Editor', category_modules('Enemy Editor')),
                  ('Holy Character Editor', category_modules('Holy Character Editor'))]
        for mode, tables in groups:
            for table_index, table in enumerate(tables):
                for index in range(table.count):
                    address = self.rom.address(table,index)
                    if address in seen:continue
                    seen.add(address)
                    name, character = record_name(self.rom,table,index,self.names)
                    chapters = self.chapters.get(character,set())
                    if mode == 'Character Editor':
                        generation = 1 if table_index == 0 else 2
                        chapters = {c for c in chapters if (c < 6) == (generation == 1)}
                        chapters = {min(chapters)} if chapters else {None}
                    else:
                        generation = None
                        chapters = chapters or {None}
                    values = self.rom.values(table,index)
                    for field,value in zip(table.fields,values):
                        if field.reference != 'FE4 Player Equipment.txt':continue
                        for chapter in sorted(chapters,key=lambda c:99 if c is None else c):
                            gen = generation or (1 if chapter is not None and chapter < 6 else 2 if chapter is not None else 0)
                            kind = 'starting' if mode == 'Character Editor' else 'drop'
                            description = 'Starting inventory' if kind == 'starting' else 'Enemy drop'
                            self.add(value,Appearance(kind,gen,chapter,
                                f'{description} — {name} (record {index:02X}, {field.name})',
                                ('record',mode,table.name,index),address+field.offset,
                                'Stored inventory; recruitment/deployment and alternate child/substitute routes must allow this unit.' if kind == 'starting' else 'Requires this enemy deployment and obtaining its drop.'))

    def _shops(self):
        for table in category_modules('Shop Editor'):
            for record in range(table.count):
                match = re.search(r'Chapter\s+(\d+)',table.name)
                chapter = int(match.group(1)) + record if match else None
                for field,value in zip(table.fields,self.rom.values(table,record)):
                    if field.reference != 'FE4 Player Equipment.txt':continue
                    if value == 0xff:break
                    self.add(value,Appearance('shop',1 if chapter is not None and chapter < 6 else 2,chapter,
                        f'Shop inventory — {field.name}',('record','Shop Editor',table.name,record),
                        self.rom.address(table,record)+field.offset,'Available only if this slot has not already been claimed in this generation.'))

    def _villages(self):
        from villages import Village,entries
        for index, entry in enumerate(entries()):
            try:
                model = Village(self.rom,index)
                self.add(model.item,Appearance('village',1 if entry['chapter'] < 6 else 2,entry['chapter'],
                    f'Village reward — {entry["label"]} → {model.recipient}',('village',entry['chapter'],index),
                    note='Requires the village visit and its visitor/story conditions; missed or destroyed villages do not claim the slot.'))
            except ValueError as error:
                self.warnings.append(entry['label']+f' (chapter {entry["chapter"]}): '+str(error))

    def _inheritance(self):
        art = ItemArt(self.rom)
        # The native inheritance routine's three explicit holy-weapon exceptions
        # are read from its CMP operands, not from item names or slot IDs.
        exceptions = set()
        code = memoryview(self.rom.data)[self.rom.header:]
        known = all(code[a] == 0xc9 and code[a+3] == 0xf0 for a in (0x7ab55,0x7ab5a,0x7ab5f))
        if known:
            exceptions = {int.from_bytes(code[a+1:a+3],'little') for a in (0x7ab55,0x7ab5a,0x7ab5f)}
        else:
            self.warnings.append('Inheritance code differs from the known CMP/branch profile; item eligibility is conditional and cannot be confirmed.')
        lock = next(m for m in category_modules('Children Settings') if 'Inheritance Lock' in m.name)
        for slot,rows in self.rows.items():
            origins = [r for r in rows if r.generation == 1]
            if not origins:continue
            item = self.rom.data[self.rom.address(art.player,0)+slot-1]
            if item == 0xff:continue
            try:
                stats = art.stats(item)
                if known and stats.get('Type') in (0,1) and stats.get('Rank',0)&0x80 and item not in exceptions:
                    continue
            except ValueError:
                self.warnings.append(f'Slot {slot:02X}: item inheritance eligibility could not be decoded.')
            self.add(slot,Appearance('inheritance',2,None,'Inherited from a generation-1 parent (conditional first appearance)',
                ('record','Children Settings',lock.name,0),note=
                'Takes priority over all ordinary generation-2 appearances if inherited. The actual parent must own this exact slot (inventory or personal supply), '
                'and the child must pass the ROM’s inheritance/weapon eligibility rules. Pairing, ownership, blood and class depend on the save. '
                'If it is not inherited, the earliest successful ordinary appearance can supply it instead. '
                +'Current Gen1 starting holders: '+(', '.join(r.label.split(' — ',1)[-1] for r in origins if r.kind=='starting') or 'none; a parent must obtain the slot through another listed source.')))

    def summary(self,slot):
        rows = self.rows[slot]
        text = ('This tracks player item SLOT '+f'{slot:02X}'+', including every indexed use of that slot. '
                'Each generation can claim it once. Later sources are fallback opportunities only when earlier sources were missed or unavailable. '
                'Within a chapter, event order and conditions determine the first successful source.')
        for generation in (1,2):
            candidates = [r for r in rows if r.generation == generation and r.kind != 'inheritance' and r.chapter is not None]
            if candidates:
                earliest = min(r.chapter for r in candidates)
                text += f' Generation {generation}: earliest ordinary indexed chapter is '+('Prologue' if earliest==0 else f'{earliest}')+'.'
        return text
