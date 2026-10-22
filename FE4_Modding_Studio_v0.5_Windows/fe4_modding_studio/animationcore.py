"""Original-layout FE4 animation assignment editor. Does not insert graphics/code."""
from pathlib import Path
from dataclasses import dataclass
import json,hashlib
CAT=json.loads((Path(__file__).parent/'data/animation_catalog.json').read_text(encoding='utf-8'))
CLASSES=CAT['classes'];MAP_NAMES=CAT['map_profiles'];MOVEMENT={int(k):v for k,v in CAT['movement_sprites'].items()}
WEAPONS={0:'Sword',1:'Lance',2:'Axe',3:'Bow',5:'Javelin',6:'Hand axe',7:'Magic',8:'Staff'}
BATTLE=0x1788c9;COUNT=206;MAP=0x1eb50d;FEMALE=0x1e85df;STANDING=0x17e8fb
class AnimationError(ValueError):pass
@dataclass(frozen=True)
class Entry:
    kind:str
    address:int
    original:bytes
    label:str
    key:tuple=()

def classname(i):return 'FF Disabled' if i==255 else f'{i:02X} {CLASSES[i]}' if i<len(CLASSES) else f'{i:02X} Unknown class'
def gender(i):return {0:'Male',1:'Female',255:'Fallback'}.get(i,f'Gender {i:02X}')
def order_key(row):return (row[0],row[3],row[2]==0,row[2])

def grouped(rows):
    # Class and gender order need not be numerically sorted, only contiguous.
    for width in (1,2,3):
        seen=set();last=None
        for row in rows:
            key=(row[0],row[3],row[2])[:width]
            if key!=last:
                if key in seen:return False
                seen.add(key);last=key
    for c,g in {(r[0],r[3]) for r in rows}:
        generic=False
        for r in rows:
            if (r[0],r[3])!=(c,g):continue
            if r[2]==0:generic=True
            elif generic:return False
    return True

class AnimationModel:
    def __init__(self,rom):
        self.rom=rom;self.changes={};self.reorder=False;self.entries={};self.by_kind={}
        b=rom.data
        for sig in CAT['signatures']:
            if hashlib.sha256(b[sig['start']:sig['end']]).hexdigest()!=sig['sha256']:
                raise AnimationError(f'Animation loader at {sig["start"]:06X} differs from the supported original-layout profile. Other editors remain available.')
        self.battle_original=bytes(b[BATTLE:BATTLE+COUNT*8]);self.battle_rows=[self.battle_original[i*8:(i+1)*8] for i in range(COUNT)]
        for i,r in enumerate(self.battle_rows):
            if (r[0]>=72 and r[0]!=255) or r[1] not in WEAPONS or r[3] not in (0,1):raise AnimationError('Unrecognized battle assignment table layout.')
            unit=f'unit {r[2]:02X}' if r[2] else 'all units'
            self.add('Battle',BATTLE+i*8+4,4,f'{classname(r[0])} | {gender(r[3])} | {WEAPONS[r[1]]} | {unit} | row {i:03}',tuple(r[:4]))
        self.bad_order=not grouped(self.battle_rows)
        for i,name in enumerate(MAP_NAMES):self.add('Map combat',MAP+49*i,49,f'{i:02X} {name}',(i,))
        for c in range(72):self.add('Female map assignment',FEMALE+c*2,2,classname(c),(c,))
        for i in range(138):
            a=STANDING+3*i;c,w=b[a:a+2]
            if c>=72 or w not in WEAPONS:raise AnimationError('Unrecognized standing-position table.')
            self.add('Battle positioning',a+2,1,f'{classname(c)} | {WEAPONS[w]} | row {i:03}',(c,w))
        for weapon,start,count in [(3,0x18affd,15),(6,0x18b03b,12),(5,0x18b06d,17)]:
            if b[start+4*count:start+4*count+2]!=b'\xff\xff':raise AnimationError('Projectile timing table terminator differs.')
            for i in range(count):
                a=start+4*i;c=int.from_bytes(b[a:a+2],'little')
                if c>=72:raise AnimationError('Unrecognized projectile timing class.')
                self.add('Projectile timing',a+2,2,f'{classname(c)} | {WEAPONS[weapon]}',(c,weapon))
        # These selectors use table-relative offsets and five-byte records; FF is fallback.
        for c in range(72):
            at=0x3805e+int.from_bytes(b[0x3805e+2*c:0x38060+2*c],'little')
            seen=0
            while True:
                if not 0x380ee<=at<=0x38337 or seen>=16:raise AnimationError('Map movement assignment table is relocated or invalid.')
                unit=int.from_bytes(b[at:at+2],'little');g=b[at+2]
                if g not in (0,1,255):raise AnimationError('Unsupported movement gender selector.')
                sprite=int.from_bytes(b[at+3:at+5],'little')
                if sprite not in MOVEMENT:raise AnimationError('Unrecognized map movement sprite ID.')
                self.add('Map movement',at+3,2,f'{classname(c)} | {gender(g)} | '+(f'unit {unit:04X}' if unit else 'all units'),(c,unit,g))
                if g==255:break
                at+=5;seen+=1
        for e in self.entries.values():self.validate(e,e.original)
    def add(self,kind,address,length,label,key):
        if address in self.entries:
            # Shared selector records must be edited consistently and advertised.
            old=self.entries[address]
            self.entries[address]=Entry(kind,address,old.original,old.label+' / '+label,old.key)
            return
        e=Entry(kind,address,bytes(self.rom.data[address:address+length]),label,key)
        self.entries[address]=e;self.by_kind.setdefault(kind,[]).append(address)
    @property
    def dirty(self):return bool(self.changes or self.reorder)
    def value(self,address):return self.changes.get(address,self.entries[address].original)
    def validate(self,e,value):
        if len(value)!=len(e.original):raise AnimationError('Assignment length cannot change.')
        if e.kind=='Battle':
            for n,v in zip(['control','main','sub','palette'],value):
                if v>CAT['limits'][n]:raise AnimationError(f'{n} ID {v:02X} exceeds the supported table range.')
        elif e.kind=='Map movement':
            if int.from_bytes(value,'little') not in MOVEMENT:raise AnimationError('Choose an existing movement sprite.')
        elif e.kind=='Map combat':
            if value[48] not in (0,1):raise AnimationError('Invalid map sprite type.')
            for offset in range(0,48,3):self.rom.address(int.from_bytes(value[offset:offset+3],'little'))
        elif e.kind=='Female map assignment':
            if value!=b'\xff\xff' and (value[0]!=e.key[0] or value[1]>=94):raise AnimationError('Use the class ID plus a female profile ID, or FF FF for the default.')
        elif e.kind=='Battle positioning':
            # Known control-header list occupies 00..2B in this profile.
            allowed={x.original[0] for x in self.entries.values() if x.kind==e.kind}
            if value[0] not in allowed:raise AnimationError('Choose a positioning ID already used by this ROM.')
    def stage(self,address,value):
        e=self.entries[address];value=bytes(value);self.validate(e,value)
        if value==e.original:self.changes.pop(address,None)
        else:self.changes[address]=value
    def copy_from(self,target,donor):
        a,b=self.entries[target],self.entries[donor]
        if a.kind!=b.kind:raise AnimationError('Donor must be the same assignment type.')
        if a.kind=='Female map assignment':
            value=self.value(donor);value=bytes([a.key[0],b.key[0] if value==b'\xff\xff' else value[1]])
        else:value=self.value(donor)
        self.stage(target,value)
    def warning(self,e):
        if e.kind!='Battle':return ''
        c,w,unit,g=e.key;notes=[]
        if not any(x.key==(c,w) for x in self.entries.values() if x.kind=='Battle positioning'):notes.append('No class/weapon positioning row exists; engine fallback remains in use.')
        if w in (3,5,6) and not any(x.key==(c,w) for x in self.entries.values() if x.kind=='Projectile timing'):notes.append('No class/weapon projectile timing row exists; copying appearance does not add one.')
        return ' '.join(notes)
    def planned(self):
        patches=[]
        battle_dirty=any(self.entries[a].kind=='Battle' for a in self.changes)
        if battle_dirty and self.bad_order and not self.reorder:raise AnimationError('This ROM has ungrouped battle rows. Enable “Group battle rows for lookup” before saving battle edits; all existing records are retained.')
        if battle_dirty or self.reorder:
            rows=[r[:4]+self.value(BATTLE+i*8+4) for i,r in enumerate(self.battle_rows)]
            if self.reorder:rows=sorted(rows,key=order_key)
            patches.append((BATTLE,self.battle_original,b''.join(rows)))
        patches.extend((a,self.entries[a].original,v) for a,v in sorted(self.changes.items()) if self.entries[a].kind!='Battle')
        return patches
    def apply(self,data):
        patches=self.planned();log=[]
        for a,old,new in patches:
            if bytes(data[a:a+len(old)])!=old:raise AnimationError(f'Another edit overlaps animation data at {a:06X}.')
            data[a:a+len(old)]=new
            if bytes(data[a:a+len(new)])!=new:raise AnimationError('Animation write verification failed.')
            log.append(f'Animation assignment {a:06X}: {len(new)} bytes')
        return log
    def export(self):return {'format':'fe4-animation-edits-v1','rom_sha256':self.rom.sha256,'group_battle_rows':self.reorder,'changes':{f'{a:06X}':v.hex() for a,v in self.changes.items()}}
    def import_project(self,obj):
        if obj.get('format')!='fe4-animation-edits-v1' or obj.get('rom_sha256')!=self.rom.sha256:raise AnimationError('Project does not match this source ROM.')
        before=self.changes.copy();flag=self.reorder
        try:
            for key,value in obj['changes'].items():self.stage(int(key,16),bytes.fromhex(value))
            if type(obj.get('group_battle_rows')) is not bool:raise AnimationError('Invalid grouping setting.')
            self.reorder=obj['group_battle_rows']
        except Exception:self.changes=before;self.reorder=flag;raise
