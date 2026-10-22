"""Lossless Project Naga dialogue codec and copy-on-write scene storage."""
import hashlib
import json
import re
from rom import DATA_DIR
from portraits import pc_address,pointer_for

def catalogue():return json.loads((DATA_DIR/'dialogue.json').read_text(encoding='utf-8'))

SIMPLE={1:'End',3:'Clear',4:'Scroll',5:'Control05',6:'Left',7:'Right',8:'Wait',9:'Start',10:'Slim'}
EXTENDED={
    0x01:('EndCommand',()),0x02:('NoOp02',()),0x05:('SetSide',(1,)),
    0x10:('MoveTextOnScreen',(1,1)),0x12:('TextSpeed',(1,)),0x13:('ChangeMusic',(1,)),
    0x14:('ChangeTextSound',(1,)),0x18:('OtherWaitForA',()),0x19:('MoveTextInBox',(1,1)),
    0x1a:('SetVRAMAddress',(2,)),0x1c:('AddSpace',(1,)),0x1d:('PauseText',(1,)),
    0x22:('PrintStoredNameA',()),0x23:('PrintStoredNameB',()),0x24:('LoadStoredPortraitA',()),
    0x25:('PrintStoredNumberA',()),0x26:('PrintStoredNumberB',()),0x27:('PrintStoredItem',()),
    0x28:('PrintStoredClass',()),0x29:('ScrollBoth',()),0x2a:('PrintDialogue',(3,)),
    0x2b:('MusicFadeOut',(1,)),0x2c:('PrintBranchingName',(2,)),0x2d:('RunASM',(3,)),
    0x2e:('LoadStoredPortraitB',()),0x2f:('LoadStoredPortraitC',()),0x30:('PrintStoredNameC',()),
    0x31:('PlaySFX31',(1,)),0x32:('PlaySFX32',(1,)),0x33:('PlaySFX',(1,)),
    0x34:('LoadSiblingPortrait',()),0x3d:('OpenBox',()),0x3e:('CloseBox',()),
    0x3f:('Portrait',(2,)),0x40:('ClearPortrait',()),
    0x80:('LoadMapSymbol',(1,1,1,1)),0x81:('ClearMapSymbol',(1,)),
    0x82:('LoadPortraitWM1',(1,2)),0x83:('LoadPortraitWM2',(1,1,1)),
    0x84:('ClearPortraitWM',(1,)),0x85:('MovePortraitWM',(1,1,1)),
    0x86:('HighlightCountry',(1,)),0x87:('ClearHighlight',()),
}
GLYPHS={int(k):v for k,v in catalogue()['glyphs'].items()}
ENCODE={v:k for k,v in GLYPHS.items()}
ALIASES={'’':"'",'“':'"','”':'"','\u00a0':' '}


def decode(data,start=0,limit=16384):
    parts=[];at=start
    end=min(len(data),start+limit)
    while at<end:
        value=data[at];at+=1
        if value==2:parts.append('\n')
        elif value in SIMPLE:
            parts.append('['+SIMPLE[value]+']')
            if value==1:return ''.join(parts),at-start
        elif 0x0b<=value<=0x0f:parts.append(f'[Font {value:02X}]')
        elif value==0:
            if at>=end or data[at] not in EXTENDED:raise ValueError(f'Unsupported dialogue command at PC {at-1:06X}.')
            name,sizes=EXTENDED[data[at]];at+=1
            if at+sum(sizes)>end:raise ValueError('Truncated dialogue command.')
            args=[]
            for size in sizes:
                args.append(f'{int.from_bytes(data[at:at+size],"little"):0{size*2}X}');at+=size
            parts.append('['+' '.join([name]+args)+']')
            if name=='EndCommand':return ''.join(parts),at-start
        elif value in GLYPHS:parts.append(GLYPHS[value])
        else:parts.append(f'[Glyph {value:02X}]')
    raise ValueError('No dialogue end found within the supported script limit.')


def encode(text):
    text=text.rstrip('\n')
    output=bytearray();at=0
    commands={name:(code,sizes) for code,(name,sizes) in EXTENDED.items()}
    simple={name:code for code,name in SIMPLE.items()}
    while at<len(text):
        char=text[at]
        if char=='[':
            end=text.find(']',at)
            if end<0:raise ValueError('An opening control tag has no closing ].')
            words=text[at+1:end].split();at=end+1
            if not words:raise ValueError('Empty control tag.')
            name,args=words[0],words[1:]
            if name in simple and not args:
                output.append(simple[name])
                if name=='End' and at!=len(text):raise ValueError('[End] must be the last tag; remove text after it.')
            elif name in ('Font','Glyph') and len(args)==1:
                try:value=int(args[0],16)
                except ValueError:raise ValueError('Font/Glyph arguments must be hexadecimal.')
                if name=='Font' and not 0x0b<=value<=0x0f or name=='Glyph' and not 0x10<=value<=255:
                    raise ValueError('Unsupported Font/Glyph byte.')
                output.append(value)
            elif name in commands:
                code,sizes=commands[name]
                if len(args)!=len(sizes):raise ValueError(f'{name} requires {len(sizes)} hexadecimal argument(s).')
                output.extend((0,code))
                for arg,size in zip(args,sizes):
                    try:value=int(arg,16)
                    except ValueError:raise ValueError(f'{name}: use hexadecimal arguments.')
                    if not 0<=value<1<<(size*8):raise ValueError(f'{name}: argument is outside its byte range.')
                    if name in ('TextSpeed','ChangeTextSound') and value==0:raise ValueError(f'{name} cannot be zero.')
                    output.extend(value.to_bytes(size,'little'))
            else:raise ValueError(f'Unknown or malformed control tag [{" ".join(words)}].')
        else:
            at+=1
            if char=='\n':output.append(2)
            elif char in ENCODE or char in ALIASES:output.append(ENCODE[ALIASES.get(char,char)])
            else:raise ValueError(f'Unsupported character {char!r}. Use supported letters or a control tag.')
    if not output or output[-1]!=1:raise ValueError('Dialogue must finish with [End].')
    if len(output)>16384:raise ValueError('Dialogue is larger than the 16 KiB scene limit.')
    # End bytes inside arguments must not be mistaken for the script end.
    _,size=decode(output)
    if size!=len(output):raise ValueError('Dialogue has bytes after its end.')
    return bytes(output)


def readable(text):
    text=re.sub(r'\[(Wait|OtherWaitForA|Scroll|ScrollBoth|Clear|Left|Right)\]', '\n\n',text)
    text=re.sub(r'\[(PrintStored\w+|PrintBranchingName)([^]]*)\]',r'{\1}',text)
    return re.sub(r'\n{3,}','\n\n',re.sub(r'\[[^]]*\]','',text)).strip('\n')


def check_profile(rom):
    if len(rom.data)-rom.header!=0x800000:raise ValueError('Dialogue editing supports the 8 MiB Project Naga beta 7 ROM.')
    if hashlib.sha256(rom.data[0x118a00+rom.header:0x118b00+rom.header]).hexdigest()!='c5727d978dc04556b61eeb3034f46f3889d0dd66a9ad119a9d203f0448359696':
        raise ValueError('The dialogue engine does not match the supported Project Naga beta 7 profile.')


class Dialogue:
    def __init__(self,rom,entry):
        check_profile(rom)
        self.rom,self.entry=rom,entry
        from villages import resolve_dialogue_ref
        self.ref=resolve_dialogue_ref(rom,entry['address'])+rom.header
        self.pointer=bytes(rom.data[self.ref:self.ref+3])
        self.start=pc_address(int.from_bytes(self.pointer,'little'))
        if not 0x400000<=self.start<0x7e0000:raise ValueError('This scene pointer does not match the translated dialogue layout.')
        self.text,self.length=decode(rom.data,self.start+rom.header)
        self.raw=bytes(rom.data[self.start+rom.header:self.start+rom.header+self.length])

    def write(self,text):
        payload=encode(text)
        if payload==self.raw:return []
        from villages import resolve_dialogue_ref
        if resolve_dialogue_ref(self.rom,self.entry['address'])+self.rom.header!=self.ref:
            raise ValueError('The village event moved this scene reference. Reload before writing.')
        if bytes(self.rom.data[self.ref:self.ref+3])!=self.pointer or bytes(self.rom.data[self.start+self.rom.header:self.start+self.rom.header+self.length])!=self.raw:
            raise ValueError('This scene changed outside the editor. Reload before writing.')
        # Preserve executable callbacks and nested-script references. Editing
        # their destinations needs a script/event editor and ownership tracking.
        protected=lambda s:re.findall(r'\[(?:RunASM|PrintDialogue)\b[^]]*\]',s)
        if protected(text)!=protected(self.text):raise ValueError('Keep existing RunASM and PrintDialogue tags unchanged.')
        from dialogue_storage import plan
        edits=plan(self,payload)
        for address,data in edits:self.rom.data[address+self.rom.header:address+self.rom.header+len(data)]=data
        return [f'{self.entry["group"]}: {self.entry["label"]}',f'Dialogue bytes: {len(self.raw)} → {len(payload)}; private text allocation']


def preview(rom,text,page=0):
    """Text-only preview with native glyphs; do not simulate script side effects."""
    lines=readable(text).splitlines() or ['']
    pages=max(1,(len(lines)+2)//3);page=min(page,pages-1)
    rows=[[0]*256 for _ in range(64)];widths=[]
    for line_number,line in enumerate(lines):
        x=8
        for char in line:
            code=ENCODE.get(ALIASES.get(char,char),ENCODE['?'])
            index=code-0x10
            advance=rom.data[0x119971+index+rom.header]
            if not 1<=advance<=16:advance=8
            if page*3<=line_number<page*3+3:
                tile=(index//8)*32+(index%8)*2
                for y in range(16):
                    for column in range(16):
                        at=rom.header+0x128000+(tile+(y//8)*16+column//8)*16+(y%8)*2
                        low,high=rom.data[at:at+2]
                        pixel=((low>>(7-column%8))&1)+2*((high>>(7-column%8))&1)
                        if pixel and x+column<248:
                            rows[8+(line_number%3)*16+y][x+column]=pixel
            x+=advance
        widths.append(x-8)
    return rows,pages,sum(width>240 for width in widths)
