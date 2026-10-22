# Project Naga text investigation and implementation

## Root cause

The v0.2/v0.3 text model directly read ROM bytes, using vanilla character maps and
a catalog of fixed original dialogue addresses. The Japanese engine/name-loader
hashes it checked remained present in the expanded Project Naga ROM, so the check
accepted a layout it did not actually support. Japanese text still present in old
banks was then incorrectly offered as editable in-game text.

## Sources

- https://github.com/Miacidae/Project-Naga-beta-v7
- `Dialogue/Encodings.asm`: English character mapping and page selection.
- `Dialogue/ControlCodes.asm`: command widths, including world-map MovePortrait
  (85), whose operand size is three bytes.
- Chapter and miscellaneous `*Pointers.asm` files: locations of event pointers.
- `Dialogue/5-Chapter 5/Intermission Table.asm`: embedded dialogue pointers.
- `Dialogue/Others/*.asm`: fixed translated name/string locations.
- `MenuText/Tilemaps/Names.asm`: 16-byte primary name descriptors at 500000.
- `MenuText/_MenuTextInstaller.asm`: bitmap name storage, plus distinct menu copies.
- `Graphics/_GraphicsInstaller.asm`: dialogue font at 128000 and widths at 119971.

The catalog records the exact repository commit. The Naga build relocates some
text differently from the original beta ROM supplied by the user: for example,
its installation listing starts prologue text at 550A60, whereas the user's live
opening pointer resolves to 6015DC. Source assembly placement is therefore NOT
used as the dialogue location. The catalog contains 1,624 pointer sites plus
315 fixed translated resources. Runtime deduplication and discovery of inserted
text yield 1,802 resources in the tested ROM.

The primary ulti-mage/FireEmblem4 disassembly remains relevant for the base game,
but its Japanese glyph mapping and original script placements are insufficient
for Project Naga. Its old resource labels are not used as translated content.

## Runtime data

All file offsets here exclude the optional 512-byte copier header.

- Live intro pointer: 31809C -> bytes DC 15 60 -> CPU/file 6015DC.
- Opening text run: 6015EB -> English text decoded from its bytes.
- Castle character names: 505C00 + 16 * index, 63 slots.
- Primary menu descriptors: 500000 + 16 * index, 570 descriptors.
- Descriptor: width in 8-pixel columns, followed by a 24-bit graphics pointer.
  Other descriptor fields are preserved.
- Primary name bitmap storage: 520000–544FFF in the tested ROM, with aliases.
  Each allocation is 512 bytes: two 256-byte alignment buffers. Within each
  buffer, the width determines tile arrangement for a 16-pixel-high label;
  unused bytes are preserved on no-op and zeroed when regenerating that buffer.
- The second rendered variant is offset one pixel right. Width is not increased.
- English dialogue font: 128000; basic glyphs arranged as 16x16 glyph cells.
  Glyph advances come from the ROM at 119971.

The live ROM has multiple BF 00 00 50 / BF 01 00 50 load references in its expanded
menu routines (e.g. 510B09 and 510B16), corroborating use of the translated primary
menu descriptor table. The primary name bitmaps match the supplied Naga source
asset in the unedited test ROM. Their preview always reads the current ROM, not
that source asset. No OCR output is substituted for bitmap contents.

## Encoding and protection

The Naga profile is chosen before the Japanese one for the detected expanded
layout. A basic English-font fingerprint prevents guessing after an incompatible
font edit. English pages 09/0A use the documented mapping. Unknown glyphs/pages
are marked read-only; mixed-font passage changes are refused. Control codes,
operands and block ends are verified after writes. Interior entry points are
protected. Shared primary bitmap storage is rejected for independent edits.

Rewrites are address-stable. This avoids repointing events or invalidating
interior script branches. New long scenes, line-break changes, automatic global
renaming, and relocating shared bitmaps are not implemented. Some assembly-built
miscellaneous string references are not indexed; this is an indexed editor, not
a claim that every text-bearing byte in the translation has been identified.

## Evidence beyond matching source text

The test suite redirects the opening event's pointer in an in-memory ROM to
6F0000 and supplies different encoded text there. The model follows that pointer
and displays the different text while the legacy Japanese name table remains
unchanged. A separate save/reopen test rewrites the actual opening passage,
changes Sigurd's castle name and primary menu bitmap to Raddy, and verifies the
new output bytes, English text, control stream, checksums and all 248 portraits.
The edited temporary ROM is not shipped; only the editor is delivered.

Menu name copies in other interfaces (Names_Menus, Names_Question and other
screen assets) remain separate. The UI and README explicitly state that these
are not synchronized by editing a primary nameplate.
