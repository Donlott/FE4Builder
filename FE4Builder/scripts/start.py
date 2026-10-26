"""Portable source launcher; no current-working-directory assumptions."""
import runpy,sys
from pathlib import Path
if sys.version_info<(3,10):raise SystemExit('FE4Builder requires Python 3.10 or newer.')
try:
    import tkinter as tk
except ImportError:raise SystemExit('Tkinter is missing. Ubuntu: sudo apt install python3-tk. Windows: install Python with Tcl/Tk.')
source=Path(__file__).resolve().parents[1]/'src'
sys.path.insert(0,str(source))
try:runpy.run_path(str(source/'FE4Builder.py'),run_name='__main__')
except tk.TclError as error:
    if 'display' in str(error).lower():raise SystemExit('A graphical desktop is required. For smoke tests use xvfb-run -a python3 FE4Builder/scripts/run_tests.py --portable.')
    raise
