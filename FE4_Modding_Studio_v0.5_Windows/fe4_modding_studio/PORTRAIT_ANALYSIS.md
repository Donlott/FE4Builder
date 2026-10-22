# FE4 modding-tool analysis — portrait foundation

Analysis date: 22 October 2026.

## Scope and confidence

This is a focused reverse-engineering and implementation pass for portrait editing, plus a source-based survey of the requested larger editor. It is **not a complete disassembly or exhaustive semantic audit of this 8 MiB hack**. Portrait read/write behaviour is verified against the actual supplied ROM and independent community image assets. Other subsystems below are a grounded implementation roadmap; they are not yet editable or fully validated in this hack.

The archive contains 17,879 entries with 124,222,435 uncompressed bytes. It mixes FE4 documentation, tools, graphics, patches, fan hacks, duplicated material and some FE5-specific material. It cannot safely be treated as one uniform specification. Japanese text was decoded as UTF-8 where valid, otherwise CP932, and relevant portrait notes were read in Japanese. No bundled Windows programs or third-party patches were executed or applied.

## Primary source

[ulti-mage/FireEmblem4](https://github.com/ulti-mage/FireEmblem4), cloned commit **387b2e4c63b72b0d3f2854eaa69f26946d83b383**.

Principal files consulted:

- `SRC/Decompressor.asm`: decompressor at CPU $80:AA02; command semantics and unusual source-bank traversal.
- `SRC/Bank8A.asm`: portrait-ID resolution, graphics and palette table lookups, dialogue decompression.
- `SRC/Dialogue.asm`: portrait DMA size and tilemap assembly, particularly $91:96F9 and $91:9739.
- `SRC/Bank8B.asm`: world-map portrait transfer and shared colour handling.
- `TABLES/PortraitGraphicPointers.csv`, `TABLES/PortraitPalettePointers.csv`, `TABLES/CHARACTER/PortraitDataIDs.csv`.
- `build.asm`: authoritative source placement and named data tables.
- `SAFEGUARD/Characters.h`, `Classes.h`, `Items.h` and corresponding character/class/item CSV tables.
- `SRC/Events.asm`, `TEXT/`, `EVENTS/`, `TOOLS/FE4c2a.py`: initial survey for later modules.

The project explicitly identifies itself as a partial disassembly. Undisassembled functions and hack-specific changes remain separate research work. The tool implements its own Python codec and image handling rather than shipping the disassembly or requiring a ROM rebuild.

## Actual supplied ROM

| Property | Observed value |
|---|---|
| File bytes | 8,389,120 |
| Copier header | 512 bytes |
| ROM body | 8,388,608 bytes (8 MiB) |
| Mapping byte at headerless $00FFD5 | $35, ExHiROM |
| SHA-256 of complete supplied file | `895f6a646c68600848367dd65c4a772b58d7c069520e4372b0f3f58074983e0c` |
| Portrait slots | 248 ($00–$F7) |
| Distinct graphics addresses | 152 |
| Distinct palette addresses | 221 |
| Changed graphics pointers versus the disassembly | 0 |
| Changed palette pointers versus the disassembly | 0 |
| Existing stored checksum | $5D7C |
| Byte sum of current 8 MiB ROM body | $AE8E |

The old checksum does not describe the current body. Actual modified saves recalculate the checksum/complement in both HiROM/ExHiROM header locations while preserving the copier header and file length. A no-change export/import returns the original bytes unchanged, including its existing checksum.

The first portrait visibly contains Marth artwork, although the original slot reference is Sigurd. This is why UI names are labelled as original FE4 references and previews, not names, are the reliable guide to the hack's content.

## Portrait structures and addressing

All offsets below exclude the 512-byte copier header. Add $200 to compare with the archive's headered file offsets.

| Structure | CPU address | Headerless file offset | Format |
|---|---|---|---|
| Graphics pointer table | $8A:B4F9 | $0AB4F9 | 248 × 3-byte little-endian pointers |
| Palette pointer table | $8A:B7E1 | $0AB7E1 | 248 × 3-byte little-endian pointers |
| First graphics stream | $CA:65B5 | $0A65B5 | FE4 compressed graphics |
| First palette | $8C:A800 | $0CA800 | 16 × 16-bit SNES colour words |
| Character portrait assignments | $8B:9A88 | $0B9A88 | Separate assignment table; not changed here |

Portrait slots and character IDs are different concepts. The loader also has a class-portrait fallback for portrait ID $F3. Replacing a slot changes every character assigned to that slot; isolating graphics sharing does not create a new character-to-slot assignment.

Each stream decodes to 64 SNES 4-bpp tiles, 32 bytes per tile: **2,048 bytes**. A raw tile viewer shows 128×32 pixels. The main portrait is 48×64; 16 additional tiles make two 16×32 animation regions.

For raw tile row `r` (0–3) and column `c` (0–15), the editable sheet maps tiles as follows:

| Raw column | Destination tile position in the 64×64 sheet |
|---|---|
| 0–5 | x = c×8; y = r×8 |
| 6–11 | x = (c−6)×8; y = 32+r×8 |
| 12–13 | x = 48+(c−12)×8; y = r×8 |
| 14–15 | x = 48+(c−14)×8; y = 32+r×8 |

The left 48 pixels are assembled from the same 6-column/four-row blocks used by the disassembled dialogue tilemap builder. Import/export does not change animation placement logic.

### Compression

The decoder handles literal runs, nibble reconstruction, doubled bytes, fixed-byte prefix/suffix pairs, output backreferences, long/short repeated-byte runs, compressed-input lookbacks, and end markers. The encoder emits a validated subset sufficient for arbitrary portrait data: literals, doubled bytes, prefix/suffix pairs, RLE and short/long LZ references. A dynamic-programming choice minimizes encoded size among those supported choices; it is not a claim of globally optimal compression over every FE4 command.

The decoder traverses successive 32 KiB windows while retaining the starting half of a 64 KiB bank. Thus a lower-half stream at $xx7FFF continues at the next bank's $0000, skipping the intervening upper half. A high-half stream continues at the next bank's $8000. Treating this as ordinary linear file data corrupts portraits crossing a boundary.

Compressed-input lookbacks can read bytes from another stream. Consequently, pointer equality alone is insufficient for sharing protection. The tool records all source bytes actually read and checks those dependencies before an in-place write. It verifies every slot after patching, not just the selected slot.

### Colour handling

Colours are SNES 15-bit RGB stored little-endian. The supplied ROM retains the common-grey behaviour documented in the archive. Index $0E is overridden with $35AD in relevant display paths, so an importer must not assign an arbitrary colour there and expect consistent display. Index zero is transparent. The other 14 palette indices remain available.

Palette words are treated as colours; the current editor does not interpret them as animation-position metadata. Any future animation-position editor needs separate tracing of the animation routines.

## Japanese documentation cross-checks

Relevant paths within the supplied archive:

1. `FE4 ツール、資料系 - Tools, Reference Materials/FE4-十二魔将弄り(FE-Void氏) - FE4-Twelve Demon Generals (FE-Void)/顔No.とヘッダ - Face number and header.txt` — portrait-ID, graphics-pointer and palette-pointer cross-reference. Its first graphics-table entry is headered $0AB6F9, agreeing with headerless $0AB4F9 above.
2. `FE4 構造体パッチ等々 - FE4 structure patch etc./通常用構造体 - Normal structure/顔グラフィック格納表・バイナリデータ - Face graphic storage table-binary data.txt` — default graphics extents, palette locations and bank-crossing warning. Its practical recommendation is to use unused storage for new graphics and keep backups.
3. `バグフォグラムズ資料 - Bugfograms material/パッチ集 - patch collection/共通パレット解除 - Common palette cancellation/顔グラ共通パレット解除 - Unlock common palette for face graphics.txt` — documents the common colour and five patch sites. All five original byte sequences were present in the supplied ROM. The editor leaves them unchanged.
4. `FE4 プログラム、画像改変パッチ系 - Programs, Asset stuff/FE4,5 顔グラ画像系 - FE4,5 Face graph image system/FE4顔グラ - FE4 face graphics/` — independent compressed `.bin` and 128×32 `.bmp` assets used for codec validation. All 25 matched pairs checked decoded to exactly the BMP's pixel indices.

The archive's `.chr` files in that particular portrait collection are 32-byte palettes; extension names alone are not a reliable description of asset contents.

## Saving strategy

The editor first attempts a replacement inside the selected stream's exclusive existing source bytes. It rejects this route when the replacement grows beyond known storage or touches another portrait's dependencies. A user-designated blank allocation region then allows relocation and independent palette storage. CPU pointers are updated only for the changed slot.

For expanded ExHiROM, allocations above 4 MiB are mapped through banks $40–$7D. Banks $7E/$7F are WRAM, so the final 128 KiB of an 8 MiB file cannot simply be used as directly addressed graphics storage. New streams stay within a single 32 KiB window. No automatic mapper patch or ROM expansion is attempted.

A blank range is not automatically free space. This version validates known portrait ownership but cannot rule out computed references from unrelated code/events. It therefore requires explicit reservation. $690000–$698000 is blank in the supplied test ROM and was used only in temporary integration-test copies. It is not declared permanently available for later versions of the project.

## Groundwork for the larger modding tool

| Module | Source-grounded structure | Consequence for implementation |
|---|---|---|
| Character stats | Character offset table at $03ADF5; records at $03B267 in the original layout; static, dynamic and enemy schemas in `Characters.h` | Record type matters. Fixed personal stats/growths, inherited children and generated enemies cannot use one flat editor. Read actual pointers and record types before writing. |
| Class stats | Offset table $038F35; class data $038FC5; class records are $1F bytes | Includes bases, growths, ten weapon ranks, movement/type, terrain bonus, 16-bit class skills and money. A data-grid editor is feasible after validating the hack's records. |
| Weapons/items | Offset table $03E9D0; data $03EAE4; common item record $0A bytes, weapon/staff record $13 bytes | Names/type, durability, cost, bonuses, rank and skills precede weapon attributes. Player-item instance IDs and weapon-definition IDs must remain distinct. |
| Skills | Separate unit skill bytes, 16-bit class skill flags, and item skill flags | Toggling existing skills is data editing. New effects or altered activation rules require assembly analysis and controlled code patches. Unknown bits must be preserved. |
| Text | Separate menu text and dialogue resources; dialogue commands and conversion tool in the disassembly | Must preserve control codes, pointers, encoding, font support and width/layout. This hack's actual text encoding cannot be assumed to match vanilla Japanese. |
| Events | `SRC/Events.asm`, `EVENTS/` chapter scripts, plus Japanese command descriptions | Build a parser that round-trips unknown commands and preserves references before offering structured changes. Map events and dialogue are related but not interchangeable formats. |
| Maps | Terrain data, tile graphics, map layouts, chapter changes and event/unit coordinates are separate concerns | A PNG paint editor is insufficient. First build a read-only renderer, then lossless layout editing, then integrate terrain, objects and event-coordinate validation. This pass does not establish a complete map codec. |

These original addresses are research anchors, not blanket permission to overwrite a patched ROM. A later editor should use explicit ROM profiles, a central allocation ledger, change history, source fingerprints and per-module validation. The current Python codec and ROM/image separation provide a starting point, but they do not yet constitute that full framework.

Recommended implementation order after this portrait test release: validate desktop/emulator behaviour; improve portrait animation workflows and allocation tracking; character/class/item tables; existing skill flags; text decoding/round trips; event inspector; map renderer and editor; custom skill code patches.

## Test coverage and outstanding validation

The package's automated suite checks known codec command vectors; generated streams; both source-bank boundary cases; invalid streams; export/import identity across all 248 slots; recompression of every distinct decoded graphic; shared-graphics relocation; shared-palette isolation; headerless input; checksum/header/file-length preservation; RGB transparency conversion; and input-file protection.

Independent community BMP comparison is an additional external oracle for the decoder. This caught and resolved a nibble-mode interpretation error during development; self-round-trip tests alone would not have established correctness.

No game emulator was available for in-game testing. No graphical display server was available for interactive Tkinter testing. Code compilation, data-level integration tests and image inspections were performed. Emulator and desktop validation remain explicit release limitations. Keep this as version 0.1 until dialogue animation, status portraits and other display contexts have been exercised in the actual game.
