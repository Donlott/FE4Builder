# Item types and player item slots

Open **Items → Item Editor**. One workspace contains **Item types** and
**Player item slots**. The former edits shared weapon, staff and ring properties,
names/descriptions, inventory icons and held artwork. The latter edits each
persistent copy's assigned type and shows its live inventories, shops, rewards,
drops and conditional inheritance appearances, with navigation buttons.

Select **Advanced item modules** in the same view dropdown to access all 20
original Nightmare item modules. The additional module selector restores broken
weapon mappings, player/enemy sounds, both holy-weapon flash modules, magic
animations and their pointers, map sprites/palettes, battle sprite pointers,
the item skill table, minimum damage, raw name pointers and weapon bonus
profiles. Original weapon/staff, ring, Circlet, Camus and player/sprite module
views are available there too, including the Camus view's raw Max Uses field.
Each module keeps its original fields and record navigation. Expanded player
slots and held-sprite assignments use their relocated tables. Module edits use
the same Write to ROM, backups, undo/redo and Save & Launch controls. Switching
views or modules settles pending changes first; opening/browsing is read-only.

Inventory icons and held weapons appear side by side in both the item views
and original item modules. The held preview follows draft sprite/palette and
weapon/staff selections without writing to the ROM. Inventory lists and item
reference fields also show their native icons; player-slot previews follow the
draft assignment. Items without held artwork are labelled accordingly, and
invalid references clear the affected preview rather than leaving stale artwork.

## Enabling entries

**Add item...** copies an existing item into a disabled ID. **Add player slot...**
assigns an enabled type to a new persistent slot. The dialog lets you choose the
hexadecimal ID, including a nonconsecutive ID, and explicitly writes the result
with an automatic backup. Opening the workspace does not patch a ROM.

| Resource | Original usable entries | Maximum | IDs |
| --- | ---: | ---: | --- |
| Item types | 138 | 255 | 00–FE |
| Persistent player item slots | 140 | 254 | 01–FE |

FF means Nothing. Player slot 00 remains reserved. The former raw player module
exposed the original two FF terminator bytes as slots 8D/8E; these are not usable
original entries. The expansion can explicitly enable those IDs.

The first addition enables the ROM patch and **requires a new game**. The new
save magic hides pre-expansion saves. Four save slots remain available; the
existing autosave selection is retained. Each new-format save always serializes
254 item records (794 bytes rather than 450), so subsequent additions/removals
do not move the remaining save fields again. The supported ROM's native
overflow area and signed personal-stat extension remain separate. SRAM remains
32 KiB when the signed-stat fix is installed.

## Removing and optimizing

Original entries remain enabled. Added entries can be removed after their
indexed references have been cleared/reassigned. Other IDs never change.
Disabled slots are cleared of saved ownership when an expanded save is loaded,
preventing a removed slot from reappearing as its placeholder item. Custom ASM
can contain references outside the index; review the coverage notes and your
custom code before removing an entry used by a running campaign.

Added stat records are compacted and identical records share space. Editing a
shared added record uses copy-on-write. Removing an item also releases its
private menu artwork and clears its descriptors and event-name entry. Its donor
and other text entries retain their addresses and artwork.

**Optimize storage / report...** previews inventory/skill icon packing and the
bytes recovered, then offers to write that concrete optimization. Stats are
already compacted on writes. The report also shows enabled counts, native-bank
record usage, private text usage and the fixed save payload. Freed bytes can be
used for subsequent entries/artwork; the ROM file size stays fixed.

Names and descriptions have independent artwork after editing. New items have
their own menu name, help description and event-message name. The existing Menu
Text, Icon and Combat Animation editors recognize enabled added IDs. Character,
enemy, shop, village and supported event-command selectors use the same live
enabled set.

## Reused graphics and mechanics

Added items copy existing properties and use an existing animation template for
battle poses, spell effects and map weapons. Held sprite/palette assignments
remain independent, so an axe can use existing axe animation poses with another
existing palette. Physical animation templates must suit the weapon type/range.
The separate blood/inheritance template retains the copied holy weapon's blood
requirement and the native Forseti/Valkyrie/Yewfelle inheritance exceptions.
It can be selected independently of the animation template for added items.

This expands definitions and persistent copies, not executable item effects.
New staff behaviors, entirely new weapon classes or custom hardcoded special
item rules still require their own game-code patches. Native inventory VRAM
still accommodates 120 unique icons; many item types can share an icon. The
editor reuses the existing 65 held sprites and 36 held palettes.

## Storage and compatibility

Supported installation target: the verified 8 MiB Project Naga ExHiROM, with or
without a copier header. Occupied reservations or changed loader instructions
are rejected before writes. Current combat-animation aliases and private menu
text are preserved. Writes use the normal backup/history system and update both
ROM checksums. A stale item form cannot overwrite changes from another editor.

The village editor's older whole-bank checksum included separately-owned icon
and combat metadata. Known independent allocations can now be recognized
without discarding the village integrity check: recovery is accepted only when
restoring those allocations to the original fill reproduces the stored checksum
exactly. Normal backed-up writes refresh that checksum when village data stayed
unchanged. Live village payloads cannot be overwritten by icon/combat writes.
Legacy village copy slots whose actual payload overlaps an owned icon/combat
allocation remain protected; relocating those copies is a separate migration.

The patch owns PC 7E8000–7ECFFF, mapped through CPU 3E8000–3ECFFF in ExHiROM.
These are ROM offsets, not CPU WRAM bank 7E. The upper-half low-bank mapping is
verified against the emulator's ExHiROM mapper. This region is outside the
existing map, intro, portrait, dialogue, background and signed-stat reservations.
The first 8 KiB reserve code,
metadata and byte-indexed tables. Added name/help descriptors and message names
use the following 12 KiB. Actual name/help artwork uses the existing menu-text
allocator and is released there on removal.

Native item consumers require bank 83 record pointers. Original records keep
their addresses, preserving pointer-based holy weapon checks. Added records
use the originally blank PC 03F7C4–03FFFF region and, after replacing both native
offset-table readers, the obsolete 276-byte offset table at 03E9D0. Together
these hold 2,384 bytes; all 117 added 19-byte weapon/staff records need 2,223.
The item definition pointer table is relocated to the guarded expansion arena.
Original player assignments are preserved; a 254-entry runtime table initializes
every persistent ID, including unclaimed placeholders for disabled slots.

The pre-expansion save-ID remapper is not used by new-format saves. Its first
four bytes are replaced by the modern load exit's disabled-slot cleanup call.
The new native save magic is 9208; original 9207/1206 saves are not migrated.

## Verification

ROM-free tests cover sparse FE entries, all 117 additions, reference blockers,
copy-on-write/reclamation, private text migration, icon/combat interoperability,
copier headers, checksums, stale forms, failed writes, backups and undo/redo.
The development audit additionally executes the uploaded ROM's native 65816
lookups, four save/load slots, and high-ID drop/reward/shop routines using RAM
fixtures. These focused checks do not constitute a complete campaign playthrough.
