"""Create clean, ROM-free Windows/Linux source releases from explicit allowlists."""
import argparse,hashlib,io,json,tarfile,zipfile
from pathlib import Path

B=Path(__file__).resolve().parents[1]
VERSION='0.1.0-preview'
DATA=('ai','army_groups','audio','conversations','dialogue','event_commands','events','intro_assets','logo_layouts','objectives','reinforcements','villages')

WINDOWS=r'''@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "FE4Builder\scripts\start.py"
) else (
    python "FE4Builder\scripts\start.py"
)
if errorlevel 1 (
    echo.
    echo FE4Builder could not start. Install Python 3.10 or newer with Tcl/Tk.
    echo If using python.exe, enable Add Python to PATH in its installer.
    pause
)
'''
LINUX='''#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.10+ is required. See START_HERE.md." >&2
    exit 1
fi
exec python3 FE4Builder/scripts/start.py "$@"
'''
START='''"""Validate the local Python/Tk installation and start the portable editor."""
import runpy,sys
from pathlib import Path
if sys.version_info < (3,10):
    raise SystemExit('FE4Builder requires Python 3.10 or newer.')
try:
    import tkinter
except ImportError:
    raise SystemExit('Tkinter is missing. Linux: install your distribution python3-tk/python3-tkinter package. Windows: install Python with Tcl/Tk enabled.')
source=Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(source))
runpy.run_path(str(source/'FE4Builder.py'),run_name='__main__')
'''
SHORTCUT=r'''# Optional: create an icon-bearing Launcher shortcut after extracting/moving.
$ErrorActionPreference = 'Stop'
$releaseDirectory = Split-Path -Parent $PSScriptRoot
$shellObject = New-Object -ComObject WScript.Shell
$link = $shellObject.CreateShortcut((Join-Path $releaseDirectory 'Launcher.lnk'))
$link.TargetPath = Join-Path $releaseDirectory 'Launcher.cmd'
$link.WorkingDirectory = $releaseDirectory
$link.IconLocation = (Join-Path $releaseDirectory 'FE4Builder\assets\sigurd.ico') + ',0'
$link.Description = 'Launch FE4Builder'
$link.Save()
'''

def instructions(platform):
    setup=('''1. Install Python 3.10 or newer (64-bit recommended) with Tcl/Tk. Enable "Add Python to PATH" if using python.exe instead of the py launcher.
2. Extract the entire ZIP to a writable folder such as Documents. Do not run from inside the ZIP.
3. Double-click Launcher.cmd (shown as Launcher if extensions are hidden).
4. Optional: run scripts/CreateShortcut.ps1 in PowerShell to create a Launcher shortcut with the Sigurd icon. Regenerate it if you move the folder.
''' if platform=='Windows' else '''1. Install Python 3.10+ and Tkinter using your Linux distribution's package manager. Debian/Ubuntu: `sudo apt install python3 python3-tk`; Fedora: `sudo dnf install python3 python3-tkinter`. A graphical desktop session is required.
2. Extract the entire tar.gz archive to a writable folder.
3. Open a terminal in the extracted directory and run `./Launcher`. If executable permission was lost, use `chmod +x Launcher` or `sh Launcher`.
4. Alternatively: `python3 FE4Builder/scripts/start.py`.
''')
    return f'''# FE4Builder {VERSION} — {platform}

A portable source release of the FE4 ROM editor. Python is required; this package is not a standalone executable. No pip packages are needed. This preview was packaged on 2026-10-22.

## Start

{setup}
Open your own legally obtained FE4 ROM in the ROM selector. No ROM, emulator frontend, save, savestate or translation patch is included. Use Emulator settings to choose your own emulator for Save & Launch.

## Compatibility

The editor recognizes FE4 ROMs with and without a 512-byte copier header. Several graphics/text/patch features require the supported 8 MiB Project Naga beta 7 layout and reject other layouts. Opening a ROM does not imply every feature supports it.

Windows includes a 64-bit Snes9x core for built-in music/SFX previews. Linux supports the editors, audio catalogue/command editing and external emulator launch, but built-in music/SFX playback is unavailable. No Windows binary is shipped in the Linux package. Linux source compatibility has been reviewed; the Linux GUI has not been executed on a Linux host for this release.

## Saving and portability

Write to ROM overwrites the opened ROM using the editor's automatic backups and history. Keep your original ROM separately. Launching the app creates preferences and caches under FE4Builder/data; backups/history are stored alongside the ROM. Extract into a writable folder, not Program Files or /usr. Move the whole extracted directory together; keep Nightmare Modules beside FE4Builder. Your own ROM may live elsewhere.

This is a preview: event command editing currently supports verified Prologue scripts, and the AI Viewer is read-only. See FE4Builder/README.md for feature-specific limits and instructions.

## Package contents

FE4Builder/src, static data and icons; FE4 Nightmare modules and upstream attribution; platform launcher; documentation; RELEASE.json with file hashes. Research trees, tests requiring a reference ROM, screenshots, personal paths/preferences, ROMs, backups, saves and audio caches are excluded.

See THIRD_PARTY.md and the included notices for dependencies. SHA256SUMS.txt next to the download archives can be used to verify the downloads.
'''

THIRD='''# Included third-party material

FE4 Nightmare modules: original companion files are preserved under Nightmare Modules/FE4 Nightmare modules. Sources and upstream attribution are in Nightmare Modules/README.md. The separate DefaultFormat download and non-FE4 modules are not bundled.

Windows audio preview: unmodified Snes9x libretro core; original license and source/build links are under FE4Builder/vendor/snes9x. Its license includes non-commercial-use terms. The Linux package does not include this binary.

Python and Tcl/Tk must be installed separately; their runtimes are not bundled. Fire Emblem names and Sigurd launcher sprite are game-derived material belonging to their respective rights holders. This distribution includes no game ROM or translation patch. This packaging step does not assign a new license to the project's source code or relicense third-party files.
'''

def payload(platform):
    files={}
    def add(source,target):files[target]=source.read_bytes()
    for path in sorted((B/'src').glob('*.py')):add(path,'FE4Builder/src/'+path.name)
    for name in DATA:add(B/'data'/f'{name}.json','FE4Builder/data/'+name+'.json')
    for name in ('sigurd-standing.png','sigurd.ico'):add(B/'assets'/name,'FE4Builder/assets/'+name)
    add(B/'README.md','FE4Builder/README.md')
    modules=B.parent/'Nightmare Modules'/'FE4 Nightmare modules'
    for path in sorted(modules.rglob('*')):
        if path.is_file() and path.suffix.lower() in ('.nmm','.txt'):
            add(path,'Nightmare Modules/FE4 Nightmare modules/'+path.relative_to(modules).as_posix())
    add(modules.parent/'README.md','Nightmare Modules/README.md')
    if platform=='Windows':
        for name in ('LICENSE','README.md','snes9x_libretro.dll'):add(B/'vendor/snes9x'/name,'FE4Builder/vendor/snes9x/'+name)
        files['Launcher.cmd']=WINDOWS.replace('\n','\r\n').encode()
        files['scripts/CreateShortcut.ps1']=SHORTCUT.encode()
    else:files['Launcher']=LINUX.encode()
    files['FE4Builder/scripts/start.py']=START.encode()
    files['START_HERE.md']=instructions(platform).encode()
    files['THIRD_PARTY.md']=THIRD.encode()
    files['RELEASE.json']=(json.dumps(dict(version=VERSION,platform=platform,format='Python source / portable',python='3.10+',files={name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}),indent=2)+'\n').encode()
    return files

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);archives=[]
    for platform in ('Windows','Linux'):
        root=f'FE4Builder-{VERSION}-{platform}';files=payload(platform)
        if platform=='Windows':
            path=out/(root+'.zip')
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
                for name,data in sorted(files.items()):archive.writestr(root+'/'+name,data)
        else:
            path=out/(root+'.tar.gz')
            with tarfile.open(path,'w:gz') as archive:
                for name,data in sorted(files.items()):
                    info=tarfile.TarInfo(root+'/'+name);info.size=len(data);info.mode=0o755 if name=='Launcher' else 0o644;info.mtime=1792627200
                    archive.addfile(info,io.BytesIO(data))
        archives.append(path)
        print(path.name,len(files),'files',path.stat().st_size,'bytes')
    (out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in archives),encoding='utf-8')
    return archives

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=B.parent/'releases');args=parser.parse_args();build(args.out)
