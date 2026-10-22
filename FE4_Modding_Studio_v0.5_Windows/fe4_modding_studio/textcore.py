"""Conservative FE4 text editing: name-table repacking and address-stable dialogue."""
from pathlib import Path
from dataclasses import dataclass
import json,hashlib,re,unicodedata
DATA=Path(__file__).parent/'data'
def load(name):return json.loads((DATA/name).read_text(encoding='utf-8'))
MENU=load('menu_font.json');FONT=load('dialogue_font.json');CATALOG=load('dialogue_catalog.json');NAMES=load('name_labels.json')
MENU_REV={v:bytes.fromhex(k) for k,v in MENU.items()}
FONT_REV={}
for k,v in FONT.items():FONT_REV.setdefault(v,[]).append(tuple(int(x,16) for x in k.split(':')))
TABLE=0x39a59;POOL=0x39ecd;END=0x3adf5
class TextError(ValueError):pass
# Extended command operands, derived from SAFEGUARD/Dialogue.h.
ARGS={0:0,1:0,2:0,3:0,4:0,5:1,6:0,7:0,8:0,**{i:0 for i in range(9,16)},16:2,17:2,18:1,19:1,20:1,21:2,22:2,23:0,24:0,25:2,26:2,27:3,28:1,29:1,30:2,31:2,32:2,33:0,34:0,35:0,36:0,37:0,38:0,39:0,40:0,41:0,42:3,43:1,44:2,45:3,46:0,47:0,48:0,49:1,50:1,51:1,52:0,53:0,54:0,55:0,56:0,57:0,58:0,59:0,60:1,61:0,62:0,63:2,64:0,128:4,129:1,130:3,131:3,132:1,133:3,134:1,135:0}
COMMANDS={1:'END',2:'NEWLINE',3:'CLEAR',4:'SCROLL',5:'SIDE',6:'LEFT',7:'RIGHT',8:'WAIT',18:'SPEED',19:'MUSIC',20:'TEXT SOUND',29:'PAUSE',34:'UNIT1 NAME',35:'UNIT2 NAME',36:'SLOT PORTRAIT',37:'NUMBER1',38:'NUMBER2',39:'ITEM NAME',40:'CLASS NAME',41:'SCROLL ALL',42:'INSERT TEXT',44:'CHILD NAME',45:'CALL ASM',46:'UNIT1 PORTRAIT',47:'UNIT2 PORTRAIT',48:'SIBLING NAME',52:'SIBLING PORTRAIT',61:'OPEN BOX',62:'CLOSE BOX',63:'LOAD PORTRAIT',64:'UNLOAD PORTRAIT'}

@dataclass
class Run:
    start:int
    end:int
    before:int|None
    after:int|None
    text:str
    raw:bytes
    editable:bool=True
@dataclass
class Block:
    label:str
    path:str
    start:int
    end:int
    runs:list
    commands:list
    error:str=''

def read_names(data):
    values=[];positions=[]
    for i in range(570):
        p=TABLE+int.from_bytes(data[TABLE+i*2:TABLE+i*2+2],'little');positions.append(p)
        if not POOL<=p<END or (p-POOL)%2:raise TextError(f'Name {i+1:03X} points outside the supported name pool.')
        e=p
        while e+2<=END and data[e:e+2]!=b'\0\0':e+=2
        if e+2>END:raise TextError('Unterminated menu name.')
        values.append(bytes(data[p:e]))
    return values,positions

def decode_menu(raw):
    result=''
    for i in range(0,len(raw),2):
        k=raw[i:i+2].hex().upper();c=MENU.get(k,f'⟦{k}⟧')
        if len(c)==1 and ('Ａ'<=c<='Ｚ' or '０'<=c<='９'):c=unicodedata.normalize('NFKC',c)
        result+=c
    return result

def encode_menu(text):
    if '\n' in text or '\r' in text:raise TextError('A menu name must be a single line.')
    out=bytearray();pos=0
    while pos<len(text):
        m=re.match(r'⟦([0-9A-Fa-f]{4})⟧',text[pos:])
        if m:
            b=bytes.fromhex(m[1])
            if b==b'\0\0':raise TextError('Terminator cannot be part of a name.')
            out.extend(b);pos+=len(m[0]);continue
        c=text[pos];pos+=1
        if c.isascii() and c.isalpha():c=chr(ord(c.upper())+0xfee0)
        elif c.isascii() and c.isdigit():c=chr(ord(c)+0xfee0)
        elif c==' ':c='　'
        if c not in MENU_REV:raise TextError(f'Unsupported menu character: {c!r}')
        out.extend(MENU_REV[c])
    if len(out)>48:raise TextError('Maximum 24 menu glyphs; even shorter names can overflow a game window. Prefer 8 or fewer.')
    return bytes(out)

def parse_block(data,entry):
    start=entry['address'];pos=start;page=None;runs=[];commands=[]
    stop=min(len(data),(start//65536+1)*65536,start+0x8000)
    try:
        while pos<stop:
            if data[pos]>=9:
                begin=pos;before=page;chars=[];valid=True
                while pos<stop and data[pos]>=9:
                    c=data[pos];pos+=1
                    if c<=15:page=min(c,14)
                    elif page is None:chars.append(f'⟦??:{c:02X}⟧');valid=False
                    else:chars.append(FONT.get(f'{page:02X}:{c:02X}',f'⟦{page:02X}:{c:02X}⟧'))
                runs.append(Run(begin,pos,before,page,''.join(chars),bytes(data[begin:pos]),valid))
                continue
            p=pos;c=data[pos];pos+=1
            if c==0:
                if pos>=stop:raise TextError('Truncated extended command')
                c=data[pos];pos+=1
            if c not in ARGS:raise TextError(f'Unknown command {c:02X} at {p:06X}')
            n=ARGS[c]
            if pos+n>stop:raise TextError('Truncated command operands')
            operand=bytes(data[pos:pos+n]);pos+=n
            commands.append((p,pos,c,operand))
            if 9<=c<=15:page=min(c,14)
            if c==1:return Block(entry['label'],entry['path'],start,pos,runs,commands)
            # Inserted dialogue can change the font state; do not guess afterwards.
            if c in [34,35,39,40,42,44,48]:page=None
        raise TextError('No end command before the bank/length boundary')
    except TextError as e:return Block(entry['label'],entry['path'],start,pos,runs,commands,str(e))

def encode_run(run,text):
    if text==run.text:return run.raw,len(run.raw)
    if not run.editable:raise TextError('This passage inherits an unknown font page. It is read-only.')
    if '\n' in text or '\r' in text:raise TextError('Choose another passage for the next line. Newline/control commands stay fixed in this version.')
    page=run.before;out=bytearray();i=0
    while i<len(text):
        m=re.match(r'⟦([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})⟧',text[i:])
        if m:
            target,code=int(m[1],16),int(m[2],16);i+=len(m[0])
            if not 9<=target<=14 or code<16:raise TextError('Invalid glyph token')
        else:
            # Multi-character font symbols such as [n1] are preserved as one glyph.
            c=next((k for k in sorted(FONT_REV,key=len,reverse=True) if text.startswith(k,i)),None)
            if c is None:
                bad=text[i]
                if bad==' ':c='½'
                elif bad==',':c='､'
                elif bad=='!':c='！'
                elif bad=='?':c='？'
                else:raise TextError(f'Character {bad!r} is absent from the vanilla dialogue font. Lowercase English needs a font patch; use UPPERCASE or Japanese.')
                consumed=1
            else:consumed=len(c)
            options=FONT_REV[c];target,code=next((v for v in options if v[0]==page),options[0]);i+=consumed
        if target!=page:out.append(target);page=target
        out.append(code)
    if run.after is None:raise TextError('Unknown final font state')
    if page!=run.after:out.append(run.after)
    used=len(out)
    if used>len(run.raw):raise TextError(f'Text needs {used} bytes; this passage has {len(run.raw)}. Shorten it. Moving story commands is not supported yet.')
    # Font-select commands are invisible and restore the original ending state.
    out.extend([run.after]*(len(run.raw)-used))
    return bytes(out),used

class TextModel:
    def __new__(cls,rom):
        if cls is TextModel:
            from nagacore import detected,NagaModel
            if detected(rom.data):return NagaModel(rom)
        return super().__new__(cls)
    def __init__(self,rom):
        self.rom=rom;d=rom.data
        if hashlib.sha256(d[0x118a01:0x1198ab]).hexdigest()!='d934d12e146a36aab79d1e62d2465aea7bf6eb61344a7fbf6d5b4ab9dc2e84a0':raise TextError('Dialogue engine differs from the tested Japanese FE4 profile.')
        if hashlib.sha256(d[0x484f6:0x48540]).hexdigest()!='873006229c7d61dcb9835ddddb1d55eddd4a2fb6789de4fc5b1d7954765271a8':raise TextError('Name loader differs from the supported profile.')
        self.names,self.positions=read_names(d);self.name_changes={};self.run_changes={}
        self.blocks=[parse_block(d,x) for x in CATALOG]
        # Editing a run crossed by a named entry point could alter its inherited font.
        starts={b.start for b in self.blocks}
        for b in self.blocks:
            for run in b.runs:
                if any(run.start<s<run.end for s in starts):run.editable=False
        self.runs={r.start:r for b in self.blocks if not b.error for r in b.runs}
        self.initial_fingerprint=hashlib.sha256(bytes(d[TABLE:END])).hexdigest()
    @property
    def dirty(self):return bool(self.name_changes or self.run_changes)
    def name(self,i):return decode_menu(self.name_changes.get(i,self.names[i]))
    def stage_name(self,i,text):
        if not 0<=i<len(self.names):raise TextError('Invalid menu name ID')
        previous=self.name_changes.get(i)
        raw=encode_menu(text)
        if raw==self.names[i]:self.name_changes.pop(i,None)
        else:self.name_changes[i]=raw
        try:self.name_patch()
        except Exception:
            if previous is None:self.name_changes.pop(i,None)
            else:self.name_changes[i]=previous
            raise
        return decode_menu(raw)
    def name_patch(self):
        values=[self.name_changes.get(i,v) for i,v in enumerate(self.names)]
        unique={};pool=bytearray();table=bytearray()
        # Deduplicate identical names, but never force aliases to remain linked.
        for raw in values:
            if raw not in unique:unique[raw]=POOL+len(pool);pool.extend(raw+b'\0\0')
            table.extend((unique[raw]-TABLE).to_bytes(2,'little'))
        if len(pool)>END-POOL:raise TextError(f'Name pool needs {len(pool)} bytes; capacity is {END-POOL}. Shorten one or more names.')
        return bytes(table),bytes(pool),values
    def stage_run(self,run,text):
        raw,used=encode_run(run,text)
        if raw==run.raw:self.run_changes.pop(run.start,None)
        else:self.run_changes[run.start]=(raw,text)
        return used
    def apply(self,data):
        log=[]
        if self.name_changes:
            if bytes(data[TABLE:END])!=bytes(self.rom.data[TABLE:END]):raise TextError('Another edit overlaps the name table.')
            table,pool,values=self.name_patch();data[TABLE:POOL]=table;data[POOL:END]=pool+bytes(END-POOL-len(pool))
            if read_names(data)[0]!=values:raise TextError('Name-table verification failed')
            log.append(f'Text: {len(self.name_changes)} menu name entries; {len(pool)}/{END-POOL} pool bytes')
        changes=[]
        for start,(raw,text) in sorted(self.run_changes.items()):
            run=self.runs[start]
            if bytes(data[start:run.end])!=run.raw:raise TextError('Overlapping text/portrait edits detected')
            if any(start<e and run.end>s for s,e in changes):raise TextError('Overlapping dialogue edits')
            data[start:run.end]=raw;changes.append((start,run.end))
            log.append(f'Text passage {start:06X}, {len(raw)} bytes (commands unmoved)')
        # Every indexed resource must keep its command stream and endpoints.
        for old in self.blocks:
            if old.error:continue
            new=parse_block(data,{'address':old.start,'label':old.label,'path':old.path})
            if new.error or new.end!=old.end or new.commands!=old.commands:raise TextError(f'Control-code verification failed: {old.path}')
        return log
