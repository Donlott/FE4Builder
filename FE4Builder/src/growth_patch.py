"""Project Naga beta 7 unit-screen growth display: native 65816 patch."""
import struct
import hashlib

ARENA=0x7d8000
SIZE=0x1000
CODE=ARENA-0x400000+0x100
FLAG=0x7e8b86  # Off-screen last tile of the unit-screen text buffer.
MAGIC=b'FE4BGROWTHSv2'
LEGACY_MAGIC=b'FE4BGROWTHSv1'

class Assembler:
    def __init__(self):self.data=bytearray();self.labels={};self.references=[]
    def emit(self,hexbytes):self.data.extend(bytes.fromhex(hexbytes))
    def word(self,value):self.data.extend(struct.pack('<H',value))
    def long(self,value):self.data.extend(value.to_bytes(3,'little'))
    def mark(self,label):self.labels[label]=len(self.data)
    def branch(self,opcode,label):self.emit(opcode);self.references.append((len(self.data),label));self.emit('00')
    def call(self,address):self.emit('22');self.long(address)
    def finish(self):
        for at,label in self.references:
            delta=self.labels[label]-at-1
            if not -128<=delta<=127:raise ValueError('Patch branch is too far.')
            self.data[at]=delta&255
        return bytes(self.data)

def program():
    # JSL init wrapper resets the view on each status-screen entry. The input
    # hook is a JML: its exit replays the displaced LDA/BMI before rejoining.
    a=Assembler()
    a.mark('init');a.emit('08 c2 20 48 a9 00 00 8f');a.long(FLAG)
    a.emit('68 28');a.call(0x88dbee);a.emit('6b')
    a.mark('input');a.emit('08 c2 30 da 5a a5 e8 89 00 40')
    a.branch('d0','toggle')
    a.emit('af');a.long(FLAG);a.emit('c9 5a a5');a.branch('d0','exit')
    a.emit('a5 e8 89 f0 bf');a.branch('f0','exit')
    a.branch('80','normal')
    a.mark('toggle')
    a.emit('af 8b 81 7f c9 02 00');a.branch('b0','exit')
    a.emit('af');a.long(FLAG);a.emit('c9 5a a5');a.branch('f0','normal')
    a.emit('a9 5a a5');a.branch('80','redraw')
    a.mark('normal');a.emit('a9 00 00')
    a.mark('redraw');a.emit('48');a.call(CODE+0x400);a.call(0x899510);a.call(0x89970d)
    # The slash belongs to the static template; redraw it when leaving growth mode.
    a.emit('a9 ee 24 8f 56 85 7e a9 fe 24 8f 96 85 7e')
    a.emit('68 8f');a.long(FLAG);a.emit('c9 5a a5');a.branch('d0','upload')
    a.call(CODE+0x200)
    a.mark('upload');a.call(CODE+0x600)
    a.call(0x80a4bd);a.emit('02 88 83 7e 00 08 80 00 58')
    a.mark('exit');a.emit('7a fa 28 a5 e8');a.branch('30','back')
    a.emit('5c 15 81 89')
    a.mark('back');a.emit('5c 32 81 89')
    if len(a.data)>0x200:raise ValueError('Growth input handler overlaps its renderer.')
    a.data.extend(bytes(0x200-len(a.data)))
    a.mark('render')
    a.emit('a9 ff 00')
    for offset in (0x1ca,0x1cc,0x1ce):
        for row in (0,64):a.emit('8f');a.long(0x7e8388+offset+row)
    entries=((0x84a464,0x1d0),(0x84a48e,0x354),(0x84a4b2,0x3d4),
             (0x84a4d6,0x454),(0x84a4fa,0x4d4),(0x84a566,0x554),
             (0x84a51e,0x5d4),(0x84a542,0x654))
    # Native redraw includes equipment/status bonuses to the right of each
    # base stat. The three-digit growth replaces the sign, but bonus digits
    # extend beyond it. Hide both remaining columns only in the growth view;
    # native redraw restores all bonus indicators on returning to stats.
    for _,position in entries[1:]:
        for offset in (6,8,70,72):
            a.emit('8f');a.long(0x7e8388+position+offset)
    for getter,position in entries:
        a.call(getter)
        a.emit('a2 20 35 86 0a a2 03 00 86 0c a2');a.word(position)
        a.call(0x89a18c)
    a.emit('6b')
    a.data.extend(bytes(0x400-len(a.data)))
    a.emit('a9 ff 00')
    for _,position in entries:
        for offset in (0,2,4,64,66,68):
            a.emit('8f');a.long(0x7e8388+position+offset)
    a.emit('6b')
    a.data.extend(bytes(0x600-len(a.data)))
    # The translated screen has a private 80x16 heading in BG3 tiles 60..79.
    # Queue both graphics halves through the native VBlank DMA helper; always
    # restore its original graphics before native navigation handles the input.
    a.emit('af');a.long(FLAG);a.emit('c9 5a a5');a.branch('d0','heading_normal')
    for source,dest in ((0x3d8900,0x4300),(0x3d89a0,0x4380)):
        a.call(0x80a4bd);a.emit('02');a.long(source);a.word(160);a.emit('80');a.word(dest)
    a.emit('a9 60 38');a.branch('80','heading_tiles')
    a.mark('heading_normal')
    for source,dest in ((0x440600,0x4300),(0x440700,0x4380)):
        a.call(0x80a4bd);a.emit('02');a.long(source);a.word(160);a.emit('80');a.word(dest)
    a.emit('a9 60 24')
    a.mark('heading_tiles');a.emit('a2 00 00')
    a.mark('heading_loop');a.emit('9f 4e 86 7e 18 69 10 00 9f 8e 86 7e 38 e9 0f 00 e8 e8 e0 14 00');a.branch('d0','heading_loop');a.emit('6b')
    code=a.finish()
    hooks={0x98004:(bytes.fromhex('22 ee db 88'),b'\x22'+(CODE+a.labels['init']).to_bytes(3,'little')),
           0x98111:(bytes.fromhex('a5 e8 30 1d'),b'\x5c'+(CODE+a.labels['input']).to_bytes(3,'little'))}
    return code,hooks

def heading(rom):
    from names import NameEditor,tile_bytes
    font=NameEditor(rom,0)
    rows=[left+[0]*3+right for left,right in zip(font.render('Growths'),font.render('%'))]
    canvas=[[0]*80 for _ in range(16)]
    for y,row in enumerate(rows):
        for x,pixel in enumerate(row):canvas[y][x+(80-len(row))//2]=2 if pixel==3 else 3 if pixel else 0
    return b''.join(tile_bytes(canvas,x,y) for y in range(2) for x in range(10))

def installed(rom):
    return version(rom)!=0

def version(rom):
    magic=bytes(rom.data[ARENA+rom.header:ARENA+rom.header+len(MAGIC)])
    return 2 if magic==MAGIC else 1 if magic==LEGACY_MAGIC else 0

def install(rom):
    code,hooks=program();before=bytes(rom.data)
    try:
        if version(rom)==2:raise ValueError('Display growth rates is already installed.')
        if version(rom)==1:uninstall(rom)
        if len(rom.data)-rom.header!=0x800000:raise ValueError('Requires the supported 8 MiB Project Naga beta 7 ROM.')
        verify_profile(rom)
        for address,(expected,new) in hooks.items():
            at=address+rom.header
            if bytes(rom.data[at:at+len(expected)])!=expected:raise ValueError(f'Incompatible or patched unit-screen code at PC {address:06X}.')
        block=bytes(rom.data[ARENA+rom.header:ARENA+rom.header+SIZE])
        if len(set(block))!=1 or block[0] not in (0,255):raise ValueError('Reserved patch storage is occupied.')
        payload=(MAGIC.ljust(16,b'\0')+bytes([block[0]])).ljust(0x100,b'\0')+code
        payload=payload.ljust(0x900,b'\0')+heading(rom)
        payload=payload.ljust(SIZE-32,bytes([block[0]]))
        payload+=hashlib.sha256(payload).digest()
        start=ARENA+rom.header;rom.data[start:start+len(payload)]=payload
        for address,(expected,new) in hooks.items():rom.data[address+rom.header:address+rom.header+len(new)]=new
    except Exception:rom.data[:]=before;raise

def uninstall(rom):
    if not installed(rom):raise ValueError('Display growth rates is not installed.')
    start=ARENA+rom.header
    block=bytes(rom.data[start:start+SIZE])
    if hashlib.sha256(block[:-32]).digest()!=block[-32:]:raise ValueError('Patch data has changed; restore a backup instead.')
    _,hooks=program()
    for address,(_,new) in hooks.items():
        if bytes(rom.data[address+rom.header:address+rom.header+len(new)])!=new:
            raise ValueError('Patch hooks have changed; restore a backup instead.')
    for address,(old,_) in hooks.items():rom.data[address+rom.header:address+rom.header+len(old)]=old
    rom.data[start:start+SIZE]=bytes([block[16]])*SIZE

def verify_profile(rom):
    # Compare executable routines, not editable character, class or growth data.
    for address,size,digest in PROFILE:
        data=bytes(rom.data[address+rom.header:address+rom.header+size])
        if hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError(f'Unsupported or modified status-screen code at PC {address:06X}. This patch supports Project Naga beta 7.')

PROFILE=(
    (0x98008,265,'164072e46128f015bc8d90f77652f8890c4b639e2fcc114ef5c09435523e8475'),
    (0x98115,64,'a69469c219466eb092a15f29193ddbb06feb2e57fc01e9acd43e69164ee9522e'),
    (0x8dbee,64,'089aca2de78be77976cf5e656769744616fda2bc788958e66bcb8ab3371d4e6a'),
    (0x99510,159,'60df13bef21cd1fd69e85b233378c581ecdc6f25a55f32211cd234d1188559d3'),
    (0x9970d,512,'70fa4bbf49c005443ef2bf48bec1408136bfa6d50ca0d043c5c248448adbde42'),
    (0x9a18c,96,'82462689cc8381f9d954681fecb5d5dc0b1e67681596fcecbf5675ce0b07820f'),
    (0x4a464,288,'cd346cc0a0c783b46abe988bf33df5b38a395c78251c1303a01911fa545b67fe'),
    (0xa4bd,96,'c585170b9d4491c8fd7f2bcfcb6c19384302185dfe64f9d4a40707d87d2abde8'),
    (0x440600,512,'27757bc14f63347e2f28673b6fb982405b558e01a4860f966da569c64c0074de'),
)

