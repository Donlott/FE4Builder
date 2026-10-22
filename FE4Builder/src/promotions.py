"""Character-ID promotion table, independent of character record layout."""
from rom import MODULES,load_module

TABLE=0x3833c  # Nightmare module 03853C includes the 512-byte copier header.


def character_id(module,values):
    field=next((i for i,f in enumerate(module.fields) if f.reference=='FE4 Character Numbers.txt'),None)
    if field is None:return None
    value=values[field]
    return value if 1<=value<=63 else None


def options():
    module=load_module(MODULES/'Character Editors'/'FE4 Promotion Editor.nmm')
    return module.fields[0].options


def address(rom,character):
    if not 1<=character<=63:raise ValueError('Promotions are available for playable character IDs 1–63.')
    return TABLE+rom.header+character-1


def plan(rom,module,draft,bound_id,value):
    if value not in options():raise ValueError('Promotion Class: choose a valid class or None.')
    if character_id(module,draft)!=bound_id:
        raise ValueError('Save and reload a changed character ID before editing its promotion class.')
    return address(rom,bound_id),value
