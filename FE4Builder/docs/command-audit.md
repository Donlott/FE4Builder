# Event command audit — 2026-11-03

Audited base: commit `89a22d1`, updated with the local child-deployment decoder correction. Scope: the 557 catalogued chapter event scripts, their decoded commands, runtime `FIELDS`/`HELP` dispatch, and the separate live item-slot decoder. This is an implementation audit, not emulator verification of every command. Chapter trigger-table conditions, uncatalogued entry points, custom ASM contents, and opcodes absent from these scripts are outside this inventory. No ROM was modified.

## Coverage

- 74 command types; 12,054 command instances.
- 29 types with editing controls; 5,036 editable instances.
- 44 types have dedicated descriptions; 30 types (839 instances) fall back to generic help.
- 34 read-only types have operands, including jumps, silent unit loads and camera scrolling to Slot 1.
- 11 read-only types have no ordinary operands. Ten have help; Event Dummy still lacks help.
- 556 of 557 layouts decode; one whole script remains read-only.

## Decoder correction — resolved locally

`4A / 4F` Deploy Unit Group Child now consumes **8 bytes**: wrapper, subcommand, group, permanent flag, original character word, replacement character word. The source macro emits only the opcode/group; the caller appends five bytes consumed by the native handler.

In event `$0FD` (253), Chapter07Ulster Spawn, offset 425 now covers the entire payload. The false Create Sprite at 428 has disappeared, and Play SFX Word at 433 is restored. Map Scroll at 436 remains aligned. The same correction also decodes event `$128` (296), Chapter08Febail Asaello_Spawn, and `$12D` (301), Chapter08Meath Spawn, which previously appeared as unsupported layouts.

The catalogue generator now verifies cached command sizes before reuse and replaces stale decoded entries while preserving their catalogue indices. Regenerated command sizes agree with the independent live item-slot decoder (variable flag lists excluded from fixed-size comparison). Regression tests cover cache rebuilding, truncation, both wrappers, headered/unheadered sound editing, and all decoded sizes. No ROM was modified.

Sources: `SAFEGUARD/EVENTS/Conditions.h` DEPLOY_UNIT_GROUP_CHILD; native handler in `SRC/Events.asm`; `src/item_slot_events.py` CONDITION_SIZES[0x4f] = 7 plus wrapper.

## Descriptions still missing

| Opcode / condition | Command | Instances | Current editing |
|---|---|---:|---|
| `07` | Test Permanent Flag Set | 52 | Read-only; operands present |
| `0D` | Castle Name | 55 | Read-only; operands present |
| `17` | Berserk Cast | 1 | Read-only; operands present |
| `25` | Move Temporary To Coords Follow | 2 | Read-only; operands present |
| `43` | Fill Event Unit Slot By Coords | 2 | Read-only; operands present |
| `44` | Faction Unit Death | 11 | Read-only; operands present |
| `45` | Run Asm | 267 | Read-only; operands present |
| `4A / 4A` | Run Event Condition / Register Unitgroup Map Sprites | 50 | Read-only; operands present |
| `4A / 4B` | Run Event Condition / Load Faction Group | 3 | Read-only; operands present |
| `4A / 4C` | Run Event Condition / Set Faction Group | 3 | Read-only; operands present |
| `4A / 4D` | Run Event Condition / Set Faction Hostility | 39 | Read-only; operands present |
| `4A / 4F` | Run Event Condition / Deploy Unit Group Child | 3 | Read-only; operands present |
| `4A / 50` | Run Event Condition / Set Unit Position | 63 | Read-only; operands present |
| `4A / 53` | Run Event Condition / Change Units Factionslot | 21 | Read-only; operands present |
| `4A / 54` | Run Event Condition / Add Unit Money | 1 | Read-only; operands present |
| `4A / 55` | Run Event Condition / Subtract Unit Money | 1 | Read-only; operands present |
| `4A / 58` | Run Event Condition / Give Unit Pid Equip | 7 | Read-only; operands present |
| `4A / 5A` | Run Event Condition / Send Inventory To Supply | 3 | Read-only; operands present |
| `4A / 5B` | Run Event Condition / Give Unit Pid Forced | 6 | Read-only; operands present |
| `4A / 60` | Run Event Condition / Modify Love Points | 51 | Read-only; operands present |
| `4A / 62` | Run Event Condition / Set Location Takeover | 1 | Read-only; operands present |
| `4A / 63` | Run Event Condition / Delete Factions Ai | 20 | Read-only; operands present |
| `4A / 64` | Run Event Condition / Revive Factions Ai | 1 | Read-only; operands present |
| `4A / 69` | Run Event Condition / Set Talk Target If Unmarried | 24 | Read-only; operands present |
| `4A / 6A` | Run Event Condition / Set Child Talk Target | 15 | Read-only; operands present |
| `4A / 6F` | Run Event Condition / Open Village | 1 | Read-only; operands present |
| `4A / 70` | Run Event Condition / Add Unit Stat | 113 | Read-only; operands present |
| `4A / 71` | Run Event Condition / Remove Area Restriction | 21 | Read-only; operands present |
| `4A / 76` | Run Event Condition / Replace Unit | 1 | Read-only; operands present |
| `FFFE` | Event Dummy | 1 | No operands; description only |

## Read-only commands that already have descriptions but could gain controls

| Command | Instances | Remaining support |
|---|---:|---|
| Load Unit by Group Silent | 426 | Army group and entry selectors; preserve hidden-load behavior. |
| Map Scroll to Event Unit Slot 1 | 80 | Scroll-speed control; destination comes from the stored slot. |
| Go To | 93 | Validated command-boundary destination selector; same-bank targets and loop checks. |
| Jump If True | 84 | Same destination support; display the preceding/shared test dependency. |
| Jump If False | 78 | Same destination support; preserve condition semantics. |

## Suggested implementation order

1. Completed: correct child-deployment decoding and regenerate this inventory.
2. Add dedicated descriptions for every verified real type still using generic help. Describe Event Dummy without exposing meaningless fields.
3. Add Check Permanent Flag; scroll speed to Event Slot 1; coordinate-based Fill Event Unit Slot; and silent group loads. These can reuse existing flag, camera, slot and Army controls, with native validation.
4. Add unit positioning, group sprite registration, faction hostility/change, money and stat changes, and remaining inventory-grant variants. Use named selectors and explain shared item identities. Existing village reward controls do not make ADD_UNIT_STAT editable in ordinary events.
5. Add castle-name banners and love-point controls after verifying their fields and ranges.
6. Add validated branch destinations for Go To/Jump If True/False; do not expose raw numeric addresses as the only interface.
7. Investigate child/substitute-aware deployment/talk commands, follow movement, replacement, faction deletion/revival/death and location takeover before enabling them.
8. Describe Run ASM, but keep arbitrary code pointers read-only until known routines can be identified and checked.

## Intentional restrictions in existing editors

- Dialogue with BG preserves its presentation/type byte.
- Group unit loading preserves the stored sprite-color byte; the game derives allegiance display from deployment state.
- Temporary coordinate movement preserves its unknown high bit and legacy combined slot mode.
- Scripted camera routes preserve legacy $12 records without offering them as normal timed pauses.
- Map Transition preserves legacy zero timing/combined mode values but does not offer them as new choices.
- Unit and camera script pointers are edited through private route copies, not arbitrary pointer entry.
- No-operand commands such as Yield, waits, Restore Phase Music, Add Castle Money, Save Chapter Turncount and End Event need explanations rather than artificial parameter controls.

## Undecoded whole scripts

| Event ID | Event | Current reason |
|---|---|---|
| `$002` | Prologue Edain Abduction | Unknown command or condition $B7. |

## Full current inventory

“Editable” means controls exist for implemented fields. “Help” means a dedicated runtime description. Chapters are 0 = Prologue through 11 = Final.

| Opcode / condition | Command | Instances | Chapters | Editable | Help |
|---|---|---:|---|---|---|
| `02` | Go To | 93 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `03` | Jump If True | 84 | 0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `04` | Jump If False | 78 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `07` | Test Permanent Flag Set | 52 | 4, 6, 7, 8, 9, 10, 11 | No | Missing |
| `08` | Check Chapter Flag | 95 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `0C` | Dialogue | 403 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `0D` | Castle Name | 55 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Missing |
| `0E` | Play Song | 373 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `11` | Play Sfx Byte | 5 | 0, 3, 4 | Yes | Yes |
| `12` | Play Sfx Word | 901 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `13` | Restore Phase Music | 297 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `14` | Dialogue With Bg | 204 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `17` | Berserk Cast | 1 | 3 | No | Missing |
| `22` | Move Temporary To Coords | 19 | 0, 1, 2, 4, 5, 6 | Yes | Yes |
| `23` | Load Unit By Group | 621 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `24` | Load Unit Direct | 62 | 0, 1, 2, 3, 5, 6, 7, 8, 9 | Yes | Yes |
| `25` | Move Temporary To Coords Follow | 2 | 3, 9 | No | Missing |
| `27` | Move Temporary By Script | 107 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 | Yes | Yes |
| `28` | Load Unit By Group Silent | 426 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `29` | Wait Unit Sprite Decompressed | 833 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `2A` | Wait Until Map Sprites Halting | 243 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `2B` | Continue Form Map Sprite Halt | 30 | 0, 1, 2, 3, 4, 5, 6, 7, 8 | No | Yes |
| `34` | Pause | 1273 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `39` | Set Camera To Event Unit Slot 1 | 19 | 0, 1, 2, 3, 6, 7, 8, 9, 10, 11 | No | Yes |
| `3A` | Set Camera Position | 56 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `3B` | Map Transition | 26 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `3F` | Scripted Map Scroll | 11 | 0, 1, 4, 5, 6, 9 | Yes | Yes |
| `40` | Map Scroll | 146 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `41` | Map Scroll To Event Unit Slot 1 | 80 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `42` | Fill Event Unit Slot | 218 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `43` | Fill Event Unit Slot By Coords | 2 | 5 | No | Missing |
| `44` | Faction Unit Death | 11 | 5, 9, 11 | No | Missing |
| `45` | Run Asm | 267 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Missing |
| `46` | Fade In By Timer | 23 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `47` | Fade Out By Timer | 76 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `4A / 34` | Run Event Condition / Remove Chapter Struct | 15 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `4A / 36` | Run Event Condition / Set Permanent Flag | 18 | 0, 1, 2, 3, 5, 6 | Yes | Yes |
| `4A / 49` | Run Event Condition / Register Character Map Sprite | 55 | 0, 1, 2, 3, 5, 6, 7, 8, 9 | Yes | Yes |
| `4A / 4A` | Run Event Condition / Register Unitgroup Map Sprites | 50 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Missing |
| `4A / 4B` | Run Event Condition / Load Faction Group | 3 | 3, 11 | No | Missing |
| `4A / 4C` | Run Event Condition / Set Faction Group | 3 | 6, 8 | No | Missing |
| `4A / 4D` | Run Event Condition / Set Faction Hostility | 39 | 1, 2, 3, 5, 6, 7, 8, 11 | No | Missing |
| `4A / 4E` | Run Event Condition / Deploy Unit Group | 50 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `4A / 4F` | Run Event Condition / Deploy Unit Group Child | 3 | 7, 8 | No | Missing |
| `4A / 50` | Run Event Condition / Set Unit Position | 63 | 0, 1, 2, 3, 5, 6, 7, 8 | No | Missing |
| `4A / 53` | Run Event Condition / Change Units Factionslot | 21 | 1, 2, 6, 7, 8, 9, 11 | No | Missing |
| `4A / 54` | Run Event Condition / Add Unit Money | 1 | 2 | No | Missing |
| `4A / 55` | Run Event Condition / Subtract Unit Money | 1 | 2 | No | Missing |
| `4A / 57` | Run Event Condition / Give Unit Pid | 37 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | Yes | Yes |
| `4A / 58` | Run Event Condition / Give Unit Pid Equip | 7 | 3, 4, 5, 7, 10, 11 | No | Missing |
| `4A / 5A` | Run Event Condition / Send Inventory To Supply | 3 | 5 | No | Missing |
| `4A / 5B` | Run Event Condition / Give Unit Pid Forced | 6 | 1, 5, 7, 11 | No | Missing |
| `4A / 5C` | Run Event Condition / Update Location And Map Change Events | 34 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `4A / 60` | Run Event Condition / Modify Love Points | 51 | 1, 2, 3, 4, 6, 7, 8, 9, 10 | No | Missing |
| `4A / 61` | Run Event Condition / Set Unit In Castle | 46 | 0, 1, 2, 3, 5, 6, 8, 9 | Yes | Yes |
| `4A / 62` | Run Event Condition / Set Location Takeover | 1 | 9 | No | Missing |
| `4A / 63` | Run Event Condition / Delete Factions Ai | 20 | 2, 4, 5, 7, 9, 11 | No | Missing |
| `4A / 64` | Run Event Condition / Revive Factions Ai | 1 | 7 | No | Missing |
| `4A / 65` | Run Event Condition / Remove Unit | 48 | 0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11 | Yes | Yes |
| `4A / 66` | Run Event Condition / Undeploy Unit | 24 | 0, 1, 2, 3, 5 | Yes | Yes |
| `4A / 68` | Run Event Condition / Set Talk Target | 55 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 | Yes | Yes |
| `4A / 69` | Run Event Condition / Set Talk Target If Unmarried | 24 | 1, 2, 3, 4, 6, 7, 8, 9, 10, 11 | No | Missing |
| `4A / 6A` | Run Event Condition / Set Child Talk Target | 15 | 6, 7, 8, 9, 10 | No | Missing |
| `4A / 6D` | Run Event Condition / Add Castle Money | 10 | 0, 1, 2, 3, 4, 6, 7, 8, 9, 10 | No | Yes |
| `4A / 6F` | Run Event Condition / Open Village | 1 | 2 | No | Missing |
| `4A / 70` | Run Event Condition / Add Unit Stat | 113 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Missing |
| `4A / 71` | Run Event Condition / Remove Area Restriction | 21 | 2, 3, 4, 5, 7, 8, 9, 10, 11 | No | Missing |
| `4A / 76` | Run Event Condition / Replace Unit | 1 | 7 | No | Missing |
| `4A / 78` | Run Event Condition / Save Chapter Turncount | 15 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `4B` | Set Flag If In Chapter | 51 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | Yes | Yes |
| `4C` | Unset Flag If In Chapter | 18 | 0, 1, 3, 4, 6, 7, 9 | Yes | Yes |
| `FD` | Yield | 3379 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
| `FFFE` | Event Dummy | 1 | 0 | No | Missing |
| `FFFF` | End Event | 558 | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 | No | Yes |
