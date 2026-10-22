"""Read-only faction AI inspection. All addresses and operands come from the open ROM."""
import json
from functools import lru_cache
from rom import DATA_DIR,army_modules
from portraits import pc_address

@lru_cache(maxsize=1)
def catalogue():return json.loads((DATA_DIR/'ai.json').read_text(encoding='utf-8'))

def chapter_name(value):return 'Prologue' if value==0 else 'Final Chapter' if value==11 else f'Chapter {value}'

class AIViewer:
    def __init__(self,rom):
        from conversations import character_names
        self.rom=rom;self.names=character_names(rom);self.groups=[];self.warnings=[]
        for info in catalogue()['groups']:
            group=dict(info,entries=[],error=None)
            try:
                pointer=self.read(0x6c784+info['id']*3,3)
                at=self.address(pointer);table=self.read(at+7,2)
                group['address']=at;group['table']=table
                if table:
                    base=self.address((pointer&0xff0000)|table)
                    for index in range(8):
                        if self.read(base+index*3,2)==65535:break
                        script=self.read(base+index*3,3)
                        self.address(script)
                        group['entries'].append(dict(number=index+1,pointer=script,address=base+index*3))
            except ValueError as error:group['error']=str(error)
            self.groups.append(group)
        self.assignments=[]
        try:
            for chapter,module in enumerate(army_modules(rom)[:12]):
                for i in range(module.count):
                    at=rom.address(module,i);raw=rom.data[at:at+8]
                    self.assignments.append(dict(chapter=chapter,faction=raw[6],ai=raw[5],character=int.from_bytes(raw[:2],'little'),source=module.names[i],address=at-rom.header,leader=bool(raw[4])))
        except ValueError as error:self.warnings.append('Army assignments unavailable: '+str(error))
        from reinforcements import Reinforcement,catalogue as spawns
        for index,entry in enumerate(spawns()['entries']):
            if not any(u['kind']=='direct' for u in entry['units']):continue
            try:
                model=Reinforcement(rom,index)
                for unit in model.units:
                    if unit['kind']!='direct':continue
                    at=model.start+unit['offset'];flags=self.read(at+10,1)
                    self.assignments.append(dict(chapter=entry['chapter'],faction=unit['faction'],ai=flags&15,character=unit['identity'],source='Event: '+entry['label'],address=at,leader=bool(flags&128)))
            except ValueError as error:self.warnings.append(f"Event {entry['id']:03X} assignments unavailable: {error}")
    def read(self,at,size):
        start=at+self.rom.header
        if at<0 or start+size>len(self.rom.data):raise ValueError(f'Address ${at:06X} is outside the ROM.')
        return int.from_bytes(self.rom.data[start:start+size],'little')
    def address(self,pointer):
        try:at=pc_address(pointer)
        except ValueError:raise ValueError(f'Unsupported ROM pointer ${pointer:06X}.') from None
        self.read(at,1);return at
    def units(self,group,number):
        return [u for u in self.assignments if u['chapter']==group['chapter'] and u['faction'] in group['slots'] and u['ai']==number]
    def shared(self,pointer):
        return [(g,e) for g in self.groups for e in g['entries'] if e['pointer']==pointer]
    def decode(self,pointer):
        """Follow both conditional paths, stop at END, bound corrupt/cyclic scripts."""
        definitions=catalogue()['commands'];pending=[pointer];nodes={};occupied={};warnings=[]
        bank=pointer&0xff0000
        while pending:
            address=pending.pop()
            if address in nodes:continue
            if len(nodes)>=512:warnings.append('Stopped at the 512-command safety limit.');break
            if address&0xff0000!=bank:warnings.append(f'Branch leaves script bank: ${address:06X}.');continue
            try:
                at=self.address(address);opcode=self.read(at,1);definition=definitions.get(str(opcode))
                if definition is None:
                    nodes[address]=dict(address=address,pc=at,raw=bytes([opcode]),name=f'Unknown opcode ${opcode:02X}',text='Decoding stopped on this path.',uncertain=True);continue
                size=1+sum(n for _,n in definition['fields'])
                if (address&65535)+size>65536:raise ValueError('Command crosses bank boundary.')
                if any(address+i in occupied and occupied[address+i]!=address for i in range(size)):
                    warnings.append(f'Overlapping command/branch at ${address:06X}.');continue
                for i in range(size):occupied[address+i]=address
                values=[];offset=1;args=[]
                for label,n in definition['fields']:
                    value=self.read(at+offset,n);values.append(value);offset+=n
                    display=str(value)
                    if label=='CharacterID':display=self.names.get(value,f'Character ${value:04X}')
                    elif label in ('Address','Routine'):display=f'${(bank|value) if n==2 else value:06X}'
                    args.append(f'{label}: {display}')
                uncertain=definition['uncertain']
                name=definition['name'].replace('_',' ').title()
                if uncertain:name+=' [partly understood]'
                raw=bytes(self.rom.data[at+self.rom.header:at+self.rom.header+size])
                nodes[address]=dict(address=address,pc=at,raw=raw,name=name,text='; '.join(args),note=definition['note'],uncertain=uncertain)
                if opcode in (1,0x1f,0x20,0x21,0x22,0x23):pending.append(bank|values[-1])
                # AI_22 is not fully understood: show both paths conservatively.
                if opcode not in (1,255):pending.append(address+size)
            except ValueError as error:warnings.append(f'${address:06X}: {error}')
        return [nodes[a] for a in sorted(nodes)],warnings
