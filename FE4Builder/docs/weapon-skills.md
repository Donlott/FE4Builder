# Additional weapon skills

Open **Patches → Additional weapon skills → Install: Additional weapon skills**.
Then open **Item Editor → Item types** and tick the desired skills in the
**Additional weapon skills** panel. **Write to ROM** saves them alongside the
item's properties with the normal automatic backup. Only equipped weapons
grant the extra skills; merely carrying another weapon does not grant them.

| Skill | Assignment | Behavior |
| --- | --- | --- |
| Critical | Native Skill Set 1, `10` | Native weapon Critical. Previously labelled Berserk. |
| Pursuit | Native Skill Set 2, `08` | Native attack-speed condition. |
| Adept | Additional weapon skills | Native extra-strike chance/rules. |
| Charge / Accost | Additional weapon skills | Native HP, attack-speed and extra-round rules. |
| Vantage | Additional weapon skills | Native half-HP condition and round order. |
| Luna | Additional weapon skills | Native sword eligibility, Skill-based proc and defense effect. |
| Sol | Additional weapon skills | Native sword eligibility, Skill-based proc and healing effect. |
| Renewal | Native Skill Set 1, `20` | Native turn healing. Previously labelled Life. |
| Paragon | Native Skill Set 1, `40` | Native experience effect. Previously labelled Elite. |

Native byte values above are hexadecimal, not character skill IDs. Multiple
extra skills can be selected together and combined with the native flags.
Personal/class skill checks take precedence where they already do; duplicate
sources do not grant duplicate copies. Existing proc priority, chance, Nihil,
Brave and other battle rules are retained. Luna/Sol are not extended to lances,
axes, bows or magic in this version. Their unchecked controls are disabled for
ineligible weapon types; clear assigned Luna/Sol before changing a sword's type.
Staffs and rings cannot receive the five extra skills.

Extra assignments are keyed by **item type**, not persistent player slot or
item-definition pointer. Thus all copies of a type share its extra skills,
while different types remain independent even if their stat records are shared.
This works with original item tables and the optional item expansion. Added
types copy the donor's assignments; deleting an added type clears its extra
skills. The native effective item ID is used, so breaking a weapon switches to
the broken item's assignments. Item names, icons and held-art previews remain
separate and unchanged. Existing skill icons and names are reused in-game.

## Installation, storage and removal

This version targets the **8 MiB Project Naga-compatible ExHiROM layout** used
by the supplied Archanea ROM. Copier headers and FastROM headers are handled.
It validates the affected routines and five original zero item mappings rather
than requiring a whole-ROM hash, allowing unrelated hack data to differ. It
rejects modified hook code, occupied storage and conflicting item mappings.
This is not a universal patch for every Project Naga revision or the original
4 MiB Japanese ROM. The supplied Archanea ROM is the real-ROM validation base.

The fixed **2,048-byte** reservation is PC **7ED800–7EDFFF**, accessed through
CPU **3ED800–3EDFFF** to avoid WRAM bank 7E. It is separate from bonus profiles,
item expansion, icons, dialogue, portraits, maps and the other supported patches.
It contains a 256-byte assignment table, 391 bytes of code, integrity metadata
and padding. No native item bits are repurposed. Save layout, SRAM capacity,
inheritance and item ranks are unchanged; installing this patch alone does not
require a new game. Restart the emulator to load the newly written ROM code.

**Remove patch** refuses while any extra assignments remain and lists the items
to clear in Item Editor. After they are cleared, removal restores all four
native hooks and the original reservation filler. IDs do not move. Patches and
item writes retain the normal backups, failed-write rollback and undo/redo.
Opening an editor does not install the patch or write to the ROM.

## Implementation and verification notes

The inventory skill checker at CPU `87:A2EF` dispatches only the five additional
skill IDs to the new table. Other IDs execute the original checker, preserving
its native flags and item mappings. New checks use the native equipped-weapon
condition and effective item-ID getters for player, holy and enemy inventories.
The native battle flag builder then supplies Adept and Accost to existing code.
Two activation calls at PC `04E239` and `04E150` additionally consult item skills
for Vantage/Luna/Sol while keeping the original personal/class and sword checks.
The native skill-list builder also includes extra skills without duplicates.

The original first-byte skill list's duplicate `41`/`60` combinations have been
corrected; its 32 choices now match Steal (`01`), Miracle (`08`), Critical (`10`),
Renewal (`20`) and Paragon (`40`). The item field at offset 16 is labelled
**Effectiveness** rather than Critical. Existing stored item bytes are preserved.

The 174-test portable suite passed. Weapon-skill tests cover code/storage guards, all 32 combinations, original flags,
copier headers, checksum maintenance, copying/deleting added types, assignment
eligibility, stale data, backups, failed writes, removal, undo/redo and the patch
and item-editor controls. On the supplied Archanea ROM, native instruction checks
passed 405 skill checks, 150 comparisons with unchanged native behavior, 23 combat
checks, and 1,592 item save/load records across all four save slots with both
original and expanded item tables. These include broken and unequipped weapons,
personal/class overlap, proc priority, Nihil, Luna damage and Sol healing.
Snes9x full battles activated weapon Luna and Sol and returned to the map;
map combat also activated Sol and healed the wielder. Tests use disposable ROM
copies and leave the source unchanged. No source ROM is included in downloads.
