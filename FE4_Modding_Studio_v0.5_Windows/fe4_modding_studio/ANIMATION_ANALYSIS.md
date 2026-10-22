# Animation assignment investigation

Primary source: ulti-mage/FireEmblem4, commit `387b2e4c63b72b0d3f2854eaa69f26946d83b383`, https://github.com/ulti-mage/FireEmblem4 . The local disassembly is incomplete. Source-covered map behavior is used directly; the battle table format is corroborated with the supplied Japanese community documentation and the actual loader bytes in the supplied ROMs. All offsets below are headerless.

## Sources

- `SRC/Bank84.asm`, `rsGetClassMapSprite` at CPU `$84:A84A`: class-relative table lookup, character/gender filters and fallback.
- `SAFEGUARD/Classes.h`, `structClassMapSpriteAssignment`: character word, gender byte, sprite word.
- `TABLES/OFFSET/ClassMapSpriteAssignmentOffsets.csv` and `TABLES/CLASS/ClassMapSpriteAssignment.asm`: 72 classes and their movement selector rows.
- `TABLES/CLASS/MapMovementShortSpritePointers.csv`, `MapMovementTallSpritePointers.csv`: short/tall movement sprite identities.
- `SRC/TempStuff.asm`, `rlUnknown88C9A6`: sprite ID high-bit chooses tall/short; low bits are an index, multiplied by three for pointer lookup.
- `SRC/TempStuff.asm`, `rlUnknown9E85A4`: original map-combat gender mapping and KnightLord/Seliph exception.
- `SRC/TempStuff.asm`, `aBattleMapSpriteData` at CPU `$9E:B50D` and `rlUnknown9E8867`: 49-byte directional map-combat profiles and their consumption.
- Supplied community archive, Normal structure `Struct.def`; `クラス順リアル武器指定戦闘アニメ・バイナリデータ`; `各クラスのマップ戦闘アニメヘッダ指定・バイナリデータ`; `各クラスの武器毎の立ち位置・バイナリデータ`; tutorial `EXP75(リアルアニメ設定・既存クラス編)`. Text was decoded as CP932. Archive addresses generally include the 512-byte copier header, which this editor subtracts.

## Tables

| Purpose | Headerless start | Layout |
| --- | --- | --- |
| Battle appearance | `1788C9` | 206 records × 8 bytes |
| Battle positioning | `17E8FB` | 138 records × 3 bytes |
| Bow timing | `18AFFD` | 15 records × 4 bytes, then FFFF |
| Hand-axe timing | `18B03B` | 12 records × 4 bytes, then FFFF |
| Javelin timing | `18B06D` | 17 records × 4 bytes, then FFFF |
| Map-combat profiles | `1EB50D` | 94 records × 49 bytes |
| Female map selector | `1E85DF` | 72 pairs of bytes |
| Movement class offsets | `03805E` | 72 relative word offsets |
| Movement selectors | `0380EE`–`03833C` | five-byte records, 118 unique rows |

Battle fields are class, weapon category, character override, gender, control ID, main graphics ID, sub-parts ID and palette ID. Categories are 00 sword, 01 lance, 02 axe, 03 bow, 05 javelin, 06 hand axe, 07 magic, 08 staff. This is the animation selector's weapon category, not a new per-item override system. Only the final four bytes are editable; selector conditions and record count are retained. The old supplied ROM also contains an FF class record, retained as disabled.

The battle scan at CPU `$95:A2C8` reads these fields through long references into `$97:88C9`. Its loop advances by eight and bounds the scan at `$0670` bytes (206 records). It tracks progress through class, gender and character matching; leaving a matched group can invoke fallback. Thus moving custom class rows into unrelated classes' blocks is not a reliable way to add them. The community tutorial also explicitly requires contiguous class records.

The WORKING NOW ROM has Hero axe/hand-axe records at indices 3, 4, 8 and 9; its sword records are at 90 and 91. Grouping in this editor sorts class, gender and character override groups, retaining every record and placing generic character-zero entries after specific characters. Group validity is checked by contiguity, not by insisting that all valid input tables be numerically sorted. The program never automatically normalizes an unedited ROM.

## Selection and data limits

The map-combat base profile is class-number indexed for males. Native female mappings use the second byte of a pair; FFFF means base profile. The first byte is not a configurable male mapping in the native loader. The editor therefore never presents it as one. The known community map-selector replacement patch is not installed by this version.

A directional map profile combines control and compressed-graphics pointers; the eighth pair is followed by the short/tall type byte. Donor copies move only these references. Per-weapon action commands live inside the referenced control/assets; they are not independent class/weapon rows like the full battle table. Per-weapon map-profile hooks are outside this release.

The character movement selector uses a different table and IDs; those IDs must not be confused with map-combat profile IDs. All 97 source-listed movement IDs are exposed, including the tall flag. This does not replace idle-sprite artwork.

Positioning and projectile timing are separate class-based tables; no row is inserted if absent. The two projectile parameter bytes are exposed together, with incomplete semantic understanding explicitly stated. A donor appearance alone is not proof that its timing or pose data fits another class.

## Validation

The module checks four loader signatures against the examined ROMs, structural table bounds, selector values, mapped pointers and timing terminators. Edits preserve lengths, selectors and unrelated bytes. Battle grouping rewrites the existing table within its original bounds. Conflicting writes from another module stop saving. All portrait slots continue to be verified by the shared saver, and normal header/checksum handling remains active.

Tests include byte-identical no-op saves; independent axe/hand-axe changes; a model of the class/gender/character scan after grouping; map-profile copies; movement changes; project round-trip/rollback; invalid IDs and changed loader rejection; combined portrait/text/animation saves; headerless output; binary diff boundaries; checksum and source preservation. No rendered-animation or emulator claims are made.
