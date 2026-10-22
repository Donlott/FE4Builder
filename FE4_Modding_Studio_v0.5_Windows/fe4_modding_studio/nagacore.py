"""Project Naga text read from live ROM pointers, never source-script contents."""
from pathlib import Path
from dataclasses import dataclass
import json, re, hashlib
from PIL import Image
from textcore import ARGS, Run, Block, TextError

CAT=json.loads((Path(__file__).parent/'data/naga_catalog.json').read_text(encoding='utf-8'))
FONT={int(k):v for k,v in CAT['font'].items()}
REV={v:k for k,v in FONT.items()}
ARGS=dict(ARGS);ARGS[0x85]=3
PALETTE=[(24,24,32),(130,130,140),(255,255,255),(0,0,0)]

def address(pointer,size):
    bank=pointer>>16
    if 0x40<=bank<=0x7d: out=pointer
    elif 0x80<=bank<=0xff: out=pointer&0x3fffff
    else: raise TextError(f'Unsupported text pointer ${pointer:06X}')
    if out>=size:raise TextError('Text pointer outside ROM')
    return out

def detected(data):
    # Naga's translated name descriptor/graphics banks plus a live event pointer.
    if len(data)<0x600000:return False
    if hashlib.sha256(data[0x128000:0x129400]).hexdigest()=='329da5a56570f7574474c5b66e9c69c278b66c979c0bf10e61a7d17b4b642ce9':return True
    try:
        p=address(int.from_bytes(data[0x31809c:0x31809f],'little'),len(data))
        g=address(int.from_bytes(data[0x500001:0x500004],'little'),len(data))
        return p>=0x400000 and g>=0x400000 and 1<=data[0x500000]<=8
    except TextError:return False

def parse(data,start,label,path,limit=None):
    pos=start;page=9;runs=[];commands=[]
    stop=min(len(data),start+0x10000,limit or len(data))
    try:
        while pos<stop:
            if data[pos]>=9:
                begin=pos;before=page;chars=[];valid=True
                while pos<stop and data[pos]>=9:
                    c=data[pos];pos+=1
                    if c<=15:page=c
                    elif page in (9,10) and c in FONT:chars.append(FONT[c])
                    else:chars.append(f'⟦{page:02X}:{c:02X}⟧');valid=False
                runs.append(Run(begin,pos,before,page,''.join(chars),bytes(data[begin:pos]),valid))
                continue
            a=pos;c=data[pos];pos+=1
            if c==0:
                if pos>=stop:raise TextError('Truncated control code')
                c=data[pos];pos+=1
            if c not in ARGS:raise TextError(f'Unknown control code {c:02X} at {a:06X}')
            n=ARGS[c]
            if pos+n>stop:raise TextError('Truncated control operands')
            arg=bytes(data[pos:pos+n]);pos+=n;commands.append((a,pos,c,arg))
            if c==1:return Block(label,path,start,pos,runs,commands)
        raise TextError('No terminator within the supported resource boundary')
    except TextError as e:return Block(label,path,start,pos,runs,commands,str(e))

def encode(text):
    text=text.replace('’',"'").replace('“','"').replace('”','"').replace('…','...')
    out=bytearray();i=0
    options=sorted(REV,key=len,reverse=True)
    while i<len(text):
        c=next((c for c in options if text.startswith(c,i)),None)
        if c is None:raise TextError(f'Character {text[i]!r} is not in the supported Naga font. Line breaks are separate commands.')
        out.append(REV[c]);i+=len(c)
    return bytes(out)

def encode_run(run,text):
    if text==run.text:return run.raw,len(run.raw)
    if not run.editable:raise TextError('Unknown glyph/font page: this passage is read-only.')
    # A font switch within a passage can be meaningful; preserve it by refusing
    # mixed-font edits rather than silently flattening its appearance.
    pages={b for b in run.raw if 9<=b<=15}
    if len(pages)>1:raise TextError('Mixed-font passage: edit is disabled to preserve formatting.')
    target=next(iter(pages),run.before)
    raw=bytes([target])+encode(text)+bytes([run.after])
    if len(raw)>len(run.raw):
        # If the input font already matches, the initial command is redundant.
        if target==run.before:raw=raw[1:]
    if len(raw)>len(run.raw) and raw[-1]==run.after and target==run.after:raw=raw[:-1]
    used=len(raw)
    if used>len(run.raw):raise TextError(f'Needs {used} bytes; this passage has {len(run.raw)}. Shorten the passage.')
    return raw+bytes([run.after])*(len(run.raw)-used),used

def bitmap(raw,width,height):
    if width%8 or height%8 or len(raw)!=width*height//4:raise TextError('Invalid 2bpp image dimensions')
    im=Image.new('P',(width,height));im.putpalette(sum((list(c) for c in PALETTE),[])+[0]*756)
    for t in range(len(raw)//16):
        x0=t%(width//8)*8;y0=t//(width//8)*8
        for y in range(8):
            a,b=raw[t*16+2*y:t*16+2*y+2]
            for x in range(8):im.putpixel((x0+x,y0+y),((a>>(7-x))&1)|(((b>>(7-x))&1)<<1))
    return im

def pack_bitmap(im):
    w,h=im.size
    if w%8 or h%8:raise TextError('Image dimensions must be multiples of eight')
    raw=bytearray(w*h//4)
    for y in range(h):
        for x in range(w):
            v=im.getpixel((x,y))
            if not isinstance(v,int) or not 0<=v<4:raise TextError('Use an indexed PNG with palette indices 0–3.')
            a=((y//8)*(w//8)+x//8)*16+(y%8)*2
            raw[a]|=(v&1)<<(7-x%8);raw[a+1]|=((v>>1)&1)<<(7-x%8)
    return bytes(raw)

class NagaModel:
    profile='Project Naga'
    def __init__(self,rom):
        if not detected(rom.data):raise TextError('Project Naga layout not detected')
        if hashlib.sha256(rom.data[0x128000:0x129400]).hexdigest()!='329da5a56570f7574474c5b66e9c69c278b66c979c0bf10e61a7d17b4b642ce9':
            raise TextError('The English font differs from the verified Project Naga encoding. Text editing is disabled rather than guessing the displayed characters.')
        self.rom=rom;d=rom.data;self.run_changes={};self.name_changes={};self.image_changes={};self.blocks=[];self.references={};self.invalid=[]
        pending=[]
        for e in CAT['pointers']:
            a=e['pointer']
            try:
                target=address(int.from_bytes(d[a:a+3],'little'),len(d))
                if target<0x400000:raise TextError('Pointer does not select expanded translated text')
                pending.append((target,e['label'],e['path']))
                self.references.setdefault(target,[]).append(a)
            except TextError as error:self.invalid.append(f'{e["label"]}: {error}')
        for e in CAT['fixed']:pending.append((e['address'],e['label'],e['path']))
        seen=set()
        while pending:
            start,label,path=pending.pop(0)
            if start in seen:continue
            seen.add(start)
            b=parse(d,start,label,path)
            self.blocks.append(b)
            if not b.error:
                for a,end,c,arg in b.commands:
                    if c==0x2a:
                        try:
                            target=address(int.from_bytes(arg,'little'),len(d))
                            if target>=0x400000:
                                pending.append((target,f'Inserted_{target:06X}',f'Inserted text/{target:06X}'))
                                self.references.setdefault(target,[]).append(end-3)
                        except TextError:pass
        self.blocks.sort(key=lambda b:(b.path,b.start))
        self.runs={}
        starts=sorted(seen)
        for b in self.blocks:
            for r in b.runs:
                if any(r.start<s<r.end for s in starts):r.editable=False
                if not b.error:self.runs.setdefault(r.start,r)
        self.names=[]
        for i in range(63):
            a=0x505c00+i*16
            b=parse(d,a,f'Character {i+1:03X}','Character names',a+16)
            if b.error:raise TextError(f'Unsupported translated character name at {a:06X}')
            self.names.append(b)
        self.menu=[]
        for i,label in enumerate(CAT['menu_labels']):
            a=0x500000+i*16;width=d[a]
            try:
                p=address(int.from_bytes(d[a+1:a+4],'little'),len(d))
                if not 1<=width<=8 or not 0x520000<=p<=0x544e00:raise TextError('Invalid name bitmap')
                self.menu.append(dict(id=i,label=label,address=a,pointer=p,width=width))
            except TextError:self.menu.append(dict(id=i,label=label,address=a,error='Unsupported bitmap descriptor'))

    @property
    def dirty(self):return bool(self.run_changes or self.name_changes or self.image_changes)
    def name(self,i):
        if i in self.name_changes:return self.name_changes[i][1]
        return ''.join(r.text for r in self.names[i].runs)
    def stage_name(self,i,text):
        if not 0<=i<len(self.names):raise TextError('Invalid character name')
        raw=b'\x09'+encode(text)+b'\x01'
        if len(raw)>16:raise TextError('Castle dialogue name must fit its 16-byte slot (14 encoded glyphs).')
        raw=raw.ljust(16,b'\0');a=self.names[i].start
        if raw==bytes(self.rom.data[a:a+16]):self.name_changes.pop(i,None)
        else:self.name_changes[i]=(raw,text)
        return text
    def stage_run(self,run,text):
        if run.start not in self.runs:raise TextError('Unindexed/read-only passage')
        raw,used=encode_run(run,text)
        if raw==run.raw:self.run_changes.pop(run.start,None)
        else:self.run_changes[run.start]=(raw,text)
        return used
    def menu_image(self,i,shifted=False):
        e=self.menu[i]
        if 'error' in e:raise TextError(e['error'])
        raw=self.image_changes.get(i,bytes(self.rom.data[e['pointer']:e['pointer']+512]))
        start=256 if shifted else 0
        return bitmap(raw[start:start+e['width']*32],e['width']*8,16)
    def stage_image(self,i,im):
        e=self.menu[i]
        if 'error' in e:raise TextError(e['error'])
        if im.mode!='P' or im.size!=(e['width']*8,16):raise TextError(f'Use an indexed PNG sized {e["width"]*8} × 16, indices 0–3. Export first to obtain the correct palette.')
        original=bytes(self.rom.data[e['pointer']:e['pointer']+512])
        if pack_bitmap(im)==original[:e['width']*32]:
            self.image_changes.pop(i,None);return
        if any(im.getpixel((im.width-1,y)) for y in range(16)):raise TextError('Keep the last pixel column empty for the one-pixel alignment variant.')
        raw=pack_bitmap(im).ljust(256,b'\0')
        other=Image.new('P',im.size);other.paste(im,(1,0));raw+=pack_bitmap(other).ljust(256,b'\0')
        p=e['pointer']
        # Shared storage is explicitly blocked, rather than renaming other units.
        if any(j!=i and 'pointer' in x and max(p,x['pointer'])<min(p+512,x['pointer']+512) for j,x in enumerate(self.menu)):
            raise TextError('This bitmap shares storage with another menu entry; independent editing requires relocation.')
        if raw==bytes(self.rom.data[p:p+512]):self.image_changes.pop(i,None)
        else:self.image_changes[i]=raw
    def render_name(self,i,text):
        codes=encode(text);e=self.menu[i];w=e['width']*8;im=Image.new('P',(w,16));im.putpalette(sum((list(c) for c in PALETTE),[])+[0]*756);x=0
        for code in codes:
            if code==191:x+=4;continue
            if not 16<=code<=95:raise TextError('Menu rendering currently supports ASCII letters, digits and basic punctuation.')
            index=code-16;start=0x128000+(index//8)*512+(index%8)*32
            raw=bytes(self.rom.data[start:start+32])+bytes(self.rom.data[start+256:start+288])
            glyph=bitmap(raw,16,16);advance=self.rom.data[0x119971+index]
            for gy in range(16):
                for gx in range(16):
                    v=glyph.getpixel((gx,gy))
                    if v:
                        if x+gx>=w-1:raise TextError(f'Name does not fit this menu image ({w-1} pixels). Shorten it or edit its PNG.')
                        if v==1 or im.getpixel((x+gx,gy))!=1:im.putpixel((x+gx,gy),v)
            x+=advance
        return im
    def export(self):
        return dict(format='fe4-naga-text-v1',rom_sha256=self.rom.sha256,
                    names={str(k):v[1] for k,v in self.name_changes.items()},
                    passages={str(k):v[1] for k,v in self.run_changes.items()},
                    images={str(k):v.hex() for k,v in self.image_changes.items()})
    def import_project(self,obj):
        if obj.get('format')!='fe4-naga-text-v1' or obj.get('rom_sha256')!=self.rom.sha256:raise TextError('This project does not match the opened ROM.')
        old=(self.name_changes.copy(),self.run_changes.copy(),self.image_changes.copy())
        try:
            for k,v in obj['names'].items():self.stage_name(int(k),v)
            for k,v in obj['passages'].items():self.stage_run(self.runs[int(k)],v)
            for k,v in obj['images'].items():
                i=int(k)
                if not 0<=i<len(self.menu):raise TextError('Invalid bitmap ID')
                raw=bytes.fromhex(v);e=self.menu[i];w=e['width']
                if len(raw)!=512:raise TextError('Invalid image payload')
                self.stage_image(i,bitmap(raw[:w*32],w*8,16))
                if self.image_changes.get(i,bytes(self.rom.data[e['pointer']:e['pointer']+512]))!=raw:raise TextError('Invalid alignment variant')
        except Exception:
            self.name_changes,self.run_changes,self.image_changes=old;raise
    def apply(self,data):
        patches=[];log=[]
        for i,(raw,text) in self.name_changes.items():patches.append((self.names[i].start,raw,f'Naga castle name {i+1:03X}: {text}'))
        for a,(raw,text) in self.run_changes.items():patches.append((a,raw,f'Naga dialogue passage {a:06X}'))
        for i,raw in self.image_changes.items():patches.append((self.menu[i]['pointer'],raw,f'Naga menu name bitmap {i+1:03X}'))
        patches.sort();end=-1
        for a,raw,label in patches:
            if a<end:raise TextError('Overlapping edits: undo the passage or name edit that covers the same bytes.')
            end=a+len(raw)
            if bytes(data[a:end])!=bytes(self.rom.data[a:end]):raise TextError('Another editor changed these text bytes')
            data[a:end]=raw;log.append(label)
        name_ranges=[(self.names[i].start,self.names[i].start+16) for i in self.name_changes]
        for old in self.blocks:
            if old.error or any(a<=old.start<b for a,b in name_ranges):continue
            new=parse(data,old.start,old.label,old.path)
            if new.error or new.end!=old.end or new.commands!=old.commands:raise TextError(f'Control stream changed: {old.label}')
        return log
