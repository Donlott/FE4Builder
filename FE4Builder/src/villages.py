"""Private village reward events, retaining original conditions and dialogue."""
import hashlib
import json
from functools import lru_cache
from rom import DATA_DIR,MODULES,load_module
from portraits import pc_address,pointer_for
from village_scripts import parse,signature

ARENA=0x6f0000
SIZE=0x10000
MAGIC=b'FE4BVILLAGESv1'.ljust(16,b'\0')
SLOT=0x180
STATS=('HP','Strength','Magic','Skill','Speed','Defense','Resistance','Luck')
CHAPTERS=['Prologue']+[f'Chapter {i}' for i in range(1,11)]+['Final Chapter']

@lru_cache(maxsize=1)
def entries():return json.loads((DATA_DIR/'villages.json').read_text(encoding='utf-8'))

def slot(index):return ARENA+0x8000+index*SLOT
def digest(block):return hashlib.sha256(block[:64]+block[96:]).digest()
def fingerprint():return hashlib.sha256(json.dumps(entries(),sort_keys=True).encode()).digest()[:16]


def pool(rom,create=False):
    block=bytearray(rom.data[ARENA+rom.header:ARENA+rom.header+SIZE])
    if block[:16]==MAGIC:
        if block[16:32]!=fingerprint() or block[32] not in (0,255) or block[64:96]!=digest(block):
            raise ValueError('Village storage was changed or uses another catalogue. Restore a backup.')
    elif create and len(block)==SIZE and len(set(block))==1 and block[0] in (0,255):
        fill=block[0];block[:128]=bytes(128);block[:16]=MAGIC;block[16:32]=fingerprint();block[32]=fill
    else:raise ValueError('Reserved village storage is occupied or unsupported. No rewards were written.')
    return block


def active_metadata(rom,index):
    data=pool(rom);at=slot(index)-ARENA;meta=data[at:at+32]
    if meta[:4]!=b'VLG1' or int.from_bytes(meta[4:6],'little')!=index:
        raise ValueError('Village script metadata is invalid.')
    length=int.from_bytes(meta[10:12],'little')
    if meta[6] not in (0,5,6,11) or meta[7]>1 or int.from_bytes(meta[8:10],'little')!=entries()[index]['length'] or not 2<=length<=SLOT-32:
        raise ValueError('Village script metadata is outside its supported bounds.')
    return meta,bytes(data[at+32:at+32+length])


def resolve_dialogue_ref(rom,reference):
    for index,entry in enumerate(entries()):
        if entry['start']<=reference<entry['start']+entry['length']:
            at=entry['ref']+rom.header
            target=pc_address(int.from_bytes(rom.data[at:at+3],'little'))
            if target==entry['start']:return reference
            if target!=slot(index)+32:raise ValueError('Village event pointer changed outside the supported layout.')
            meta,_=active_metadata(rom,index)
            offset=reference-entry['start'];cut=entry['reward']
            if meta[7] and cut is not None:
                if cut<=offset<cut+5:raise ValueError('Dialogue reference overlaps a removed reward command.')
                if offset>=cut+5:offset-=5
            return slot(index)+32+meta[6]+offset
    return reference


def dialogue_pointer_edit(rom,reference,payload):
    if not ARENA<=reference<ARENA+SIZE:return [(reference,payload)]
    if len(payload)!=3 or rom.data[reference+rom.header-1]!=0x0c:
        raise ValueError('Unsupported private village dialogue reference.')
    block=pool(rom);offset=reference-ARENA
    block[offset:offset+3]=payload;block[64:96]=digest(block)
    return [(ARENA,bytes(block))]


class Village:
    def __init__(self,rom,index):
        if len(rom.data)-rom.header!=0x800000:raise ValueError('Village rewards support the 8 MiB Project Naga beta 7 ROM.')
        self.rom,self.index=rom,index;self.entry=entries()[index]
        e=self.entry;at=e['ref']+rom.header
        self.pointer=bytes(rom.data[at:at+3]);target=pc_address(int.from_bytes(self.pointer,'little'))
        original=bytes(rom.data[e['start']+rom.header:e['start']+rom.header+e['length']])
        if signature(original)!=e['signature']:raise ValueError('Original village event code does not match this profile.')
        self.nodes=parse(original,0)[0];self.item=0;self.gold=0;self.stat=None;self.amount=None
        self.kind='none';reward=e['reward']
        if reward is not None:self.kind='item' if original[reward+1]==0x57 else 'stat'
        self.recipient='Visitor'
        if reward is not None:
            actor=int.from_bytes(original[reward+2:reward+4],'little') if self.kind=='item' else original[reward+2]
            if actor not in (255,65535):
                chars=load_module(MODULES/'Character Editors/FE4 1st Gen Character Editor.nmm').fields
                names=next(f.options for f in chars if f.reference=='FE4 Character Numbers.txt')
                self.recipient=names.get(actor,f'Character {actor:02X}')
        self.body=original;self.snapshot=original
        if target==slot(index)+32:
            meta,payload=active_metadata(rom,index);prefix=meta[6];removed=bool(meta[7])
            self.gold=int.from_bytes(meta[12:14],'little');self.item=meta[14]
            body=bytearray(payload[prefix:]);self.snapshot=payload
            if removed:
                if self.kind!='item':raise ValueError('Only an item command can be removed by this editor.')
                body[reward:reward]=original[reward:reward+5]
            for offset,opcode,size in self.nodes:
                if opcode in (2,3,4):
                    relative=ARENA+int.from_bytes(body[offset+1:offset+3],'little')-(slot(index)+32+prefix)
                    if removed and relative>=reward:relative+=5
                    body[offset+1:offset+3]=(e['start']+relative & 0xffff).to_bytes(2,'little')
            self.body=bytes(body)
            if len(body)!=e['length'] or signature(body)!=e['signature']:
                raise ValueError('Private village event structure does not match the original.')
        elif target!=e['start']:raise ValueError('Village event pointer has been relocated by another tool.')
        elif self.kind=='item':self.item=self.body[reward+4]
        if self.kind=='stat':self.stat,self.amount=self.body[reward+3:reward+5]
        self.original_values=(self.item,self.gold,self.stat,self.amount)

    def write(self,item,gold,stat=None,amount=None):
        if type(item) is not int or not 0<=item<=142 or type(gold) is not int or not 0<=gold<=50000:
            raise ValueError('Choose an item slot 1–142 or None; extra gold must be 0–50,000.')
        if self.kind=='stat' and (type(stat) is not int or not 0<=stat<8 or type(amount) is not int or not 0<=amount<=30):
            raise ValueError('Choose a supported stat and a bonus from 0–30.')
        if (item,gold,stat,amount)==self.original_values:return []
        fresh=Village(self.rom,self.index)
        if fresh.pointer!=self.pointer or fresh.snapshot!=self.snapshot or fresh.original_values!=self.original_values:
            raise ValueError('This village changed outside the editor. Reload before writing.')
        e=self.entry;body=bytearray(self.body);reward=e['reward'];removed=self.kind=='item' and item==0
        if self.kind=='item' and item:body[reward+4]=item
        elif self.kind=='stat':body[reward+3:reward+5]=bytes((stat,amount))
        if removed:del body[reward:reward+5]
        prefix=bytearray()
        if gold:prefix.extend(b'\x4a\x54\xff\xff'+gold.to_bytes(2,'little'))
        if self.kind!='item' and item:prefix.extend(b'\x4a\x57\xff\xff'+bytes([item]))
        def mapped(offset):return offset-(5 if removed and offset>=reward+5 else 0)
        boundaries={offset for offset,_,_ in self.nodes}
        for offset,opcode,size in self.nodes:
            if opcode in (2,3,4):
                destination=(e['start']&0xff0000)+int.from_bytes(self.body[offset+1:offset+3],'little')-e['start']
                if destination not in boundaries:raise ValueError('Village branch target is not a supported command boundary.')
                at=mapped(offset);target=slot(self.index)+32+len(prefix)+mapped(destination)
                body[at+1:at+3]=(target&0xffff).to_bytes(2,'little')
        payload=bytes(prefix+body)
        if len(payload)>SLOT-32:raise ValueError('Village event exceeds its private allocation.')
        block=pool(self.rom,create=True);at=slot(self.index)-ARENA
        block[at:at+SLOT]=bytes([block[32]])*SLOT
        meta=bytearray(32);meta[:4]=b'VLG1';meta[4:6]=self.index.to_bytes(2,'little')
        meta[6]=len(prefix);meta[7]=removed;meta[8:10]=e['length'].to_bytes(2,'little');meta[10:12]=len(payload).to_bytes(2,'little')
        meta[12:14]=gold.to_bytes(2,'little');meta[14]=item
        block[at:at+32]=meta;block[at+32:at+32+len(payload)]=payload;block[64:96]=digest(block)
        self.rom.data[ARENA+self.rom.header:ARENA+self.rom.header+SIZE]=block
        # RUN_EVENT_CONDITION uses the event's bank as DB for both ROM reads
        # and low-address WRAM writes. The 2F:8000 mirror maps this ExHiROM
        # allocation while keeping low WRAM visible; bank 6F would not.
        ref=e['ref']+self.rom.header;self.rom.data[ref:ref+3]=(slot(self.index)+32-0x400000).to_bytes(3,'little')
        return [f'{CHAPTERS[e["chapter"]]} / {e["label"]}: item slot {self.item} → {item}; extra gold {self.gold} → {gold}',
                f'Stat reward: {self.stat}/{self.amount} → {stat}/{amount}; original event conditions retained']
