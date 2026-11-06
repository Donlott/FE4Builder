# Weapon skills: current support and extension feasibility

This review uses the latest supplied headered FE4 Archanea ROM. The editor
label corrections change no ROM instructions, item flags or save data. Extra
weapon-skill support described below is a feasibility result, not an installed
game patch or a newly enabled dropdown choice.

| Skill | Native weapon support | What an extension needs |
| --- | --- | --- |
| Critical | Yes: Skill Set 1, `10` | Already works. Previously labelled Berserk. |
| Pursuit | Yes: Skill Set 2, `08` | Already works with the ordinary attack-speed condition. |
| Adept | No native item mapping | A new item-skill source/mapping. Existing battle code already reads item-derived Adept flags. |
| Charge / Accost | No native item mapping | A new item-skill source/mapping. Existing round checks already read item-derived Accost flags. |
| Vantage | No native item mapping | A new item-skill source plus an equipped-weapon check in the activation routine, retaining the half-HP condition. |
| Luna | No native item mapping | A new item-skill source plus an equipped-weapon check in the sword-skill proc routine. Native eligibility is sword-only. |
| Sol | No native item mapping | The same proc-routing change as Luna. Native eligibility is sword-only; the healing effect already exists. |
| Renewal | Yes: Skill Set 1, `20` | Already works. Previously labelled Life. |
| Paragon | Yes: Skill Set 1, `40` | Already works. Previously labelled Elite. |

Values in the table are hexadecimal **bytes**, not character skill IDs. The
two skill bytes form one 16-bit mask at item-record offsets 8–9. For example,
Critical plus Paragon is first-byte `50`; Pursuit is second-byte `08`.
The native inventory skill check normally requires a weapon to be equipped.
Carried non-weapon skill items use the game's separate native behavior.

The companion module's old first-byte list contained duplicate `41` and `60`
entries and omitted a valid combination. Its 32 combinations now consistently
match Steal (`01`), Miracle (`08`), Critical (`10`), Renewal (`20`) and Paragon
(`40`). Existing stored item bytes remain unchanged. The separate field at
offset 16 is now labelled **Effectiveness**: its mounted, airborne, dragon,
armor and mage targets are unrelated to the Critical skill.

## Native code checked

The item-to-skill mapping table is at CPU `87:A280`. The inventory checker at
`87:A2EF` includes the equipped-weapon condition. The battle flag builder at
`84:E06C` already combines personal/class skills with inventory skills.
Adept's strike count at `84:E2AB` and Accost's round check at `84:E3F8` consume
these combined flags. Adding their mappings alone worked in isolated probes.

Vantage's activation at `84:E231` separately calls the personal/class-only
checker, so adding its item mapping alone did not activate it. The sword-skill
selector at `84:E106` likewise ignores inventory skills when rolling for Luna
or Sol, even though their battle flags can be collected. Adding an item-aware
check in temporary overlays enabled those activations under existing eligibility.
Allowing Luna/Sol on other weapon types would require a broader change and
separate tests of combat effects, ranges, animation paths and interactions.

Critical's native calculation at `84:FD98` directly tests item bit `0010`.
Renewal at `84:AFF9` and Paragon at `84:EF2D` already check inventory skills.

## Scope of the feasibility probes

The native instruction emulator ran against an in-memory copy of the supplied
ROM with a real unit/inventory RAM fixture. Personal/class skill checks were
forced false for isolation. Item checks covered equipped and unequipped weapons. Individual
trial mappings produced actual Adept strikes and a successful Accost round
check; an item-aware routing prototype enabled Vantage at half HP and Luna/Sol
proc selection with sword eligibility. Luna/Sol used a deterministic successful
chance and a fixture for activation-log allocation; this was not a full battle
animation or damage/healing playthrough.

These trials reused a spare bit one skill at a time. Preserving all native
item flags leaves only four unassigned bits for the five additional requested
skills. A complete extension should use separate ROM metadata or another
explicitly verified allocation rather than silently repurposing the existing
unknown `0002` flag. Additional save fields are not inherently required, since
weapon skill definitions can remain ROM data. Simultaneous combinations,
personal-skill interactions, breakage/equipment changes, UI display and both
animation modes still need production-patch tests.

The original uploaded ROM remained byte-for-byte unchanged throughout the review.
