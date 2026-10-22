"""Remember the last successfully opened ROM without automatically loading it."""
import json
import os
from pathlib import Path
import tempfile
from rom import DATA_DIR,ROOT

SETTINGS=DATA_DIR/'rom-selector.json'


def last_rom():
    try:
        data=json.loads(SETTINGS.read_text(encoding='utf-8'))
        value=data.get('last_rom','') if isinstance(data,dict) else ''
        return value if isinstance(value,str) and '\0' not in value else ''
    except (OSError,ValueError):return ''


def initial_directory(value):
    try:
        directory=Path(value).expanduser().parent if value else ROOT
        while not directory.is_dir() and directory!=directory.parent:directory=directory.parent
        return directory if directory.is_dir() else ROOT
    except (OSError,ValueError):return ROOT


def remember(path):
    value=str(Path(path).resolve())
    SETTINGS.parent.mkdir(parents=True,exist_ok=True)
    handle,temporary=tempfile.mkstemp(prefix='rom-selector-',suffix='.tmp',dir=SETTINGS.parent)
    try:
        with os.fdopen(handle,'w',encoding='utf-8') as out:
            json.dump({'last_rom':value},out,indent=2)
        os.replace(temporary,SETTINGS)
    finally:
        if Path(temporary).exists():Path(temporary).unlink()
    return value
