# FE4Builder

A Python/Tkinter editor for Fire Emblem: Genealogy of the Holy War ROMs, inspired by FEBuilderGBA.

Edit characters, classes, equipment, armies, portraits, maps, dialogue and selected event commands. Includes backups and undo history, linked editors, an AI viewer, and external emulator launching. This is an early preview with feature-specific ROM compatibility checks.

## Run from source

Requires Python 3.10+ and Tkinter. No pip dependencies are needed.

- Windows: run `FE4Builder/scripts/Launcher.cmd`.
- Linux: install Python/Tkinter, then run `python3 FE4Builder/src/FE4Builder.py` from the repository root. Debian/Ubuntu packages: `python3 python3-tk`.

Select your own ROM at startup. Several text and graphics features require the 8 MiB Project Naga beta 7 layout. The editor supports ROMs with or without copier headers where the individual feature permits it.

Built-in music/SFX playback currently requires 64-bit Windows. Linux retains audio browsing and event command editing, but its GUI has not yet been verified on a Linux host. Configure a separately installed emulator for Save & Launch.

Read [the feature documentation](FE4Builder/README.md) before editing. Keep an untouched original ROM; Write to ROM overwrites the selected file using automatic backups and history.

## Build shareable packages

Run `python FE4Builder/scripts/build_release.py`. The `releases/` directory receives a Windows ZIP, a Linux tar.gz, and checksums. Both packages require Python/Tkinter and include launchers and setup instructions. Release archives are generated rather than committed.

## Tests

`python FE4Builder/scripts/run_tests.py test_release.py` checks packaging and clean startup without a ROM. Most other tests require a local reference Project Naga beta 7 ROM in the repository root and a graphical desktop; ROM fixtures are never distributed. Some developer tests also need research material excluded from this repository. The native audio checks require 64-bit Windows.

## Included material

No game ROMs, translation patches, saves, savestates, personal settings, backups or research downloads are included. FE4 Nightmare module attribution is in [Nightmare Modules/README.md](Nightmare%20Modules/README.md). The Windows Snes9x audio core has its own [license](FE4Builder/vendor/snes9x/LICENSE) and [source links](FE4Builder/vendor/snes9x/README.md), including non-commercial terms. Game-derived names and launcher artwork belong to their respective rights holders.

A project-wide source license has not yet been selected; third-party files retain their own terms.
