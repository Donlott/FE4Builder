"""Existing conversation participants, talk availability and recruitment switches."""
import json
from functools import lru_cache
from rom import DATA_DIR,character_modules
from event_layouts import checked,profiles

@lru_cache(maxsize=1)
def catalogue():return json.loads((DATA_DIR/'conversations.json').read_text(encoding='utf-8'))

def character_names(rom):
    modules=character_modules();field=next(f for f in modules[0].fields if f.reference=='FE4 Character Numbers.txt')
    names={key:value for key,value in field.options.items() if key>0 and key!=65535}
    from names import NameEditor
    for module in modules:
        idfield=next((i for i,f in enumerate(module.fields) if f.reference=='FE4 Character Numbers.txt'),None)
        namefield=next((i for i,f in enumerate(module.fields) if f.reference=='FE4 Character Name Numbers.txt'),None)
        if idfield is None or namefield is None:continue
        for index in range(module.count):
            values=rom.values(module,index)
            try:names[values[idfield]]=NameEditor(rom,values[namefield]).current
            except ValueError:pass
    return names

class Conversation:
    def __init__(self,rom,index):
        self.rom=rom;self.index=index;self.entry=catalogue()['entries'][index];e=self.entry
        for address,raw in e['guards']:
            if bytes(rom.data[address+rom.header:address+rom.header+len(raw)//2])!=bytes.fromhex(raw):
                raise ValueError('A linked event or talk table was relocated. Reopen the original supported layout to edit this conversation.')
        self.snapshots={tuple(key):checked(rom,profiles()[tuple(key)]) for key in e['profiles']}
        def pair(at):return tuple(int.from_bytes(rom.data[at+rom.header+i:at+rom.header+i+2],'little') for i in (0,2))
        self.pair=pair(e['checks'][0]+2)
        if any(pair(at+2)!=self.pair for at in e['checks']):raise ValueError('Linked talk conditions disagree. Their participant fields cannot be safely synchronized.')
        if e['editable']:
            if any(pair(at+3)!=self.pair for at in e['tables']):raise ValueError('The Talk menu table and conversation condition disagree.')
            for marker in e['markers']:
                at=marker['address']+rom.header
                if tuple(rom.data[at:at+2])!=self.pair:raise ValueError('A linked Talk target disagrees with the conversation condition.')
        self.enabled=[bytes(rom.data[r['address']+rom.header:r['address']+rom.header+5])==bytes.fromhex(r['original']) for r in e['recruits']]

    def write(self,initiator,target,enabled):
        e=self.entry;rom=self.rom
        current=Conversation(rom,self.index)
        if current.snapshots!=self.snapshots:raise ValueError('Linked event data changed while this editor was open. Reload before writing.')
        if len(enabled)!=len(self.enabled) or any(type(v) is not bool for v in enabled):raise ValueError('Incorrect recruitment switches.')
        if any(type(v) is not int for v in (initiator,target)):raise ValueError('Choose valid character IDs.')
        pair=(initiator,target)
        if pair!=self.pair:
            if not e['editable']:raise ValueError('This conversation uses an unverified or substitute-aware availability route. Its participants are read-only.')
            field=next(f for f in character_modules()[0].fields if f.reference=='FE4 Character Numbers.txt')
            valid={key for key in field.options if key>0 and key!=65535}
            if initiator not in valid|{65535} or target not in valid:raise ValueError('Choose named characters; only the initiator may be Any character.')
            if initiator==target:raise ValueError('A character cannot talk to themselves.')
            if e['markers'] and (initiator>255 or target>255):raise ValueError('This conversation has byte-sized Talk targets: both IDs must be at most 255.')
            for i,other in enumerate(catalogue()['entries']):
                if i==self.index or other['chapter']!=e['chapter'] or other['kind']!=4:continue
                at=other['checks'][0]+rom.header
                a=int.from_bytes(rom.data[at+2:at+4],'little');b=int.from_bytes(rom.data[at+4:at+6],'little')
                if target==b and (initiator==a or 65535 in (initiator,a)):
                    raise ValueError('That participant pair overlaps another conversation in this chapter. Its event could fire instead.')
        edits=[]
        if e['editable']:
            words=initiator.to_bytes(2,'little')+target.to_bytes(2,'little')
            edits.extend((at+2,words) for at in e['checks']);edits.extend((at+3,words) for at in e['tables'])
            edits.extend((m['address'],bytes([initiator,target])) for m in e['markers'])
        for r,on in zip(e['recruits'],enabled):edits.append((r['address'],bytes.fromhex(r['original']) if on else b'\xfd'*5))
        for at,raw in edits:rom.data[at+rom.header:at+rom.header+len(raw)]=raw
        return [f'Conversation participants {self.pair} → {pair}; recruitment {self.enabled} → {enabled}.']
