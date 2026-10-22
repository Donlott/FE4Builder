# FE4 Portrait Studio 0.1

A small native Linux portrait editor for Fire Emblem: Genealogy of the Holy War. Tested at the binary/data level against the supplied **FE4 Archanea – Headered.smc** project ROM. This release edits portraits only; stats, maps, skills, text and event editors are future modules.

## Start on Pop!_OS / Ubuntu

Extract this ZIP to a folder. Install the dependencies once:

```bash
sudo apt install python3 python3-tk python3-pil python3-pil.imagetk
```

Open a terminal in the extracted folder and run:

```bash
bash run.sh
```

No Wine, Windows executables, network connection, pip environment or compiled extension is required. Other Linux distributions need Python 3.10+, Tkinter, Pillow and Pillow's ImageTk support.

## Replace a portrait

1. **Open ROM…** and select your `.smc` or `.sfc` file.
2. Select a portrait slot. Search accepts a hex ID or an original FE4 reference name. Names are not your hack's character names; use the visual preview to identify the right slot.
3. **Export PNG…** to obtain its complete 64×64 sheet.
4. Edit that PNG in GIMP. The left 48×64 is the main portrait. The right 16×64 holds two 16×32 animation regions. Keep the complete sheet dimensions and edit the animation region consistently with the face.
5. **Import PNG…** to stage the replacement. Inspect the portrait and full-sheet previews. You can stage several slots; **Undo slot** restores one.
6. **Save ROM copy…** to write a separate ROM. The opened ROM cannot be overwritten by the editor.
7. Test the copy in your emulator: dialogue/talking frames, status screen, world-map portraits and combat presentation. Keep your original project ROM.

**A 48×64 image alone is intentionally rejected.** It does not contain the animation tiles. This version does not generate animation frames, move the animation region, resize artwork or invent missing pixels. The full PNG sheet is the input format.

## Colours and transparency

SNES colours use 5 bits per channel, so RGB colours are rounded to console precision. FE4's original common-colour logic remains enabled in the supplied ROM: index 0 is transparent, index 14 is shared grey ($35AD), and the remaining 14 indices are editable colours.

- Exported indexed PNGs preserve their indices, including duplicate palette colours. Keep index 0 transparent and index 14 grey.
- RGB/RGBA PNGs are supported. RGBA transparency must be completely transparent or completely opaque.
- For completely opaque RGB images, the top-left colour is the transparent background key throughout the image. Use RGBA if that colour must also appear as opaque artwork.
- If too many colours remain after SNES conversion, import stops unless **Allow colour reduction** is selected. Inspect the reduced preview before saving.
- The editor preserves the on-ROM index-14 word; FE4's runtime common grey is used for preview/export. It does not apply a global palette-unlock patch.

## When a replacement needs more space

Smaller replacements can reuse their own existing compressed storage if no other portrait reads the affected bytes. Otherwise the editor needs a region that you designate as unused. This also isolates shared graphics and palettes, so editing one slot does not change other slots.

Use **Reserve space…** and enter a **headerless** hexadecimal range, with an exclusive end. For example, `690000-698000` is uniformly zero-filled in the supplied 8 MiB test ROM. This is a candidate, not proof that your project has reserved it for portraits. Confirm ownership against your project's allocation map before using it. The editor checks blankness, mapping, internal headers, portrait tables, palettes and compressed references; it cannot prove that unrelated event/code data never references a blank region.

Reservations apply to the currently opened input and current save. Reopen a saved ROM before continuing a separate editing session, and select a new unused region if more allocation is required. The editor will reject already populated ranges. It never automatically expands or changes the ROM mapper.

## Verification and limits

- All 248 slots in the supplied ROM decode to 2,048 bytes each.
- Every exported sheet can be reimported without binary changes.
- Encoder tests cover every distinct portrait in that ROM.
- Save verification re-decodes **every** slot and compares graphics and palettes with expected results; unchanged slots must remain unchanged.
- Shared-graphics and shared-palette tests use an isolated saved copy and reopen it.
- Headerless input, copier-header preservation, bank crossings, transparency, malformed streams, source overwrite protection and checksum updates are tested.
- Decoder output additionally matched 25 independently supplied community BMPs pixel-for-pixel.

**Not emulator-tested here.** A graphical display server was unavailable, so the Tkinter window could not be interactively exercised in this environment. The GUI source compiles and uses the tested core, but first-run desktop/UI testing remains necessary. This is an initial test release, not a claim of universal compatibility with FE4 hacks.

The supported profile expects FE4's original 248-slot pointer tables and loader. Hacks that relocate tables, rewrite graphics compression, unlock common palettes or change portrait layout need a profile update. Common-grey preview assumes the original behaviour. The editor does not modify character-to-portrait assignments or add new slots.

## Included files

- `studio.py`: native GUI.
- `core.py`: ROM, image, allocation and saving logic.
- `codec.py`: FE4 decompression and compression.
- `cli.py`: optional command-line interface.
- `test_core.py`: repeatable codec and ROM integration tests.
- `ANALYSIS.md`: English findings, sources, future-editor design and limitations.
- `rom_audit.json`: facts recorded from the supplied test ROM.

The package contains no game ROM. Original FE4 names identify reference slots, not current project identities.

## Optional command line

Slot numbers are hexadecimal; addresses exclude a copier header.

```bash
python3 cli.py '/path/to/game.smc' export 00 portrait_00.png
python3 cli.py '/path/to/game.smc' import 00 portrait_00.png '/path/to/game_edited.smc'
python3 cli.py '/path/to/game.smc' import 00 portrait_00.png '/path/to/game_edited.smc' --reserve 690000-698000
python3 test_core.py '/path/to/your/test-rom.smc'
```

The integration tests' relocation cases expect the supplied test ROM's blank `690000-698000` region. They create only temporary copies and never alter the supplied ROM. For another ROM, use the codec-only tests (`python3 test_core.py`) or adapt the integration fixture.
