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
| Inventory/compact skill palette | `1E0160` | 16 SNES colors |
| Stat-screen skill palette | `1E01E0` | 16 SNES colors |
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

## Native rendering limits

The original item loader at PC `00CDF0` copies CPU `$D8:4000`, length `$4000`,
to VRAM word `$4200`. The item OBJ template adds tile `$20` to the item's table
value. Tile IDs occupy only nine bits of the OBJ attribute word. Therefore the
last eight physical slots would carry into palette bits: slot 120 starts at
atlas tile `$1E0`, and `$20 + $1E0 = $200`. Only slots 0–119 are exposed, and
the original last `$400` bytes of padding are preserved untouched. Slot 119's
bottom-right tile remains `$1FF` after the sprite offset.

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
The portable desktop/package regression suite passed. This is native-instruction
and editor verification; a full rendered SNES playtest remains necessary.
