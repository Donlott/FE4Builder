"""Private scene copies; preserve original scripts and all unselected pointers."""
import hashlib
from dialogue import catalogue
from portraits import pointer_for,pc_address

REGIONS=((0x7d0000,0x8000),(0x7d9000,0x7000))
SIZE=0xf000
START=0x2400
MAGIC=b'FE4BDIALOGUEv1'.ljust(16,b'\0')
MAX_ENTRIES=2048


def physical(offset):
    return 0x7d0000+offset+(0x1000 if offset>=0x8000 else 0)


def pool(rom):
    return b''.join(rom.data[at+rom.header:at+rom.header+size] for at,size in REGIONS)


def digest(block):return hashlib.sha256(block[:64]+block[96:]).digest()


def plan(model,payload):
    rom=model.rom;entries=catalogue()['entries']
    if len(entries)>MAX_ENTRIES:raise ValueError('Dialogue catalogue exceeds the supported directory size.')
    fingerprint=hashlib.sha256(b''.join(e['address'].to_bytes(3,'little') for e in entries)).digest()[:16]
    block=bytearray(pool(rom))
    if block[:16]==MAGIC:
        if block[16:32]!=fingerprint or block[32] not in (0,255) or block[64:96]!=digest(block):
            raise ValueError('Dialogue storage was changed or uses another catalogue. Restore a backup.')
    else:
        if len(set(block))!=1 or block[0] not in (0,255):
            raise ValueError('Reserved dialogue storage is occupied. No dialogue was changed.')
        fill=block[0]
        block[:128]=bytes(128);block[:16]=MAGIC;block[16:32]=fingerprint;block[32]=fill
        block[128:128+MAX_ENTRIES*4]=bytes(MAX_ENTRIES*4)
    index=next(i for i,e in enumerate(entries) if e['address']==model.entry['address'])
    allocations=[]
    for i in range(len(entries)):
        at=128+i*4;offset=int.from_bytes(block[at:at+2],'little');size=int.from_bytes(block[at+2:at+4],'little')
        if not offset and not size:continue
        if not (START<=offset<offset+size<=0x8000 or 0x8000<=offset<offset+size<=SIZE):
            raise ValueError('Invalid dialogue allocation directory.')
        allocations.append((offset,offset+size,i))
    allocations.sort()
    if any(a[1]>b[0] for a,b in zip(allocations,allocations[1:])):raise ValueError('Dialogue allocations overlap.')
    own=next((a for a in allocations if a[2]==index),None)
    if own:
        if physical(own[0])!=model.start:raise ValueError('The private scene pointer no longer matches its allocation.')
        # Do not overwrite a private script deliberately shared by another ref.
        from villages import resolve_dialogue_ref
        for entry in entries:
            if entry['address']==model.entry['address']:continue
            at=resolve_dialogue_ref(rom,entry['address'])+rom.header
            try:target=pc_address(int.from_bytes(rom.data[at:at+3],'little'))
            except ValueError:continue
            if physical(own[0])<=target<physical(own[0])+own[1]-own[0]:
                raise ValueError('Another scene references this private text. Restore/reload before editing shared private scripts.')
    used=[a for a in allocations if a[2]!=index]
    chosen=None
    # First-fit reuse, respecting the growth-patch gap and half-bank boundaries.
    for low,high in ((START,0x8000),(0x8000,SIZE)):
        cursor=low
        for begin,end,_ in used+[(high,high,-1)]:
            if end<=low:continue
            if begin>=high:begin=high
            if begin-cursor>=len(payload):chosen=cursor;break
            cursor=max(cursor,end)
        if chosen is not None:break
    if chosen is None:raise ValueError('The 51 KiB private dialogue area is full. Shorten scenes or restore a backup; the ROM was not expanded.')
    if own:block[own[0]:own[1]]=bytes([block[32]])*(own[1]-own[0])
    block[chosen:chosen+len(payload)]=payload
    at=128+index*4;block[at:at+4]=chosen.to_bytes(2,'little')+len(payload).to_bytes(2,'little')
    block[64:96]=digest(block)
    from villages import dialogue_pointer_edit
    return [(REGIONS[0][0],bytes(block[:0x8000])),(REGIONS[1][0],bytes(block[0x8000:]))]+dialogue_pointer_edit(
        rom,model.ref-rom.header,pointer_for(physical(chosen)).to_bytes(3,'little'))
