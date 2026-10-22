# FE4 Modding Studio 0.5 — Portrait storage optimization

Native Linux editor for FE4 Archanea: portraits, text and animation assignments.
No ROM is included. Open your latest Hero-fix v2 ROM to retain those fixes.

## Launch on Pop!_OS / Ubuntu

Install dependencies once, if needed:

```bash
sudo apt install python3 python3-tk python3-pil python3-pil.imagetk
```

Extract the ZIP, open a terminal in `fe4_modding_studio`, and run:

```bash
bash run.sh
```

Python 3.10+, Tkinter, Pillow and ImageTk are required. Older distro Pillow is
supported. No pip installation or Internet access is needed to run the editor.

## Repack portrait storage

Import your portrait replacements, click **Preview packing…**, enable
**Optimize portrait storage when saving**, and save a ROM copy. Smaller sheets
can now fund larger ones across the portrait pool. Identical graphics share one
allocation. Unknown gaps and unrelated data remain untouched.

The first preview may take around a minute. Read `PORTRAIT_REPACKING.md` for
storage boundaries, shared palettes, and the limitation on rediscovering unused
tails after reopening a saved copy. Stage a batch before saving for best results.

## Corrected text reading

Click **Names & story…**. Your ROM now selects the **Project Naga** interface.
The old editor read leftover Japanese ROM data using vanilla disassembly
addresses and character maps. It did not simply display a source text file,
but those bytes were not the translation's active text. Its compatibility check
failed to detect that distinction. Do not use the old Japanese text editor to
edit your Project Naga ROM.

The new reader follows current event pointers and decodes the English bytes at
their destinations. Source files provide reference labels, pointer locations and
encoding rules only; no English story script is bundled as display content.
Fixed translated name slots are read directly from their ROM locations.

On the supplied Hero-fix v2 ROM, 1,802 indexed translated resources parse without
errors. As a concrete check, the event pointer at headerless `31809C` contains
`DC 15 60`, selecting `6015DC`. The opening passage starts at `6015EB` and reads:
“Milady, the castle is completely surrounded!”

## English dialogue and story

1. Open **English dialogue & story** and search for English text or a scene label.
2. Select a resource. The context displays actual ROM text and fixed commands.
   The sidebar shows the resolved ROM address and pointer locations.
3. Select a passage, rewrite it, and click **Stage passage**.
4. Use **Save ROM copy…** and test the new file in your emulator.

Uppercase/lowercase English and the documented Naga characters are supported.
Passages must fit their current byte allocation. Shorter passages are padded
with invisible font-selection commands. Line breaks, event/portrait commands,
pointers and resource endpoints remain fixed. This release does not relocate
scripts or add new lines. Unknown glyphs or unsupported mixed-font passages are
protected. The context is not a rendered dialogue-window preview.

## Names: choose the intended in-game representation

Project Naga has separate systems; a rename is not automatically global.

- **Castle dialogue names:** 63 actual translated slots. Edit the displayed name
  and stage it. Each has 16 bytes including font selection and terminator, leaving
  up to 14 encoded glyphs. These do not change literal story mentions.
- **Menu name graphics:** 570 primary nameplate descriptors. Reference labels
  identify original entries; they are not OCR and are not presented as current
  text. The preview displays the actual ROM pixels. Type a short name and render
  it using the ROM font, or export/edit/import an indexed PNG. Both alignment
  variants are updated. New text must fit the original width; shared bitmap
  allocations are protected rather than overwriting other entries.
- **Literal mentions in story:** use English search and edit the relevant passages.

**Remaining limitation:** the primary nameplate editor does not update the
separate pre-rendered name copies in other menu screens or Valkyrie text. Those
copies require their own graphics editing. This version is not a global rename
feature. The primary nameplate renderer currently supports ASCII letters,
digits and basic punctuation; PNG import permits custom artwork.

PNG imports must retain the exported dimensions, indexed mode, and indices 0–3.
Keep the last column empty for the one-pixel alignment variant. The preview uses
an illustrative grayscale palette; game palette selection remains unchanged.

## Staging and projects

Click **Stage** before changing selections; unstaged typing is not saved.
Closing the text window retains staged changes in the current ROM session.
**Save edit project…** writes Naga edits to JSON. Load it against the exact same
input ROM, checked by SHA-256. Legacy Japanese text projects cannot be imported
into the Naga editor. **Save ROM copy…** combines portrait, text and animation
edits without overwriting the input ROM.

## Existing features

Portrait editing retains older-Pillow compatibility, unlocked-palette detection,
and the shared-portrait fix: identical fitting replacements for slots 00/F6 can
be written once with both pointers retained. See `PORTRAITS.md`.

**Animations…** edits existing battle assignments, map profiles, movement
selectors, and positioning/timing records. See `ANIMATIONS.md`. The separately
installed Hero fixes are retained when saving text edits; this tool does not
install them into an older ROM automatically.

## Validation and limits

Six Naga tests cover live pointer following, English decoding, byte-identical
no-op saves, passage budgets, control preservation, character names, name bitmap
round trips, alias protection, transactional edit projects, overlap rejection,
headerless input, checksum updates, and preservation of all portraits and
unrelated bytes. Animation integration tests also cover combined saves.

```bash
python3 test_text.py /path/to/FE4_Archanea_Hero_Hand_Axe_Test_v2.smc
python3 test_animation.py /path/to/FE4_Archanea_Hero_Hand_Axe_Test_v2.smc
```

Tests use temporary copies. Test expectations are specific to the supplied ROM.
No emulator combat/dialogue or interactive GUI test was performed here. Verify
text width and the edited representations in-game. Unknown engine/layout changes
may need another profile; this is not a universal FE4 translation editor.

See `NAGA_TEXT_ANALYSIS.md` for provenance and addresses. `TEXT_ANALYSIS.md`
describes the legacy Japanese format, not your ROM's active translated text.
