"""Persistent emulator configuration and argument-safe process launching."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from rom import DATA_DIR

SETTINGS=DATA_DIR/'emulator.json'

def default_config():
    candidates=[Path(r'C:\Games\Snes\snes9x-x64.exe'),Path(r'C:\Games\Snes\snes9x.exe')]
    executable=next((str(p) for p in candidates if p.is_file()),'')
    return {'executable':executable,'arguments':['{rom}']}

def load_config(path=SETTINGS):
    path=Path(path)
    if not path.exists():return default_config()
    try:config=json.loads(path.read_text(encoding='utf-8'))
    except (ValueError,OSError) as error:raise ValueError('Cannot read emulator settings: '+str(error))
    if not isinstance(config,dict) or not isinstance(config.get('executable'),str) or not isinstance(config.get('arguments'),list) or not all(isinstance(a,str) for a in config['arguments']):
        raise ValueError('Emulator settings must contain an executable path and an argument list.')
    return {'executable':config['executable'],'arguments':config['arguments']}

def command(config,rom_path):
    executable=Path(config['executable']).expanduser()
    rom=Path(rom_path).resolve()
    if not config['executable'] or not executable.is_file():raise ValueError('Choose an existing emulator executable in Emulator settings.')
    if not rom.is_file():raise ValueError('The ROM file does not exist.')
    arguments=config.get('arguments',['{rom}'])
    if not isinstance(arguments,list) or not all(isinstance(a,str) and '\0' not in a for a in arguments):raise ValueError('Invalid emulator argument list.')
    result=[str(executable.resolve())]+[arg.replace('{rom}',str(rom)) for arg in arguments]
    if not any('{rom}' in arg for arg in arguments):result.append(str(rom))
    return result

def save_config(config,path=SETTINGS):
    executable=Path(config['executable']).expanduser()
    if not config['executable'] or not executable.is_file():raise ValueError('Choose an existing emulator executable.')
    normalized={'executable':str(executable.resolve()),'arguments':config['arguments']}
    if not isinstance(normalized['arguments'],list) or not all(isinstance(a,str) and '\0' not in a for a in normalized['arguments']):raise ValueError('Use one emulator argument per line.')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    handle,temporary=tempfile.mkstemp(prefix='emulator-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(handle,'w',encoding='utf-8') as out:
            json.dump(normalized,out,indent=2);out.write('\n')
        os.replace(temporary,path)
    finally:
        if Path(temporary).exists():Path(temporary).unlink()
    return normalized

def launch(config,rom_path):
    argv=command(config,rom_path)
    # Pass paths as individual arguments; never invoke a shell command string.
    return subprocess.Popen(argv,cwd=str(Path(argv[0]).parent),shell=False)
