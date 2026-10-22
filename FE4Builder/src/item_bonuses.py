"""Names for native weapon bonus profiles and standard ring effects."""
WEAPON_NAMES=('None','Tyrfing','Naga','Gungnir','Gae Bolg','Balmung','Yewfelle',
              'Helswath','Valflame','Mjolnir','Forseti','Bragi (unused profile)',
              'Mystletainn','Loptous','Safeguard','Barrier Blade')
RING_BONUSES={0:'None',1:'+5 Speed',2:'+5 Magic',3:'+5 Strength',4:'+5 Defense',
              5:'+5 Resistance',6:'+3 Movement',7:'+5 Skill'}
STATS=('Strength','Magic','Skill','Speed','Defense','Resistance')
# The operand bytes of native ADC/LDA immediate instructions. Signatures
# exclude the amount, permitting subsequent edits while rejecting other code.
CODE_EFFECTS={
    ('weapon',14):('Defense',(0x49ca4,),bytes.fromhex('d0 08 a5 4c 18 69'),bytes.fromhex('85 4c 22 ba 97')),
    ('weapon',15):('Resistance',(0x49d10,),bytes.fromhex('d0 08 a5 4c 18 69'),bytes.fromhex('85 4c 22 ba 97')),
}
for _value,_stat,_offset in ((1,'Speed',0x49c49),(2,'Magic',0x49b93),
                            (3,'Strength',0x49b38),(4,'Defense',0x49cb5),
                            (5,'Resistance',0x49d21),(7,'Skill',0x49bee)):
    CODE_EFFECTS['ring',_value]=(_stat,(_offset,),bytes.fromhex('f0 08 a5 4c 18 69'),bytes.fromhex('85 4c ae 6f 05'))
CODE_EFFECTS['ring',6]=('Movement',(0x49d7b,0x49dba),bytes.fromhex('89 02 00 f0 05 a9'),bytes.fromhex('85 4c 22'))


class BonusEditor:
    def __init__(self,rom,kind,value):
        if len(rom.data)-rom.header!=0x800000:
            raise ValueError('Bonus editing supports the 8 MiB Project Naga beta 7 ROM profile.')
        if kind not in ('weapon','ring') or not 0<=value<=(15 if kind=='weapon' else 7):
            raise ValueError('Select a supported bonus profile.')
        self.rom,self.kind,self.value=rom,kind,value
        self.name=WEAPON_NAMES[value] if kind=='weapon' else ('None' if value==0 else RING_BONUSES[value].split(' ',1)[1]+' ring effect')
        self.fields=[];self.locations=[];self.size=1
        if value and kind=='weapon' and value<14:
            table=0x389c9+rom.header
            self.pointer_at=table+(value-1)*2
            self.pointer=bytes(rom.data[self.pointer_at:self.pointer_at+2])
            relative=int.from_bytes(self.pointer,'little')
            if relative<26 or relative>218 or (relative-26)%16:
                raise ValueError('Unsupported weapon bonus table pointer; no data was changed.')
            self.fields=list(STATS)
            self.locations=[(table+relative+10+i,) for i in range(6)]
        elif value:
            stat,offsets,prefix,suffix=CODE_EFFECTS[kind,value]
            self.fields=[stat];self.locations=[tuple(at+rom.header for at in offsets)]
            self.size=2
            for at in self.locations[0]:
                if bytes(rom.data[at-len(prefix):at])!=prefix or bytes(rom.data[at+2:at+2+len(suffix)])!=suffix:
                    raise ValueError('This bonus uses unsupported or modified game code; no data was changed.')
            if len({bytes(rom.data[at:at+2]) for at in self.locations[0]})!=1:
                raise ValueError('Movement bonus routines disagree; restore a backup before editing.')
        self.original=[bytes(rom.data[locations[0]:locations[0]+self.size]) for locations in self.locations]
        self.values=[int.from_bytes(value,'little') for value in self.original]

    def write(self,values):
        if len(values)!=len(self.fields) or any(type(v) is not int or not 0<=v<=(3 if f=='Movement' else 255) for f,v in zip(self.fields,values)):
            raise ValueError('Use whole bonuses from 0–255; Movement supports 0–3 to keep the native movement lookup within range.')
        fresh=BonusEditor(self.rom,self.kind,self.value)
        if fresh.locations!=self.locations or fresh.original!=self.original:
            raise ValueError('This bonus changed outside the editor. Reload before writing.')
        edits=[(at,new.to_bytes(self.size,'little')) for locations,old,new in zip(self.locations,self.values,values) for at in locations if old!=new]
        for at,data in edits:self.rom.data[at:at+len(data)]=data
        return [f'{field}: +{old} → +{new}' for field,old,new in zip(self.fields,self.values,values) if old!=new]

    def users(self):
        from rom import category_modules
        result=[];seen=set()
        ids={self.value}
        if self.kind=='weapon' and 0<self.value<14:
            table=0x389c9+self.rom.header
            ids.update(i for i in range(1,14) if bytes(self.rom.data[table+(i-1)*2:table+i*2])==self.pointer)
        for module in category_modules('Item Editor'):
            if (self.kind=='weapon')!=module.name.startswith('FE4 Weapon/Staff Editor'):continue
            field=next((f for f in module.fields if f.name in ('Stat Bonus','Stat Bonuses')),None)
            if field is None:continue
            for index in range(module.count):
                address=self.rom.address(module,index)
                if address not in seen and self.rom.data[address+field.offset] in ids:
                    seen.add(address);result.append(module.names[index])
        return result


def ring_bonuses(rom):
    result={0:'None'}
    for value in range(1,8):
        try:
            effect=BonusEditor(rom,'ring',value)
            result[value]=f'+{effect.values[0]} {effect.fields[0]}'
        except ValueError:result[value]=RING_BONUSES[value]+' (unsupported code)'
    return result


def weapon_bonuses(rom):
    result={0:'None'}
    stats=('Strength','Magic','Skill','Speed','Defense','Resistance')
    for value,name in enumerate(WEAPON_NAMES[1:14],1):
        # Native 84A6B6 indexes the holy-blood profile table, then its six
        # weapon-boost bytes. Read the opened ROM so edited profiles stay true.
        table=0x389c9+rom.header
        pointer=table+(value-1)*2
        relative=int.from_bytes(rom.data[pointer:pointer+2],'little')
        start=table+relative+10
        boosts=rom.data[start:start+6]
        if len(boosts)==6 and 0<=relative<0x1000:
            effect=', '.join(f'+{amount} {stat}' for stat,amount in zip(stats,boosts) if amount)
            result[value]=f'{name}: {effect or "No stat increase"}'
        else:
            result[value]=f'{name} bonus profile'
    for value in (14,15):
        try:
            effect=BonusEditor(rom,'weapon',value)
            result[value]=f'{WEAPON_NAMES[value]}: +{effect.values[0]} {effect.fields[0]}'
        except ValueError:result[value]=WEAPON_NAMES[value]+' (unsupported code)'
    return result
