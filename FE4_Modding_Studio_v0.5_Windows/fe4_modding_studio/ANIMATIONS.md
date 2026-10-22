# Animation assignments — version 0.3

Open your ROM, then click **Animations…** in the main window. This module changes references to existing animation assets; it does not draw frames, insert animation sheets, play animations, or change weapon ranks.

## Different battle animations for axes and hand axes

1. Choose **Battle** in the category dropdown.
2. Search for the class's original FE4 name or hexadecimal class ID. Hero is `19` (called Forrest in some older documentation).
3. Select the desired **Axe** row, including its gender and any character-specific condition.
4. Choose a donor row, then click **Load donor values into fields**. Donors are filtered to the same weapon category. Alternatively edit the hexadecimal control, main graphics, sub-parts and palette IDs individually.
5. Click **Stage assignment**.
6. Select the separate **Hand axe** row and choose its donor independently. For example, Hero male Hand axe can borrow Warrior male Hand axe without changing Hero male Axe.
7. If the editor reports ungrouped battle rows, enable **Group battle rows for lookup**.
8. **Save ROM copy…**, and test it in your emulator.

The four values form a compatible set: a motion controller designed for cavalry will generally not work with infantry graphics. Copying a complete donor is the easiest starting point. Editing a main graphics ID alone cannot create missing poses. Existing assets and their supported weapons still determine what can work.

Your WORKING NOW ROM already contains custom Hero axe and hand-axe rows. They are separated from its sword rows, which conflicts with the lookup's grouping requirements. The grouping checkbox keeps every record and its values, but brings class/gender/character groups together, with character-specific rows before generic rows. It does not add weapon support or remove existing custom entries. Grouping is an explicit staged change; it is required before saving battle edits in this ROM. Unedited ROM saves remain byte-identical.

## Positioning and projectile timing

The battle appearance table is only part of the setup. **Battle positioning** and **Projectile timing** expose the existing separate tables. The latter has Bow, Hand axe and Javelin records. They are class-specific and shared across genders. Changing a female battle appearance does not isolate these values to females.

Select a row in these categories and copy a compatible donor, or edit its hexadecimal value(s). These tables do not always contain a row for every class/weapon combination. The Battle view reports missing related rows. In your ROM, Hero has no hand-axe positioning or hand-axe projectile timing entry. Changing Hero's battle appearance leaves the engine's fallback behavior in place; test projectile release, impact, return, criticals, misses and dodges carefully.

This version edits existing records only. It does not add missing rows or expand/relocate tables. Changing assignments does not make a class capable of equipping a weapon. No edits to positioning or timing happen implicitly when a donor appearance is chosen.

## Map combat

Select **Map combat**, choose the target profile, load a donor, and stage it. This copies the entire 49-byte profile: eight pairs of motion/graphics pointers plus the sprite type. It keeps matching controls and graphics together, without copying the graphics themselves.

Each map profile contains its weapon actions internally. **There are no independent Axe and Hand axe assignment rows here in the supported original map loader.** This release replaces the whole map-combat profile, affecting all its weapons. Independent per-weapon map-profile overrides would need additional engine work and are not implemented.

In the original loader, male units use the profile with their class number. Female units normally use that same profile unless **Female map assignment** selects another. Consequently replacing a base profile can affect both genders. The female selector cannot redirect male units. Seliph as KnightLord uses the separate `5D KnightLordSeliph` profile; the female selector does not change that exception. Ballista handling and other special engine paths are not generalized by this editor.

## Map movement

**Map movement** changes existing movement/selection sprite assignments. Each row displays its class, gender and optional character condition. Fallback rows are used when earlier conditions do not match. Choose the desired existing short/tall sprite from the dropdown and stage it. These assignments are independent of map combat and do not edit idle artwork.

## Saving and compatibility

Click **Stage assignment** before changing rows. Unstaged typing or loaded donor values are not saved. Closing the animation window keeps staged edits in the open ROM session. The main Save ROM copy includes portraits, names/story and animation changes together.

**Save animation project…** stores only staged animation edits and the grouping setting as JSON. Reload it against the exact original input ROM, checked by SHA-256. It contains no ROM data or portrait/text edits. Reopen a saved ROM to begin another session.

Supported: the original table layouts and loader routines found in both supplied Archanea ROMs, including the newer common-palette-unlocked ROM. Loader differences disable this module without disabling the other editor windows. Relocated/expanded animation tables and patched map selectors need a separate profile.

This is a binary-tested first release. No emulator or interactive GUI testing was available. There is no animation preview. Tests verify bounded changes and save/reopen behavior, not visual correctness or compatibility of arbitrary graphics/controller combinations.
