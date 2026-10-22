"""Edit fixed-size spawn operands and verified turn conditions without relocating code."""
import json
from functools import lru_cache
from rom import DATA_DIR
from portraits import pc_address
from event_layouts import checked

@lru_cache(maxsize=1)
def catalogue():return json.loads((DATA_DIR/'reinforcements.json').read_text(encoding='utf-8'))

class Reinforcement:
    def __init__(self,rom,index):
        self.rom=rom;self.index=index;self.entry=catalogue()['entries'][index]
        e=self.entry;self.profile=e['profile'];self.start=self.profile['start']
        at=0xfe8bf+e['id']*3+rom.header;self.pointer=bytes(rom.data[at:at+3])
        if pc_address(int.from_bytes(self.pointer,'little'))!=self.start:
            raise ValueError('This event has been relocated. Reinforcement editing supports its original location only.')
        self.snapshot=checked(rom,self.profile);self.units=[]
        for unit in e['units']:
            at=unit['offset'];raw=self.snapshot[at:at+11]
            direct=unit['kind']=='direct'
            values=list(raw[4:9] if direct else raw[4:7]);values[-1]&=7
            self.units.append(dict(unit,identity=int.from_bytes(raw[1:3],'little') if direct else int.from_bytes(raw[2:4],'little'),
                                   faction=raw[3] if direct else None,group=None if direct else raw[1],
                                   speed_flags=raw[8 if direct else 6]&0xf8,values=values))
        self.triggers=[];self.chapter_profile=catalogue()['chapters'][e['chapter']]
        links=[t for t in catalogue()['triggers'] if t['event']==e['id'] and t['chapter']==e['chapter']]
        self.chapter_snapshot=checked(rom,self.chapter_profile) if links else None
        for link in links:
            at=link['address']+rom.header
            shared=sorted({t['event'] for t in catalogue()['triggers'] if t['address']==link['address']})
            self.triggers.append(dict(link,turn=rom.data[at+1],faction=rom.data[at+2],shared=shared))

    def write(self,units,turns):
        current=Reinforcement(self.rom,self.index)
        if (current.pointer,current.snapshot,current.chapter_snapshot)!=(self.pointer,self.snapshot,self.chapter_snapshot):
            raise ValueError('Event data changed while this editor was open. Reload before writing.')
        if len(units)!=len(self.units) or len(turns)!=len(self.triggers):raise ValueError('Incorrect reinforcement field count.')
        edits=[]
        for old,values in zip(self.units,units):
            if len(values)!=len(old['values']):raise ValueError('Incorrect spawn field count.')
            if any(type(v) is not int for v in values):raise ValueError('Coordinates and speed must be whole numbers.')
            if any(not 0<=v<=63 for v in values[:-1]):raise ValueError('Map coordinates must be between 0 and 63.')
            if not 0<=values[-1]<=7:raise ValueError('Movement speed must be between 0 and 7.')
            raw=values[:-1]+[values[-1]|old['speed_flags']]
            edits.append((self.start+self.rom.header+old['offset']+4,bytes(raw)))
        for old,turn in zip(self.triggers,turns):
            if type(turn) is not int or not (1<=turn<=254 or turn==255):raise ValueError('Turn must be 1–254, or 255 for any turn.')
            edits.append((old['address']+self.rom.header+1,bytes([turn])))
        for at,raw in edits:self.rom.data[at:at+len(raw)]=raw
        return [f'Edited spawn coordinates / speed in event {self.entry["id"]:03X}; turn conditions: {turns}']
