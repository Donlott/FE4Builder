# FE4Builder

Donlot was here!

A Python/Tkinter editor for Fire Emblem: Genealogy of the Holy War ROMs, inspired by FEBuilderGBA.

Edit characters, classes, equipment, armies, portraits, maps, dialogue and selected event commands. Includes backups and undo history, linked editors, an AI viewer, and external emulator launching. This is an early preview with feature-specific ROM compatibility checks.

## Run from source

Requires Python 3.10+ and Tkinter. No pip dependencies are needed.

- Windows: run `FE4Builder/scripts/Launcher.cmd`.
- Ubuntu 22.04: run `sh "Setup Ubuntu.sh"`, then `sh Launcher.sh`. See [LINUX.md](LINUX.md) for optional audio and testing instructions.

Select your own ROM at startup. Several text and graphics features require the 8 MiB Project Naga beta 7 layout. The editor supports ROMs with or without copier headers where the individual feature permits it.

Built-in music/SFX playback supports 64-bit Windows and a Linux backend using a separately installed Snes9x libretro core plus paplay/aplay/ffplay. Ubuntu GUI/audio verification still needs a native run; ROM-free CI checks are configured for Ubuntu 22.04 and Windows. Configure a separately installed emulator for Save & Launch.

Read [the feature documentation](FE4Builder/README.md) before editing. Keep an untouched original ROM; Write to ROM overwrites the selected file using automatic backups and history.

## Build shareable packages

Run `python FE4Builder/scripts/build_release.py`. The `releases/` directory receives a Windows ZIP, a Linux tar.gz, and checksums. Both packages require Python/Tkinter and include launchers and setup instructions. Release archives are generated rather than committed.

## Tests

`python FE4Builder/scripts/run_tests.py --portable` checks platform handling, packaging and clean startup without a ROM. On headless Linux, prefix it with `xvfb-run -a`. Most other tests require a local reference Project Naga beta 7 ROM in the repository root and a graphical desktop; ROM fixtures are never distributed. Some developer tests also need research material excluded from this repository. The legacy native audio snapshot tests require 64-bit Windows; the portable suite tests Linux process control without playing sound.

## Included material

No game ROMs, translation patches, saves, savestates, personal settings, backups or research downloads are included. FE4 Nightmare module attribution is in [Nightmare Modules/README.md](Nightmare%20Modules/README.md). The Windows Snes9x audio core has its own [license](FE4Builder/vendor/snes9x/LICENSE) and [source links](FE4Builder/vendor/snes9x/README.md), including non-commercial terms. Game-derived names and launcher artwork belong to their respective rights holders.

A project-wide source license has not yet been selected; third-party files retain their own terms.


## FE4 Modding Studio v0.5 — separate project snapshot

[FE4_Modding_Studio_v0.5_Windows](FE4_Modding_Studio_v0.5_Windows/) preserves the contributed FE4 Modding Studio project alongside FE4Builder while integration is in progress. The two applications remain separate; FE4Builder's existing launchers and release packages are unchanged.

The Studio snapshot includes its original source, data catalogues, documentation, regression tests, setup script and Windows launchers. For its portrait storage optimization, Project Naga text and animation tools, follow [README_WINDOWS.txt](FE4_Modding_Studio_v0.5_Windows/README_WINDOWS.txt). On Windows, run **Setup Windows.bat** in that folder first, then **Start Studio.bat**. It has its own pinned Pillow dependency and local virtual environment; see [LINUX.md](LINUX.md) for separate Ubuntu setup/launch scripts. FE4Builder's dependency instructions do not apply to it.

Local virtual environments, Python caches, build outputs and game files are excluded. The snapshot is stored for collaboration and future integration; adding it does not validate its ROM-writing behavior or change the original project's terms.
