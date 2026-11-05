# Additional weapon stat bonuses

Open **Items → Stat Bonus Editor**, or click **Edit…** next to a weapon's
**Stat Bonus** field in Item Editor. **Add weapon bonus…** lets you select a
free hexadecimal profile ID, copy an existing combination, and edit Strength,
Magic, Skill, Speed, Defense and Resistance. **Add & write to ROM** creates the
profile with the normal automatic backup and undo history. Assign the new
profile in an item's Stat Bonus dropdown, then write that item to the ROM.

Custom profiles use IDs **10–FF**, allowing 240 additional combinations.
Original IDs **00–0F** retain their meanings; **00** is None. Unlike item and
player-slot selectors, **FF is a valid custom bonus ID**, not Nothing. A profile
can be shared by several weapons, while copying creates an independent effect.
Changing a custom profile does not change its source's bonuses or holy blood
growths. Original profile pointer aliases retain their existing shared behavior.

**Remove custom bonus** is available for added entries. It refuses removal while
an enabled original or added item references that ID. Reassign those items
first. Other profile IDs never move, and removed IDs are available for reuse.
The reference list follows live item pointers and ROM item names; disabled item
records and arbitrary custom ASM references are outside this list.

Bonuses are unsigned integers from 0–255. HP, Luck and Movement are outside the
six-stat profile format. Large bonuses can exceed the game's display capacity.
Ring effects and Safeguard/Barrier Blade keep their existing separate behavior.

## Weaker inheritable legendary weapons

Create the lesser weapon as its own item type, reuse the existing artwork,
and assign an independent, smaller bonus profile. Use the intended ordinary
A/B/C rank and blood/inheritance template. Bonuses do not impose a holy blood
requirement or block inheritance. The usual child class/weapon compatibility
and any selected special inheritance exceptions still apply. The stronger
version can retain its original profile. Adding profiles alone does not change
any item assignments, ranks or inheritance settings.

## ROM storage and compatibility

The first addition checks the supported 8 MiB Project Naga ExHiROM layout and
the native weapon bonus routine before installing its lookup extension. It
reserves PC **7ED000–7ED7FF**, accessed through CPU **3ED000–3ED7FF** so the
code reads ROM rather than WRAM bank 7E. This is separate from expanded item,
menu text, icon, combat, growth, map and promotion patch storage.

The fixed **2,048-byte** reservation contains integrity metadata, 76 bytes of
code, enable flags and room for 240 six-byte profiles. The editor reports active
bonus bytes separately from this reservation. Removing individual profiles
clears their data; removing the last profile restores the original five-byte
hook and releases the whole reservation. ROM file size and SRAM size stay fixed.

The original 13 table profiles and both special sword effects remain native.
Disabled custom IDs return zero bonus. The patch uses the existing item bonus
byte and adds no RAM fields or save fields. It works with original item tables
and the optional item expansion; it does not itself require a new game.

Opening the editor does not install a patch or change ROM data. Writes check
storage ownership, routine signatures, integrity and stale data; save failures
restore ROM memory. Copier headers, automatic backups, undo/redo and item-editor
graphics previews remain supported. Custom bonus storage or native routine
modifications that do not match this format are rejected rather than overwritten.
