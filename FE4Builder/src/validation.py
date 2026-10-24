"""Profile-aware explanations and read-only validation; unknown semantics stay warnings."""
from dataclasses import dataclass
from copy import copy
from rom import MODULES,load_module,class_modules,character_modules,army_modules
from portraits import pc_address,COUNT,GRAPHICS_TABLE,PALETTE_TABLE

@dataclass(frozen=True)
class Issue:
    severity: str
    field: str
    message: str

def pointer_field(module,field):
    # Some 24-bit fields are machine-code patches, not pointers.
    return field.name=='Address' and field.size==3 and 'Definition Editor' in module.name

def explain_field(module,field):
    name=field.name
    if module.name=='FE4 Item Sprite Editor by Lorena' and name in ('Sprite','Palette'):
        meaning='Held-weapon battle sprite/palette assignment. This changes the larger weapon artwork; the 16x16 inventory icon is a separate graphics resource. Use the Held weapon preview to inspect changes.'
    elif field.reference=='FE4 Player Equipment.txt':
        meaning='Inventory slot ID, not an item type ID. Slots 1-142 point to shared player item assignments; 255 means Nothing. The linked item editor changes stats for every instance of that item type.'
    elif field.reference=='FE4 Weapon List.txt':
        meaning='Direct item type ID. Weapon/staff or ring stats are shared by every instance of this item. 255 means Nothing.'
    elif field.reference=='FE4 Classes.txt':
        meaning='Class ID. Class base stats, movement, ranks and skills are shared by all characters using that class. Click the link to edit its profile.'
    elif field.reference=='FE4 Character Skills 3.txt':
        meaning='Personal skill bitmask. Bit 0x04 is Escape: defeated/retreat handling instead of normal death. Finn, Quan and Ethlyn use it in generation 1. Their departure scripts are separate: Quan/Ethlyn leave together, Finn independently. Keep the flag for their standard story behavior. Recover (0x08) restores HP to maximum at turn start; Return (0x20) enables the return-to-home-castle command when its normal conditions permit. Both work as personal skills without their rings. Life and Elite retain their existing names. Canto is supplied by class/item skills, not a personal bit in the standard ROM.'
    elif name.startswith(('Skills','Class Skills','Skill Set')):
        meaning='Bitmask: each named skill is a flag, and one option can contain several skills. Unknown or unused bits are flagged rather than silently removed.'
    elif name.startswith('Blood'):
        meaning='Holy blood flags. Each two-bit pair encodes minor or major blood for one lineage. Setting both grades for the same lineage is suspicious. Blood can change weapon access and inherited stats.'
    elif 'Growth' in name:
        meaning='Growth percentage used when leveling. Values above 100 are supported; child growths also depend on inheritance.'
    elif name.startswith('Base '):
        meaning='Class base contribution shared by characters using this class.' if 'Class Editor' in module.name else 'Stored personal base stat. Final stats can also include class contributions and inheritance; this is not always the displayed in-game total.'
    elif field.reference=='Class Weapon Rank.txt':
        meaning='Base class weapon access: 0 = A, 1 = B, 2 = C, 3 = unavailable. Holy blood may affect effective character ranks.'
    elif field.reference=='FE4 Weapon Rank.txt':
        meaning='Required weapon rank: 0 = A, 1 = B, 2 = C, 255 = holy/S. Holy and personal restrictions are not fully simulated by validation.'
    elif name=='Leadership':
        meaning='Number of leadership stars. A designated army/group leader gives Hit and Avoid bonuses to themselves and allies within 3 tiles: 0-1 stars = no bonus, 2 = +10, 3 = +20, 4 = +30, 5 = +40. The first star gives no bonus. Giving stars to an ordinary unit does not automatically make them a leader. Normal values are 0-5; higher values are outside the original bonus table, and events may alter leadership.'
    elif name=='Promotion-Into Level':
        meaning='Minimum character level required to promote into this destination class (normally 20). FE4 reads this field from the character\'s promotion target, not their current class. Changing it affects every character whose promotion target is this class; it does not reset the character\'s level.'
    elif name=='Gold x 100':
        meaning='Stored in units of 100 gold: a value of 10 represents 1,000 gold.'
    elif name in ('X','Y'):
        meaning='Army deployment grid coordinate, normally 0-63. Existing off-map or event-controlled coordinates can be preserved; new out-of-range positions are rejected.'
    elif name=='Relative group pointer':
        meaning='16-bit byte offset relative to unheadered PC 0x1C000, not a 24-bit SNES address. Editing it can redirect a shared deployment group; the full army structure is checked.'
    elif pointer_field(module,field):
        meaning='24-bit SNES ROM address, not a file offset. Validation checks address mapping and ROM bounds; portrait definitions also check the compressed graphics stream.'
    elif 'pointer' in name.lower() or 'Pointer' in module.name:
        meaning='Pointer or offset whose interpretation depends on the module bank/base. No universal conversion is assumed; only documented pointer formats are checked automatically.'
    elif name=='Char Name':
        meaning='Shared name ID. The name editor edits the text/graphics referenced by this ID; other users of the same ID also change.'
    elif name in ('Minimum Range','Maximum Range'):
        meaning='Weapon/staff minimum or maximum targeting range. Minimum greater than maximum is flagged; special item behavior may require custom rules.'
    elif name=='Faction slot':
        meaning='Deployment faction slot. Events can change allegiance, so this alone does not determine permanent player/enemy ownership.'
    elif name=='AI':
        meaning='Stored AI behavior byte. Event scripts and other AI data also affect behavior; these combinations are not fully interpreted yet.'
    elif name=='Movement':
        meaning='Base class movement in map tiles; terrain costs, skills, items and events can affect actual movement.'
    else:
        meaning='No detailed behavioral description is documented for this field yet. Labels and named options follow its Nightmare module.'
    minimum=-(1<<(field.size*8-1)) if field.signed else 0
    maximum=(1<<(field.size*8-int(field.signed)))-1
    return f'{name}: {meaning}\nStored range: {minimum} to {maximum} ({field.size} byte(s)).'

def validate_record(rom,module,index,values):
    issues=[]
    if len(values)!=len(module.fields):
        return [Issue('Error','Record','Wrong number of field values.')]
    stored=rom.values(module,index)
    named={f.name:v for f,v in zip(module.fields,values)}
    for f,v,old in zip(module.fields,values,stored):
        low=-(1<<(f.size*8-1)) if f.signed else 0
        high=(1<<(f.size*8-int(f.signed)))-1
        if not low<=v<=high:
            issues.append(Issue('Error',f.name,f'Value must be {low} to {high}.'));continue
        if f.reference=='FE4 Classes.txt' and not 0<=v<72:
            issues.append(Issue('Warning',f.name,'Unsupported class ID for this ROM profile. Custom class tables are not modeled.'))
        elif f.reference=='FE4 Player Equipment.txt':
            if v!=255 and not 1<=v<=142:
                issues.append(Issue('Warning',f.name,'Unsupported inventory slot; expected 1-142 or 255 (Nothing).'))
            elif v!=255:
                player=load_module(MODULES/'Item Editors'/'FE4 Player Weapon Editor.nmm')
                item=rom.data[rom.address(player,0)+v-1]
                if item not in player.fields[0].options:
                    issues.append(Issue('Warning',f.name,f'Slot {v} refers to unknown item ID {item:02X}.'))
        elif f.options and v not in f.options and not f.name.startswith(('Blood','Skills','Class Skills','Skill Set')):
            issues.append(Issue('Warning',f.name,'Value is absent from the named module options; it may be unused or specific to a hack.'))
        if f.name.startswith(('Skills','Class Skills','Skill Set')):
            known=sum(bit for bit in (1<<i for i in range(f.size*8)) if f.options.get(bit,'').strip() and not f.options[bit].lower().startswith(('unused','unknown','?')))
            if v&~known:
                issues.append(Issue('Warning',f.name,f'Contains unknown/unused skill bits 0x{v&~known:X}.'))
        if f.name=='Leadership' and v>5:
            issues.append(Issue('Warning',f.name,'Normal leadership is 0–5 stars; this value is outside the original bonus table.'))
        if f.name.startswith('Blood'):
            known=sum(1<<i for i in range(f.size*8) if f.options.get(1<<i,'').strip())
            if v&~known:issues.append(Issue('Warning',f.name,f'Contains undocumented holy blood bits 0x{v&~known:X}.'))
        if f.name.startswith('Blood') and any((v>>shift)&3==3 for shift in range(0,f.size*8,2)):
            issues.append(Issue('Warning',f.name,'Minor and major flags are both set for at least one lineage.'))
        if module.addresses is not None and f.name in ('X','Y') and v>=64:
            issues.append(Issue('Error' if v!=old else 'Warning',f.name,'Coordinate is outside the 64 x 64 deployment grid. Existing off-map positions may be event-controlled.'))
        if pointer_field(module,f):
            if v==0:
                issues.append(Issue('Warning',f.name,'Null pointer; only safe if the game supports an absent resource here.'))
            else:
                try:
                    address=pc_address(v)
                    extent=named.get('Length',1)
                    if not 0<=address<len(rom.data)-rom.header or address+extent>len(rom.data)-rom.header:
                        raise ValueError('Pointer target is outside the ROM.')
                    if 'Portrait Definition' in module.name:
                        from fe4_codec import decompress
                        data,_=decompress(memoryview(rom.data)[rom.header:],address,limit=4096,banked=True)
                        if len(data)!=2048:raise ValueError('Portrait graphics must decode to 2048 bytes.')
                except ValueError as error:
                    issues.append(Issue('Error',f.name,str(error)))
    if module.name==character_modules()[0].name and index in (4,5,16):
        if not named.get('Skills 3',0)&0x04:
            issues.append(Issue('Warning','Skills 3','Escape protection is absent for generation-1 Finn, Quan or Ethlyn. Standard retreat, later appearances and related story behavior may be affected.'))
    if named.get('Minimum Range',0)>named.get('Maximum Range',255):
        issues.append(Issue('Warning','Range','Minimum range exceeds maximum range; normal targeting cannot use this interval.'))
    if any(f.name=='Relative group pointer' for f in module.fields):
        try:
            trial=copy(rom);trial.data=bytearray(rom.data)
            trial.write(module,index,values);army_modules(trial)
        except (ValueError,OverflowError) as error:
            issues.append(Issue('Error','Relative group pointer',str(error)))
    # Check base class ranks only. Blood/inheritance/events are not a full simulator.
    class_id=named.get('Class')
    if class_id is not None and 0<=class_id<72:
        classes=class_modules()[0]
        ranks=dict(zip((f.name for f in classes.fields),rom.values(classes,class_id)))
        has_blood=any(v for f,v in zip(module.fields,values) if f.name.startswith('Blood'))
        from linked_editors import field_target
        items=None
        for f,v in zip(module.fields,values):
            if not f.name.startswith('Equipment') or f.reference not in ('FE4 Player Equipment.txt','FE4 Weapon List.txt'):continue
            try:
                target=field_target(rom,f,v)
                if target is None or 'Weapon/Staff' not in target[1]:continue
                if items is None:
                    from rom import category_modules
                    items={m.name:m for m in category_modules('Item Editor')}
                item=items[target[1]]
                stats=dict(zip((f.name for f in item.fields),rom.values(item,target[2])))
                weapon=stats.get('Weapon Type',255)
                names=['Sword','Lance','Axe','Bow','Staff','Fire','Thunder','Wind','Light','Dark']
                if weapon>=len(names):continue
                rank=ranks.get(names[weapon]+' Rank',3)
                required=stats.get('Rank',2)
                if rank==3:
                    issues.append(Issue('Warning',f.name,f'Base class has no {names[weapon]} access. Holy blood, inheritance and event restrictions are not fully modeled.'))
                elif not has_blood and required!=255 and rank>required:
                    issues.append(Issue('Warning',f.name,f'Weapon requires a higher {names[weapon]} rank than the base class provides.'))
                elif required==255 and not has_blood:
                    issues.append(Issue('Warning',f.name,'Holy/S-rank weapon without stored holy blood. Inheritance and personal requirements need manual review.'))
            except (ValueError,KeyError):
                pass
    return issues

def shared_notes(rom,module,index,portrait_id=None,values=None):
    notes=[]
    from map_sprites import MapSprites
    if module.name==class_modules()[0].name:
        sprites=MapSprites(rom);count=0;missing=0
        for character in range(1,697):
            try:count+=sprites.character(character)[0]==index
            except (ValueError,IndexError):missing+=1
        notes.append(f'Shared class profile: {count} stored character IDs reference this class, including enemy/unused records. Promotions and event changes are additional users.')
        if missing:notes.append(f'{missing} character IDs could not be resolved; this reference count is incomplete.')
    ranges={'FE4 Weapon/Staff Editor 1':0,'FE4 Weapon/Staff Editor 2':0x7a,'FE4 Ring Editor':0x6a,'FE4 Item Editor by Camus':0x6a,'FE4 Circlet Editor':0x89}
    if module.name in ranges:
        item=ranges[module.name]+index
        player=load_module(MODULES/'Item Editors'/'FE4 Player Weapon Editor.nmm')
        start=rom.address(player,0)
        count=sum(value==item for value in rom.data[start:start+142])
        notes.append(f'Shared item-type data: ID {item:02X} appears in {count} player inventory slots. Enemy item references also use these stats; this is not a private copy of one equipped weapon.')
    for f,v in zip(module.fields,rom.values(module,index) if values is None else values):
        if f.reference=='FE4 Player Equipment.txt' and 1<=v<=142:
            count=0
            for table in character_modules():
                offsets=[i for i,field in enumerate(table.fields) if field.reference=='FE4 Player Equipment.txt']
                for i in range(table.count):
                    values=rom.values(table,i)
                    count+=any(values[j]==v for j in offsets)
            notes.append(f'{f.name}: inventory slot {v} is referenced by {count} stored character records. Assignment changes to that slot affect all references.')
    if 'Portrait Definition' in module.name:portrait_id=index
    if portrait_id is not None and 0<=portrait_id<COUNT:
        data=memoryview(rom.data)[rom.header:]
        for table,label in ((GRAPHICS_TABLE,'graphics pointer'),(PALETTE_TABLE,'palette pointer')):
            pointer=bytes(data[table+portrait_id*3:table+portrait_id*3+3])
            count=sum(bytes(data[table+i*3:table+i*3+3])==pointer for i in range(COUNT))
            notes.append(f'Portrait {portrait_id:02X} {label} is shared by {count} portrait IDs.')
        notes.append('A portrait replacement affects every character assigned that portrait ID. Different graphics pointers can also share compressed-stream bytes; the importer checks those dependencies and clones shared palettes when needed.')
    if not notes:notes.append('This table edits shared ROM data directly. Detailed reference counting is not implemented for this module; event/script references may exist.')
    return notes

def validate_structure(rom):
    issues=[]
    try:army_modules(rom)
    except ValueError as error:issues.append(Issue('Error','Army groups',str(error)))
    from chapter_maps import ChapterMap
    for chapter in range(12):
        try:
            model=ChapterMap(rom,chapter)
            if any((word&1023)>=len(model.graphics)//32 for word in model.definitions+model.dictionary):
                raise ValueError('Tile definition references graphics outside the loaded tileset.')
        except ValueError as error:issues.append(Issue('Error',f'Chapter {chapter}',str(error)))
    from portraits import Portrait
    for i in range(COUNT):
        try:Portrait(rom,i)
        except ValueError as error:issues.append(Issue('Error',f'Portrait {i:02X}',str(error)))
    return issues
