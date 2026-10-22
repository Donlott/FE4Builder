"""Create a private environment beside the application; no global pip changes."""
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent

def main():
    if os.name != 'nt':
        raise RuntimeError('Run this setup on Windows.')
    if not (3, 10) <= sys.version_info[:2] < (3, 15):
        raise RuntimeError('Use Python 3.10 through 3.14 with Tcl/Tk. Python 3.13 is a suitable choice.')
    import tkinter
    if not (ROOT / '.venv' / 'Scripts' / 'python.exe').exists():
        print('Creating a private Python environment...')
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    python = ROOT / '.venv' / 'Scripts' / 'python.exe'
    subprocess.run([str(python), '-m', 'pip', 'install', '--only-binary=:all:',
                    '-r', str(ROOT / 'requirements.txt')], check=True)
    subprocess.run([str(python), '-c',
                    'import tkinter; from PIL import Image, ImageTk; '
                    'import core, textcore, nagacore, animationcore, repack; '
                    'print("Editor dependencies and data files loaded successfully.")'],
                   cwd=ROOT / 'fe4_modding_studio', check=True)
    print('\nSetup complete. Double-click Start Studio.bat.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nSetup failed:', exc)
        print('See README_WINDOWS.txt for installation and repair instructions.')
        sys.exit(1)
