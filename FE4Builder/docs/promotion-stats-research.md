# Negative personal stats after class changes

This investigation used the supplied 8 MiB headered ROM, SHA256
`ad585c023f2692b0de31e648ff167d01398628b6a8cbcc22c00b7147ed6da6f1`.
All PC offsets below exclude the 512-byte copier header.

The reference getter names and data structures are in
[ulti-mage/FireEmblem4, Bank84.asm](https://github.com/ulti-mage/FireEmblem4/blob/387b2e4c63b72b0d3f2854eaa69f26946d83b383/SRC/Bank84.asm).
The exact instructions were independently checked in the uploaded ROM.

## Cause and expected behavior

The promotion wrapper at `$84:ABB0` snapshots effective stats, calls the class
setter `$84:A191`, snapshots again and subtracts before/after values for the
animation. The setter changes the class byte; it does not corrupt the six
personal stat bytes. The defect is in the effective-stat getters shared by
promotion, status displays and battle calculations:

```asm
CLC
ADC personalStat,X
AND #$00FF
CMP #31
BCC done
LDA #30
```

The personal byte uses signed values, but the byte mask wraps a negative total.
A class base 0 plus personal Magic −7 becomes 249, then gets capped to 30.
In the supplied ROM Wendell's personal Magic/Resistance are −7/−6; Sage's bases
are 15/12 and Sniper's are 0/3. The native code reproduces 8/6 → 30/30 while
keeping both personal bytes unchanged. Correct signed totals are 8/6 → 0/0.

The fix computes `clamp(class_base + signed_personal, 0, 30)` in 16-bit
arithmetic. Class bases remain unsigned bytes; personal bytes are sign-extended
from −128..127. Existing ring and weapon bonuses are added in their original
order after this base-stat cap, so an allowed +5 above 30 still works. Enemy
stat getter branches bypass the replacement arithmetic. HP/Luck/movement and
the character's underlying personal values are not changed.

## Hooks and storage

| Stat | Replaced 15-byte calculation at PC |
| --- | --- |
| Strength | `049B57` |
| Magic | `049BB2` |
| Skill | `049C0D` |
| Speed | `049C68` |
| Defense | `049CD4` |
| Resistance | `049D40` |

Each replacement is a JSL plus NOP padding, retaining native branch targets and
epilogues. Six small helper entries load the correct absolute-indexed personal
byte. They share a signed-add/clamp routine using only a temporary word on the
native stack, preserving X/Y, DBR and direct page. The caller's original
epilogue restores its status register.

An 81-byte helper program and integrity metadata occupy verified zero padding
at PC `04FF20–04FFFF`, after the uploaded ROM's last bank-$84 code at `04FF0A`.
The game executes the helpers through CPU `$84:FF40`. Installation requires
uniform 00/FF padding, checks all seven hook sites and the relevant surrounding
instructions, then writes the entire patch as one normal ROM transaction.
Removal verifies helper SHA256, program bytes, metadata and every hook before
restoring all original instructions and the original padding fill byte.
No ROM expansion, new SRAM, or edited class/personal-stat tables are needed.

## Negative promotion deltas

The promotion snapshot/delta routine at `$84:AC50` correctly produces signed
16-bit decreases, such as Magic −8 and Resistance −6 in the reference test.
The full-battle gain controller at `$9E:95D3` originally treats every nonzero
delta as an unsigned **+digit** sprite index. This would show invalid gain
artwork for a decrease even after the underlying stat arithmetic is repaired.

The four-byte load/zero-branch at PC `1E95D3` is redirected to a helper. Zero
and negative deltas rejoin the native advance-to-next-stat path at `$9E:961D`;
positive deltas rejoin at `$9E:95D7` unchanged. This skips only the unsigned
gain flash for a decrease. Actual post-promotion values and signed delta
buffers remain intact; no stat preservation or compensating growth is added.

## Validation

The emitted helper bytes ran in a 65816 instruction interpreter for **73,216
cases**: every unsigned class-base/signed personal-byte combination for the
shared arithmetic, plus all five other stat offsets with representative bases
and every raw personal byte. This covers negative extremes, crossing zero,
positive overflow, nonzero adjacent bytes, stack balance and register contracts.

The complete native getters then ran for **4,752 cases** across all 72 actual
class records and six stats. An additional **90 equipment cases** checked that
ring bonuses still apply after the base-stat cap, including results above 30.
Enemy branch routing was checked separately with observable fixture returns.

The real `$84:ABB0` promotion wrapper, class setter, effective-stat snapshots
and delta builder were executed. Fixtures replaced only unrelated action setup,
sprite bookkeeping and asynchronous scene launch. Personal bytes, inventory
data and level stayed intact. The native gain controller completed in **86
frames** with its number/sign sprite routines retained, graphics/SFX APIs
stubbed, and negative deltas excluded from unsigned gain flashes.

The patch was also installed on the previously generated signed personal-stat
save/load ROM. Full raw stat bytes survived reopening all **four save slots**;
post-load Sniper totals were correct. SRAM header bytes and the original
save/growth helper remained byte-identical. Removing the promotion patch
restored that patched input ROM exactly. The uploaded source file was untouched.

ROM-free tests cover installation/removal, exact affected byte ranges, copier
headers and FF padding, altered code/storage, tampered removal, disk-write
rollback, automatic backup/undo/redo and the Patches window controls. The full
portable desktop/package suite includes these regressions. This is instruction-
level and editor verification; a complete rendered SNES playtest has not been
performed. Loading an already corrupted old save cannot reconstruct lost
personal bytes, so the earlier save/load fix remains relevant.
