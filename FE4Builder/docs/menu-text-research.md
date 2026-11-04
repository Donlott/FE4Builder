# Menu text in the FE4 Archanea / Project Naga ROM

The implementation was checked against the latest supplied 8,389,120-byte
headered ROM, SHA256
`ad585c023f2692b0de31e648ff167d01398628b6a8cbcc22c00b7147ed6da6f1`.
Addresses below are headerless PC offsets. No ROM/font graphics are distributed.

The public build reference is
[Miacidae/Project-Naga-beta-v7](https://github.com/Miacidae/Project-Naga-beta-v7/tree/8924fb4ff5330b347074083736ada17940b677a5),
commit `8924fb4ff5330b347074083736ada17940b677a5`. Relevant source paths are
recorded in `data/menu_text.json`. Runtime description/skill tables were also
checked in the uploaded binary, rather than inferred from vanilla offsets.

| Text | Entries | Native table / source | Original graphics |
| --- | ---: | --- | --- |
| Item names | 138 | `504000`, 16-byte records | `572000–57FFFF` |
| Item descriptions | 138 | `507000`, 16-byte records | `5A0000–5AFFFF` |
| Shared item effect descriptions | 25 | Fixed 512-byte images | `5A0000–5A31FF` |
| Skill names and help | 20 | `09AC56 + native skill ID × 3` | 18 original frames in `594000–59CFFF`; Canto/Return initially null |
| Compact skill names | 18 | `507A00`, 32-byte records | Selected tiles in `450000–450FFF` |
| Class names | 72 | `502400`, 16-byte records | `568000–570FFF` |
| Terrain names | 26 | `503000`, 16-byte records | `580000–5833FF` |
| Status names | 7 | `503F00`, 16-byte records | `546000–546DFF` |
| Skill types | 2 | `502900`, 16-byte records | `547000–5473FF` |
| Map location labels | 46 | `503200`, 16-byte records | `584000–58FFFF` |
| Menu location labels | 55 | `505000`, 16-byte records | `584000–58FFFF` |
| Item message names | 110 | `506700–506DDF`, 16-byte encoded strings | Rendered by dialogue engine |
| Class message names | 71 | `506200–50666F`, 16-byte encoded strings | Rendered by dialogue engine |

The item message list deduplicates broken-weapon variants; its IDs therefore
diverge from inventory item IDs. The class message list likewise has a separate
entry count. Do not write these lists by assuming matching item/class record
indices. They are explicit categories, not automatic rename targets.

Menu records hold tile counts and 24-bit pointers to native planar 2bpp artwork.
Item names have left/right variants; locations have left/center/right or
left/center variants. Description counts `10` and `30` mean 16 or 48 tiles:
one or three 128-pixel lines. Skill help stores four 128-pixel rows, with the name
on the first. The native tilemap displays only eight name tiles (64 pixels)
and twelve tiles on each help row (96 pixels); the editor's name limit is
56 pixels to also fit the compact name column. The compact Skills menu is another tilemap; skill edits repack
its name tiles while preserving headings, type labels and unrelated artwork.

## Canto, Return and the skill-help graphics loader

Native skill ID `01` is Canto and `1D` is Return (see
[SAFEGUARD/Skills.h](https://github.com/ulti-mage/FireEmblem4/blob/387b2e4c63b72b0d3f2854eaa69f26946d83b383/SAFEGUARD/Skills.h)).
Their 24-bit help pointers at `09AC59` and `09ACAD` are
zero in the supplied ROM, even though their status-screen icons are enabled.
Two entries are appended at catalogue keys 708/709, text-entry IDs `1B`/`1C`.
Their native skill IDs and pointer addresses are explicit; text-entry IDs are
not assumed to equal native IDs. Existing catalogue keys remain unchanged.

Unassigned entries load as blank artwork. Suggested Canto/Return text is staged
in the editor, with no ROM mutation until Write to ROM. An already assigned
supported pointer retains its current artwork/text. The new entries use the
ordinary four-row private help format. They do not rewrite icon/visibility
tables or add rows to the game's original 18-entry global Skills glossary.

The real status help caller at `$89:A3F6` loads all three pointer bytes into
`lR18` (`$24..26`) before calling `$51:1A00`. That renderer subsequently replaces
the bank with `$59` at PC `511A11`: `A9 00 59 85 25`. This previously prevented
private skill graphics in `$5B..5F` from loading correctly. A skill-text write
checks the caller's exact 16-byte sequence and replaces only that five-byte
bank override with NOPs. Original `$59` artwork and private artwork then use
their own pointers, with the original transfer length, destination, tilemaps,
skill effects and icon tables preserved. Unknown/custom loader code is rejected
before any mutation. Unchanged text writes remain no-ops.

Character-name code already renders the small Project Naga font from
`128000` and its width table at `119971`. The new codec also supports spaces
and the available single-character accented glyphs. Foreground-column matching
recognizes the current bitmap; it never substitutes an upstream name merely
because an ID exists. I and l have identical pixels in this font. Hash-bound
hints resolve original reference artwork, while private records retain exact
user-entered text. Unrecognized custom artwork is shown explicitly in the
preview, not overwritten by opening or saving an unchanged entry.

## Private storage

The uploaded ROM's entire `5B0000–5FFFFF` region was zero-filled. No existing
FE4Builder allocator uses it. It is separate from backgrounds (`69–6E`), village
events (`6F`), intro graphics (`70–79`), maps (`7A–7B`), portrait storage (`7C`),
dialogue/growth (`7D`), and the signed-stat helper at `7BE000`.

The 320 KiB region contains a versioned header, catalogue fingerprint, original
fill byte, SHA256 over metadata/artwork/text, and an allocation directory at
offset `80` with 8-byte offset/length pairs indexed by catalogue key. Artwork
starts at offset `3000`. First-fit allocation reuses a changed entry's space
and stays within a 64 KiB ROM bank. Names store only their needed tile bytes.
Graphics are followed by `TXT1`, a two-byte UTF-8 length, and the exact text.
This text is editor metadata; the game follows the native graphics pointers.
Fixed shared-effect images also retain an integrity-bound text/artwork record.

The original 708-entry fingerprint `71fc7b09c03454b73a9757a6de892422`
is accepted when the two appended directory slots are empty. Opening an old
edited ROM does not change it. The next explicit write upgrades the fingerprint
and SHA256 while retaining every old allocation key, pointer, bitmap and text.
Suggested wording and labels are excluded from the new layout fingerprint so
future wording changes do not invalidate existing edits.

Before writing, the editor checks snapshots of relevant native tables, original
artwork, and the font. It verifies the private directory and every catalogued
private pointer before reusing space. Unsupported layouts, occupied regions,
corruption, aliasing across private owners, capacity failures and stale forms
fail before mutation. Saving uses the existing atomic ROM write, backups and
history, with the in-memory transaction restored on a failed save.

## Verification

ROM-free tests construct an independent synthetic font/layout and exercise
all 710 no-op loads, every category's exact text/artwork round trip, shared
name/description isolation, separate message IDs, overflow/invalid input,
compact skill preservation and exhaustion, bank boundaries and storage
exhaustion, stale/corrupt/foreign pointers, headered saving, backup/undo/redo,
failed disk writes, live labels, nonmodal UI, switching cancellation, and F5.
Additional regressions cover unassigned/previously assigned Canto and Return,
their exact native pointers, the bank-override repair, unknown loader rejection,
the visible 96-pixel help limit, staged default text and legacy-directory migration.

The actual uploaded ROM was also audited: all 710 entries loaded and stayed
byte-identical on an unchanged write (including the two unassigned panels).
A RAM copy received a different test string in every entry, all 710 changes
survived file save and reopen, and the test used 262,084 bytes of private allocations. Other reserved banks,
the font and Sheena's existing animation fix remained unchanged. The uploaded
source was never modified.

The ROM's real `$51:2300` item-description wrapper was executed in a 65816
instruction interpreter with its final DMA API captured. It forwarded the
private artwork pointer, expected 512-byte length and destination `$4C00` to
the existing native transfer API.

The native `$89:A3C0` skill-help caller and `$51:1A00` renderer were also executed
for all 18 original entries and all 20 edited entries, including Canto/Return,
with the final transfer API captured. Every transfer used the expected complete
24-bit pointer, 2,048-byte length and `$4C00` destination. The old `$59` override
defect was reproduced and the repaired path verified. Executing `$51:1B00`
confirmed that all three description rows display twelve tiles each (96 pixels).
The two existing visibility tables remained byte-identical and a saved test
copy reopened with all 20 skill texts intact. The original upload was unchanged.

Full in-game coverage of every menu and message context has not been performed.
The subsequent item-help repair below also received a rendered emulator check.

## Item-help length repair

Project Naga's five item-description readers at PC `51231D`, `51271A`,
`512912`, `512A18` and `51341D` load the single-byte tile count at
`507000 + item ID × 16` with a 16-bit `LDA`. The extra byte belongs to the
adjacent graphics pointer. Private allocations can have arbitrary low pointer
bytes, which contaminated the DMA length and the saved layout count. In the
latest supplied ROM, Sagebreaker's descriptor begins `30 D7 5C 5B`: it requests
48 tiles, but the unmasked read becomes `D730`, and the direct loader uploads
`E600` (58,880) bytes instead of `0600` (1,536). This overwrites menu graphics.

All five reads now call an eight-byte helper at `5B2F00` which performs the
same indexed load and masks it with `AND #$00FF`. The helper occupies reserved
header space after the maximum allocation directory and before artwork at
`5B3000`; it participates in the pool checksum. Loader signatures and helper
occupancy are checked before any write. The existing full pointer, native DMA
and tilemap code remain in use. New description edits install the repair, and
the Icon Editor can apply it to already-saved private descriptions without
rewriting their artwork, spelling or pointers.

The latest uploaded ROM was checked with all 138 items in both packing modes:
828 direct native help uploads matched their artwork pointer, byte count and
destination; 552 queued native help entries matched their byte count and
pointer. Snes9x reproduced Sagebreaker's repeating-tile screen on the original
ROM and displayed its help normally on the repaired copy. Saved custom skill
artwork and assignments remained intact. The source upload was unchanged.
