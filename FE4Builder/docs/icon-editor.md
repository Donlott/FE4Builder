# Native item and skill icon editing

This editor was verified against the supplied headered 8 MiB ExHiROM ROM,
SHA256 `ad585c023f2692b0de31e648ff167d01398628b6a8cbcc22c00b7147ed6da6f1`.
Offsets below exclude the 512-byte copier header. Modified copies were used for
validation; the uploaded source file was not edited.

## Graphics and assignment formats

Both icon families use 16 × 16, four-tile, uncompressed SNES 4bpp artwork.
Within an atlas, each row contains sixteen 8 × 8 tiles. Logical icon `n` starts
at tile `(n // 8) * 32 + (n % 8) * 2`; the other tiles are +1, +16 and +17.
Each complete icon occupies 128 bytes. The importer preserves indexed palette
positions from exported templates, including repeated colors. Other PNGs must
match the native palette or explicitly enable nearest-color reduction. Partial
alpha and incorrectly sized images are rejected before staging any changes.

| Resource | PC address | Format |
| --- | --- | --- |
| Item graphics | `184000` | `4000`-byte raw DMA sheet |
| Item assignments | `00D1AE` | 138 little-endian tile numbers |
| Status/trade item assignments | `0BBED5` | 138 little-endian byte offsets into the same sheet |
| Weapon-type / empty icons | `0AA2CB` | Nine byte offsets; preserved independently when packing |
| Inventory palette | `1E0160` | 16 SNES colors |
| Skill palette | `1E00C0` by default | 16 SNES colors; follows the native copy-loop source |
| Original skill graphics | `1E34C0` | `0C00`-byte raw sheet; 24 icons |
| Stat-screen skill assignments | `099300` | 29 words; `FFFF` hides a skill |
| Stat-help skill assignments | `09A52F` | 29 words |
| Compact Skills-menu assignments | `0BDB7E` | 18 words |

The compact Skills menu has only eighteen entries. Its skill-bit positions are
1, 2, 3, 4, 5, 7, 11, 13, 14, 15, 16, 17, 18, 19, 20, 23, 24 and 27.
It is not a third 29-word table: reading/writing past those eighteen words would
overwrite unrelated data/code. Skills absent from that menu can still have
artwork assigned to the two stat-screen contexts. New icons do not create new
skill mechanics, item types or compact-menu entries.

The skill palette is a menu override, rather than the character palette
initially loaded into the same CGRAM bank. The copy loop at PC `00BE0A` copies
CPU `$DE:00C0–00DF` into OBJ palette 7 for the stat screen and its help window.
The loop at PC `00D3D8` copies the same colors into OBJ palette 3 for the compact
Skills menu. Thus the default game uses the same multicolor skill palette in
all three contexts. Reading the initial character palette at `1E01E0`, or the
initial inventory palette at `1E0160` for compact skills, gives incorrect colors.
The editor validates those copy-loop instructions and reads their live source
operands, so relocated palette data is followed automatically. Thumbnails,
painting swatches, imports and PNG exports all use that screen's palette. Skills
absent from the compact menu use their stat-help artwork and palette as a fallback.

## Native rendering limits

The original item loader at PC `00CDF0` copies CPU `$D8:4000`, length `$4000`,
to VRAM word `$4200`. The item OBJ template adds tile `$20` to the item's table
value. Tile IDs occupy only nine bits of the OBJ attribute word. Therefore the
last eight physical slots would carry into palette bits: slot 120 starts at
atlas tile `$1E0`, and `$20 + $1E0 = $200`. Only slots 0–119 are exposed, and
the original last `$400` bytes of padding are preserved untouched. Slot 119's
bottom-right tile remains `$1FF` after the sprite offset.

The character-status and trade screens do not use the bulk menu's tile-number
table. `$8B:BE68` reads byte offsets from `0BBED5` and queues two 64-byte
uploads, with sources 512 bytes apart, into per-inventory-slot VRAM positions.
Both item tables are now written together (`byte offset = tile number × 32`).
The separate weapon-type/empty-slot offsets are tracked through optimization;
private item edits also preserve artwork used by these displays.

### Repairing ROMs saved with the earlier Icon Editor

Open the existing ROM in **Graphics & Text → Icon Editor**. A display-repair
message enables **Write to ROM** even when no artwork has been repainted.
Writing synchronizes the status/trade assignments with the saved editor
assignments. It also repairs the Project Naga item-help length readers when
private item descriptions are present. Existing artwork and text allocations
are retained. The normal backup and undo history cover the entire repair.
Restart the emulator with the written ROM and reopen the menu; an old save
state can retain already-corrupted video memory.

The previous editor updated only `00D1AE`, so optimization could leave stale
status-screen references. On the latest supplied ROM (SHA256
`1dbf054e9a6de85a72fd83b83ccfe6031b905c4a4aa837e2a7d071ccb8aa4b03`),
32 item types differed between these two tables, including Greataxe (`60`) and
Sagebreaker (`66`). Sagebreaker's separate help corruption came from an
unmasked tile-count read, rather than damaged icon artwork. Details are in
[menu-text-research.md](menu-text-research.md#item-help-length-repair).

Validation executed the actual status/trade loader for all 138 items, both
with and without optimization (276 loads), and checked all five native item
description paths. In Snes9x, a new-game test session using this ROM reproduced
the repeating-tile corruption after assigning Sagebreaker and Greataxe to a
test inventory in emulator RAM. The same session with the repaired ROM showed
both saved custom icons and opened both help panels without corruption. The
uploaded ROM was not modified; test inventory changes were confined to the
disposable emulator session.

Skill atlas uploads have three verified native destinations:

| DMA descriptor PC | Original source | Byte length | VRAM word destination |
| --- | --- | --- | --- |
| `00BD70` | `$DE:34C0` | `0C00` | `6800` |
| `00C57A` | `$DE:34C0` | `0C00` | `0000` |
| `00D39A` | `$DE:34C0` | `0C00` | `4200` |

The editor checks all descriptors, preceding JSL instructions, their copies at
PC +`400000`, adjacent upload descriptors, assignment readers and OBJ templates.
The stat-screen template uses tile base `$80`; the compact template uses `$20`.
A fourth atlas row fits within eight-bit atlas tile numbers and existing VRAM
gaps. The enlarged stat upload ends at VRAM `$7000`, exactly where the next
native upload begins. Expansion is capped at 32 icons / `$1000` bytes, and all
three descriptors and their mirrors change together. No decompressor, additional
DMA callback, skill effect, palette or gameplay code is injected.

## Storage and optimization

PC `6FC000–6FDFFF` is an exclusive 8 KiB reservation, verified uniformly empty
before first use. It is separate from the earlier Sheena helper near `6F0000`,
the signed-stat routines, dialogue/background storage, menu-text storage, intro
storage, map storage and promotion/growth-display helpers. Occupied storage is
viewable but cannot be written by this editor. Existing owned storage must have
valid metadata and a SHA256 digest before any icon operation can be saved.

The 256-byte metadata header records version, original fill byte, library flags,
expansion state and original artwork/loaded-sheet sizes. Blank user-added icons
have explicit library flags so they survive reopening. The expanded skill atlas
starts at PC `6FC100` and occupies 4096 bytes, without crossing a ROM bank. The
native skill atlas is retained; it is not reclaimed as unrelated free storage.

Optimization canonicalizes identical complete 128-byte icons, packs their unique
artwork and remaps every supported reference. Unique unassigned artwork is kept.
Reclaimed slots are zeroed. Item padding is preserved. A skill atlas fitting
24 icons returns to the original source and length, and clears its private
graphics allocation to the recorded fill byte. Metadata is retained for library
flags, integrity and original-size accounting.

Original sizes are captured on the first open and saved per ROM path in
`data/icon-sizes.json`; they are never replaced by an optimized baseline. On the
first actual write the original values are also recorded in ROM metadata, so
moving an edited ROM can retain the baseline. Preferences and the first-report
flag persist in the config. Damaged configuration is reported and preserved.

Reports distinguish occupied artwork slots, raw loaded-sheet bytes, and private
ROM storage. Packing frees reusable slots; it does not shrink a fixed raw DMA
upload or reduce the file's 8 MiB size. The original 16 KiB inventory upload
includes its padding even when fewer icons are referenced.

Writes use the normal automatic backup/history transaction and restore the
in-memory ROM on disk failure. The window holds a source snapshot, rejecting
stale edits if another editor changed the ROM. PNG import, private copying,
painting, library additions, reassignment and optimization are staged until save.

## Validation

ROM-free tests cover codecs, private/shared assignments, blank library entries,
capacity exhaustion, sprite palette-bit limits, six-path skill expansion, exact
affected byte ranges, duplicate packing and skill-sheet contraction, stale or
tampered storage, copier headers, FF-filled reservations, backup/undo/redo,
failed-write rollback, first-open baselines, config damage, indexed PNG round
trips, color-reduction opt-in, alpha/dimension rejection and nonmodal UI flows.
Palette regressions distinguish the skill menu override from the initial
character/inventory colors, follow changed copy-loop source operands, cover
copier headers and validate default preview/thumbnail/export colors, context
changes and missing compact entries without introducing ROM edits.

On a disposable copy of the supplied ROM, all nine safely available item slots
and all eight additional skill slots were filled. The real 65816 DMA queue
routine `$80:A4BD` executed for all six expanded descriptors; queued sources,
4096-byte lengths and VRAM destinations matched the new atlas. The real sprite
writer `$80:87C7` executed for 216 cases: all 120 item slots and all 32 skill
slots in each of the three display contexts. Tile additions retained palette
bits throughout, including each icon's bottom-right tile.

Another 208 item/skill references retained their exact artwork through packing
and reopening. Undo restored the expanded ROM, then the source exactly; redo
restored the edited ROM. Coexistence checks installed the earlier promotion and
growth-display patches on the signed-save ROM, edited icons, and removed those
patches without affecting icon storage or signed-save/Sheena helper data.
The portable desktop/package regression suite passed. Those earlier expansion
checks covered native instructions and the editor. The later status/help and
combat fixes also received the rendered Snes9x checks described in this document.

## Physical weapon combat animations

Inventory icons, held battle sprites and attack animations are independent.
On the latest uploaded Archanea ROM (SHA256
`1dbf054e9a6de85a72fd83b83ccfe6031b905c4a4aa837e2a7d071ccb8aa4b03`),
Greataxe (`60`) already has held sprite `26`, palette `14`; Sagebreaker (`66`)
has held sprite `21`, palette `20`. However, both retain staff battle style
`86` in the native style table at PC `1983BA`. The effect list at `19832D`
also still maps `66` to the unused `27` staff effect. The map weapon loader
at `$9E:8E01` accepts only IDs `00–39` and `7A–7C`, so it skips both items.
Changing the icon or the held-sprite assignment cannot repair these selectors.

**Item Editor → Combat animations...** provides an explicit, per-item physical
animation base. The suggested base matches the current weapon type, attack
range and, where possible, assigned held graphic. For this ROM, Greataxe uses
`2C` (Helswath), and Sagebreaker uses `2D` (Hand Axe). A ranged axe needs the
native close/ranged style `63`, which resolves to `23` at close range and `64`
at distance. The target's held graphic and palette remain in use. Map combat
uses the base weapon's map graphic/palette. Selecting a different base does
not change damage, effectiveness, skills, uses, stats, names or inventory icons.

Three guarded presentation hooks apply the alias:

| Hook PC | Native routine | Purpose |
| --- | --- | --- |
| `15A1ED` | `$95:A1ED` | Select battle attack style, retaining native distance handling |
| `16DC8A` | `$96:DC7C` | Select the base weapon's effect rather than a leftover staff effect |
| `1E8E01` | `$9E:8E01` | Load the base weapon's map weapon graphic/palette |

The gameplay item IDs and held-weapon loader are untouched. The implementation
keeps a 138-byte alias table and small stack-only helpers in a checked 4 KiB
reservation at PC `6FE000–6FEFFF`, immediately after icon storage. It requires
the verified 8 MiB ExHiROM layout, checks native code and storage integrity,
and rejects occupied/custom layouts before writing. Each save creates a backup
and undo entry. Removing the last alias restores all three original hooks and
the original free-space fill. The ROM is not expanded.

Bases are limited to supported physical sword/lance/axe/bow styles. Melee-only
styles cannot be selected for ranged weapons, and the control rejects missing
held graphics/palettes. It does not add new class poses or magical attacks.

Validation executed 141 alias cases (all item IDs plus sentinel/out-of-range
values), 564 native style selections, 1,128 native effect selections across both
battle sides, and 141 native map loads. Unconfigured items matched the original
routine results; configured items matched their base weapon. Original gameplay
IDs, held graphics, palettes and all item data were preserved. Tests also cover
headered/unheadered ROMs, FF-filled storage, incompatible ranges, tampering,
custom hooks, stale models, save rollback, removing aliases, backup/undo/redo
and the Item Editor button.

In a disposable Snes9x session, the starting player's class was changed in RAM
to Hero to match the reported class, and both test weapons and a nearby enemy
were arranged in emulator RAM. The unmodified combat selectors reproduced
Sagebreaker's empty-handed attack and stalled full battle. With the repair,
Greataxe completed full and map battles with visible weapon graphics;
Sagebreaker completed full battles at range 1 and 2 and displayed weapon
graphics in map combat. These are focused checks, not coverage of every class
or battle condition. Replaying the same close-range map attack before and after
the patch produced identical player/enemy personal data, player inventory and
all 142 item-instance records. The uploaded ROM was left untouched.
