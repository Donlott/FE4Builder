FE4 Modding Studio v0.5 - Windows package
=======================================
Portraits, portrait storage optimization, Project Naga text, animation assignments.
No ROM is included. Use your own latest working project ROM.

QUICK START
1. Extract ALL files from the ZIP into a writable folder such as Documents.
   Do not launch files while they are still inside the ZIP.
2. Install desktop Python 3.10-3.14 from https://www.python.org/downloads/windows/
   Python 3.13 is a suitable choice. Include Tcl/Tk, pip, and the Python launcher
   (or enable Add Python to PATH). Do not use the minimal embeddable ZIP.
3. Double-click Setup Windows.bat. Internet is needed to install Pillow.
   It creates a private .venv folder here, without changing global packages.
4. Double-click Start Studio.bat. Normal use then works offline.
5. Open your ROM and save edits to a separate ROM copy.

The launcher keeps a console open behind the editor so errors can be copied.
Setup does not need Administrator privileges in a writable folder.
Target: Windows 10/11 with desktop Python and Tcl/Tk.

SHARING
Send this entire ZIP to your friend. They follow the quick-start steps above.
Do not include your local .venv folder: Python environments are not portable.
If you move the extracted folder after setup, delete only .venv and rerun setup.

OPTIONAL: BUILD AN EXE ON WINDOWS
After setup, double-click Build EXE.bat. This downloads PyInstaller and builds:
  dist\FE4_Modding_Studio\FE4_Modding_Studio.exe
Test opening a ROM, portraits, text, animations and saving a copy, then ZIP the
ENTIRE dist\FE4_Modding_Studio folder to share it. Keep its _internal folder.
The recipient of that built folder does not need to install Python.
Build again after changing source code. This download itself contains no .exe.
The executable is not signed. Follow your computer's security policy.

FEATURE NOTES
Import your portrait replacements, click Preview packing, enable Optimize
portrait storage when saving, then save a ROM copy. Stage replacements as a
batch before saving to make the most of the available portrait storage.
The first packing preview can take a minute or more.
Full documentation is in fe4_modding_studio, especially PORTRAIT_REPACKING.md,
NAGA_TEXT_ANALYSIS.md and ANIMATIONS.md. The README's apt/run.sh instructions
are Linux-specific; use the Windows launchers provided here instead.

TROUBLESHOOTING
- Python not found: enable the launcher or PATH option in Python setup.
- tkinter missing: modify/repair desktop Python to install Tcl/Tk and IDLE.
- Pillow download fails: check internet/proxy access and run setup again.
- Multiple Python versions: from this folder use py -3.13 setup_windows.py
  (substitute the version you installed).
- If .venv is broken, delete only .venv and rerun Setup Windows.bat.
- Keep ROMs outside the application folder if you replace/delete the app later.
- A known input ROM can be opened on either platform; saves stay copies.

VALIDATION
The application code and bundled data were checked in the Linux build host.
Catalog reads explicitly use UTF-8 for Windows compatibility. The existing
v0.5 ROM regression tests are included. Windows batch launchers, the Windows
GUI, and the optional EXE build could not be run on this host; this is not a
Windows-tested standalone executable. Please test a copy of the ROM first.

Sources for packaging instructions:
https://docs.python.org/3.12/using/windows.html
https://pillow.readthedocs.io/en/stable/installation/basic-installation.html
https://pyinstaller.org/en/stable/usage.html
