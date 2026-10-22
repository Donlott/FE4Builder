# Text implementation findings

Primary source: [ulti-mage/FireEmblem4](https://github.com/ulti-mage/FireEmblem4), examined locally at commit `387b2e4c63b72b0d3f2854eaa69f26946d83b383`. Relevant files are `SAFEGUARD/Dialogue.h`, `TEXT/DIALOGUE/Dialogue.h`, `SAFEGUARD/MenuText.h`, `TABLES/OFFSET/CharacterNameOffsets.csv`, `labels.txt`, `build.asm` and the files under `TEXT/DIALOGUE`. The supplied Japanese community archive and test ROM were used alongside the disassembly. Bundled JSON data records source-derived glyph mappings, reference labels and resource locations; it contains no ROM image.

## Test input

The supplied file has a 512-byte copier header and an 8 MiB ExHiROM payload. Full-file SHA-256: `895f6a646c68600848367dd65c4a772b58d7c069520e4372b0f3f58074983e0c`. All offsets below exclude that copier header.

## Menu names

The table at `039A59` contains 570 little-endian 16-bit offsets relative to the table base. Its string pool is `039ECD`–`03ADF5` (exclusive), 3,880 bytes. Strings are two-byte menu-font codes terminated by `0000`; these are not the dialogue encoding.

Repacking the input's logical names with deduplication uses 2,994 bytes, leaving 886 bytes. The editor regenerates all name offsets after an edit, allowing formerly shared names to diverge. It validates every decoded result against the intended name bytes before saving.

The test ROM's first name is SIGURD, longer than the original Japanese name. A later pointer lands inside this replacement and reads its trailing D. The editor preserves this existing logical value unless explicitly edited; it does not guess the intended name or silently repair the project's text.

## Dialogue

The source supplies 1,697 named resources at original disassembly addresses. 1,696 parse in the test ROM, with 13,874 unique text-run addresses, of which 13,572 are editable. `Chapter01/WorldMapUnused` encounters unknown command `4A` at `3287E2`; editing that resource is disabled.

Ordinary font selectors `09`–`0F` change the active font page (`0F` shares the final page); bytes `10` and above select glyphs. Commands and their operands are parsed separately, including the `00` extended prefix. Inserted names/text can change font state, so passages without a subsequently known font are protected. A named entry point inside a text run also prevents editing that run.

The encoder selects pages as needed, restores the original final font page and fills unused bytes with redundant font selectors. This keeps each passage's size and every following command address fixed. The save path reparses every originally valid resource and verifies the complete command sequence, operand bytes, command addresses and resource endpoint. Any overlapping portrait/text writes or overlapping staged dialogue writes fail verification.

This deliberately avoids relocation: there may be event references, inserted text references or entry points not represented in this partial disassembly. Original addresses are a compatibility assumption, not proof that every catalog entry is still used by a modified project's events. This version does not discover relocated scripts or prove all runtime references.

## Font and layout limits

Menu names and dialogue use different glyph maps. ASCII menu letters are mapped to full-width uppercase. The original dialogue map has uppercase Latin letters but no lowercase English alphabet. Dialogue spaces map to the existing narrow-space glyph; unsupported characters are rejected. No font graphics are patched.

Byte-budget validation does not establish visual fit. English may have different widths and page-switch overhead from Japanese. Dynamic dialogue names have their own small original capacities. Adding lines, changing commands, moving resources, updating event pointers and installing lowercase font graphics are future work.

## Verification scope

The included text integration tests verify no-op round trips across the menu names and all parsed dialogue runs; name alias isolation; rejection of unsupported/oversized text; immutable command locations; combined name, story and portrait changes; checksum and copier-header preservation; headerless operation; source-file preservation; and overlapping-write rejection. The existing portrait suite is retained.

Tests operate on temporary copies. An emulator and graphical display server were unavailable, so execution in the game and interactive desktop behavior remain unverified. In particular, repeated font-selector padding and English line widths still need an in-game check.

## Additional ROM profile, 0.2.2

The newer supplied WORKING NOW ROM uses the exact community patch described in `顔グラ共通パレット解除 - Unlock common palette for face graphics.txt`, under Bugfograms material / patch collection / Common palette cancellation in the supplied archive. Its documented headered changes are 09A383 F0→D0, 0B8574 9FD7557F→EAEAEAEA, 0BD980 8D5C02→EAEAEA, 16CCD5 8DFC01→EAEAEA, and 16CD04 8DFC01→EAEAEA. All five match this ROM. The editor recognizes the complete signature and uses stored index-14 palette colours for this profile. The older profile continues to force shared grey. No patch bytes are changed by the editor.
