"""Fixed-size existing objective conditions and the global defeat roster slot."""
import json
from functools import lru_cache
from rom import DATA_DIR,character_modules
from event_layouts import checked,profiles

@lru_cache(maxsize=1)
def catalogue():return json.loads((DATA_DIR/'objectives.json').read_text(encoding='utf-8'))

class Objective:
    def __init__(self,rom,index):
        self.rom=rom;self.index=index;self.entry=catalogue()['entries'][index];e=self.entry
        for address,raw in e['guards']:
            if bytes(rom.data[address+rom.header:address+rom.header+len(raw)//2])!=bytes.fromhex(raw):
                raise ValueError('A chapter, event or castle table changed location or layout. Objective editing is disabled for this layout.')
        keys=[e['profile']]+e['event_profiles']
        self.snapshots={tuple(key):checked(rom,profiles()[tuple(key)]) for key in keys}
        at=e['address']+rom.header;self.kind=rom.data[at];self.flag=rom.data[at+1]
        self.first=int.from_bytes(rom.data[at+2:at+4],'little')
        self.second=int.from_bytes(rom.data[at+4:at+6],'little') if self.kind in (2,15) else 65535
        self.castles=catalogue()['chapters'][e['chapter']]['castles']

    def write(self,kind,first,second):
        current=Objective(self.rom,self.index)
        if current.snapshots!=self.snapshots:raise ValueError('Objective data changed while this editor was open. Reload before writing.')
        if not self.entry['editable']:
            if (kind,first,second)==(self.kind,self.first,self.second):return []
            raise ValueError('Child/substitute-aware death checks are read-only.')
        if any(type(v) is not int for v in (kind,first,second)):raise ValueError('Choose valid objective fields.')
        if kind==2:
            if first not in (*range(7),65535):raise ValueError('Choose a faction slot from 0–6, or Any faction.')
            if second not in {c['id'] for c in self.castles}:raise ValueError('Choose a castle in the selected chapter.')
        elif kind==15:
            field=next(f for f in character_modules()[0].fields if f.reference=='FE4 Character Numbers.txt')
            if first not in {key for key in field.options if key>0}|{65535}:raise ValueError('Choose a character for the defeat trigger.')
            if second not in (*range(7),65535):raise ValueError('Choose a faction slot from 0–6, or Any faction.')
        else:raise ValueError('Supported objective types are Seize castle and Unit defeated.')
        if (kind,first,second)!=(self.kind,self.first,self.second):
            for i,e in enumerate(catalogue()['entries']):
                if i==self.index or e['chapter']!=self.entry['chapter'] or not e['editable'] or not e['events'] or not self.entry['events']:continue
                at=e['address']+self.rom.header
                if self.rom.data[at]!=kind:continue
                a=int.from_bytes(self.rom.data[at+2:at+4],'little');b=int.from_bytes(self.rom.data[at+4:at+6],'little')
                if kind==2:overlap=second==b and (first==a or 65535 in (first,a))
                else:overlap=(first==a or 65535 in (first,a)) and (second==b or 65535 in (second,b))
                already_overlapped=self.kind==kind and ((self.second==b and (self.first==a or 65535 in (self.first,a))) if kind==2 else (self.first==a or 65535 in (self.first,a)) and (self.second==b or 65535 in (self.second,b)))
                if overlap and not already_overlapped:raise ValueError('This condition overlaps another trigger in the chapter. Change that trigger first to avoid conflicting story actions.')
        at=self.entry['address']+self.rom.header
        raw=bytes([kind,self.flag])+first.to_bytes(2,'little')+second.to_bytes(2,'little')
        self.rom.data[at:at+6]=raw
        return [f'Objective at PC {self.entry["address"]:06X}: {(self.kind,self.first,self.second)} → {(kind,first,second)}; flag {self.flag:02X} preserved.']

class DefeatRule:
    def __init__(self,rom):
        self.rom=rom;self.profile=catalogue()['defeat'];self.snapshot=checked(rom,self.profile)
        self.address=self.profile['address'];at=self.address+rom.header
        self.slot=int.from_bytes(rom.data[at:at+2],'little')
        if not 1<=self.slot<=24:raise ValueError('The native protected-roster slot is outside the supported range 1–24.')

    def write(self,slot):
        if type(slot) is not int or not 1<=slot<=24:raise ValueError('Choose a protected roster slot from 1 to 24.')
        if DefeatRule(self.rom).snapshot!=self.snapshot:raise ValueError('The defeat rule changed while this editor was open. Reload before writing.')
        at=self.address+self.rom.header;self.rom.data[at:at+2]=slot.to_bytes(2,'little')
        return [f'Global player defeat roster slot {self.slot} → {slot} (both generations).']
