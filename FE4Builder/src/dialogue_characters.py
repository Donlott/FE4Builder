"""Character IDs used by ordinary dialogue portrait commands."""
import re
from rom import MODULES,lines,number,character_modules

PORTRAIT=re.compile(r'\[Portrait\s+([0-9a-fA-F]{1,4})\]')

def portrait_command_at(text,offset,selection=None):
    """Only target the command under the caret or the one explicitly selected."""
    for match in PORTRAIT.finditer(text):
        if selection:
            start,end=selection
            hit=start<match.end() and end>match.start() and not text[start:match.start()].strip() and not text[match.end():end].strip()
        else:hit=match.start()<=offset<match.end()
        if hit:return match.start(),match.end(),int(match[1],16)
    return None

def character_choices(app):
    result={}
    for line in lines(MODULES/'Character Editors/FE4 Character Numbers.txt')[1:]:
        value,name=line.split(None,1);result[number(value)]=(name,None)
    for module in character_modules():
        for index in range(module.count):
            values={field.name:value for field,value in zip(module.fields,app.rom.values(module,index))}
            identity=values.get('Char no.')
            if identity is not None:result[identity]=(app.record_name(module,index),values.get('Class'))
    return result
