# Ubuntu 22.04 development and testing

FE4Builder uses Python 3.10+ and Tkinter, available on Ubuntu 22.04. It does not need Wine, a Windows Python installation or pip dependencies. Keep the complete repository, including Nightmare Modules, together in a writable folder.

## First setup and launch

From a fresh clone:

```sh
git clone https://github.com/Donlott/FE4Builder.git
cd FE4Builder
sh "Setup Ubuntu.sh"
sh Launcher.sh
```

The setup script installs Python, Tkinter, venv, Xvfb and xauth through apt, using sudo. It does not open or modify a ROM. Alternatively install `python3 python3-tk` yourself, then run `python3 FE4Builder/scripts/start.py`. Launching needs a desktop session; Xvfb is for automated checks. Shell scripts use LF line endings and locate their files relative to themselves, so paths containing spaces work.

Select your own compatible ROM at startup. The normal editor features and ROM-layout restrictions apply on both systems. Backups and history remain beside your ROM; preferences/cache stay under FE4Builder/data. Mouse wheel and Shift+wheel work in canvases on X11 (Button 4/5), as well as Windows-style wheel events. The Army form and open comboboxes keep their original scrolling restrictions. Linux case-sensitive ROM paths have distinct UI contexts and history identities.

## Built-in music/SFX previews (optional)

Ubuntu 22.04 provides `libretro-snes9x` in multiverse and `pulseaudio-utils` for paplay:

```sh
sudo apt install libretro-snes9x pulseaudio-utils
```

If apt cannot locate the core, enable the multiverse repository in Ubuntu Software & Updates first. The editor detects the Snes9x core under system libretro directories and RetroArch's per-user core directory. For a manually installed native core, set its absolute path before launching:

```sh
FE4BUILDER_AUDIO_CORE=/absolute/path/snes9x_libretro.so sh Launcher.sh
```

Core architecture must match 64-bit Python. Do not point Linux at the Windows DLL. Audio plays through paplay, aplay or ffplay; a desktop audio session must be running. Missing optional components disable preview playback with an explanation while leaving audio browsing/event editing available. Linux rendering uses the same isolated libretro worker and read-only ROM snapshot as Windows. System core versions can produce different previews; actual Ubuntu native playback still requires validation on your computer. No new core binary is distributed here.

Package references: https://packages.ubuntu.com/jammy/libretro-snes9x and https://packages.ubuntu.com/jammy/pulseaudio-utils .

## Testing changes together

```sh
git pull --ff-only
xvfb-run -a python3 FE4Builder/scripts/run_tests.py --portable
```

The portable suite needs no ROM. It checks clean GUI startup, module paths with exact casing, Linux wheel handling, audio process control, package integrity and extracted-package startup. The `Windows and Ubuntu portable checks` GitHub Actions workflow runs these checks on ubuntu-22.04 and Windows when pushed or when a pull request is opened. Until the workflow runs, a local Windows result is not proof of an Ubuntu GUI pass.

For ROM integration checks, put your own Project Naga beta 7 reference ROM in the repository root and run a selected test file, for example:

```sh
xvfb-run -a python3 FE4Builder/scripts/run_tests.py test_group_load.py
```

Some development tests require research fixtures not included in GitHub. Windows-native sound-driver/snapshot tests are Windows-specific. Never upload the ROM or local environments. Test gameplay with your preferred Linux SNES emulator; Emulator settings accepts Linux executables/scripts and discovers snes9x, snes9x-gtk or bsnes from PATH. Flatpak emulators can be configured with /usr/bin/flatpak and one argument per line (including run, application ID and {rom}); give the emulator access to the ROM's folder.

## Separate FE4 Modding Studio snapshot

Its own Pillow dependency is separate from FE4Builder:

```sh
cd FE4_Modding_Studio_v0.5_Windows
sh "Setup Ubuntu.sh"
sh "Start Studio.sh"
```

This creates `.venv-linux`, leaving any Windows `.venv` alone. It uses the snapshot's existing requirements.txt. These launchers do not merge the applications or validate the snapshot's ROM-writing behavior.
