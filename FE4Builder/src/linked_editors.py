"""Resolve field references to exact editor records, including inventory slots."""
from rom import MODULES,load_module,class_modules

REFERENCES={'FE4 Classes.txt','FE4 Player Equipment.txt','FE4 Weapon List.txt'}

def field_target(rom,field,value):
    if field.reference=='FE4 Classes.txt':
        module=class_modules()[0]
        if not 0<=value<module.count:
            raise ValueError('This class ID has no editable class record.')
        return 'Class Editor',module.name,value
    if field.reference not in REFERENCES:
        return None
    if value==255:
        return None
    if field.reference=='FE4 Player Equipment.txt':
        if not 1<=value<=142:
            raise ValueError('This equipment slot is outside the player item table.')
        module=load_module(MODULES/'Item Editors'/'FE4 Player Weapon Editor.nmm')
        value=rom.data[rom.address(module,0)+value-1]
        if value==255:
            return None
    if 0<=value<0x6a:
        name,index='FE4 Weapon/Staff Editor 1',value
    elif 0x6a<=value<0x7a:
        name,index='FE4 Ring Editor',value-0x6a
    elif 0x7a<=value<=0x88:
        name,index='FE4 Weapon/Staff Editor 2',value-0x7a
    elif value==0x89:
        name,index='FE4 Circlet Editor',0
    else:
        raise ValueError('This item ID has no supported item editor.')
    return 'Item Editor',name,index
