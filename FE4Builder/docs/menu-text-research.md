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
| Skill names and help | 18 | Non-null entries in `09AC5C`, 3-byte pointers | `594000–59CFFF` |
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
one or three 128-pixel lines. Skill help has four 128-pixel lines, with the name
on the first. The compact Skills menu is another tilemap; skill edits repack
its name tiles while preserving headings, type labels and unrelated artwork.

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

Before writing, the editor checks snapshots of relevant native tables, original
artwork, and the font. It verifies the private directory and every catalogued
private pointer before reusing space. Unsupported layouts, occupied regions,
corruption, aliasing across private owners, capacity failures and stale forms
fail before mutation. Saving uses the existing atomic ROM write, backups and
history, with the in-memory transaction restored on a failed save.

## Verification

ROM-free tests construct an independent synthetic font/layout and exercise
all 708 no-op loads, every category's exact text/artwork round trip, shared
name/description isolation, separate message IDs, overflow/invalid input,
compact skill preservation and exhaustion, bank boundaries and storage
exhaustion, stale/corrupt/foreign pointers, headered saving, backup/undo/redo,
failed disk writes, live labels, nonmodal UI, switching cancellation, and F5.

The actual uploaded ROM was also audited: all 708 entries were recognized and
left byte-identical by an unchanged write. A RAM copy received a different
test string in every entry, all 708 changes survived file save and reopen,
and the test used 257,888 bytes of private allocations. Other reserved banks,
the font and Sheena's existing animation fix remained unchanged. The uploaded
source was never modified.

The ROM's real `$51:2300` item-description wrapper was executed in a 65816
instruction interpreter with its final DMA API captured. It forwarded the
private artwork pointer, expected 512-byte length and destination `$4C00` to
the existing native transfer API. This verifies the pointer path, not a full
SNES rendering/session. Full in-game coverage of every menu and message context
has not been performed; native-font UI previews and the automated checks do
not replace that playtesting.
