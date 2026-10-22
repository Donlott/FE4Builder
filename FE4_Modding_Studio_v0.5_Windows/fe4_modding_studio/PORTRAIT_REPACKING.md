# Portrait storage optimization (v0.5)

## Use

1. Open your latest working ROM and import the replacement PNG sheets.
2. Click **Preview packing…**. The first preview may take around a minute;
   compressed results are cached for subsequent previews and saving.
3. Enable **Optimize portrait storage when saving**.
4. Click **Save ROM copy…**, then test that copy in an emulator.

Stage the whole batch before saving to share the available storage across all
replacements. PNG dimensions remain 64×64; this feature addresses compressed
byte size, not larger image dimensions. Preview does not enable the checkbox.

With optimization enabled, the editor independently re-encodes every unique
portrait sheet, packs those streams into eligible portrait storage, and updates
all 248 graphics pointers. Identical pixels share one stream even when their
palettes differ. A smaller replacement can fund a larger replacement anywhere
in the pool; they need not have adjacent slot IDs. Existing palettes stay in
place where safe; conflicting shared-palette edits receive separate copies.

Without the checkbox, the previous conservative in-place saving behavior remains.

## What may be overwritten

The automatic pool is the intersection of:

- bytes directly read by the live portrait decompressor, excluding bytes visited
  only through compressed-stream lookbacks;
- the supported FE4 portrait graphics area (headerless lower half-bank windows
  A65B5–A8000, B0000–B8000 through F0000–F8000, and 100000–105639).

Palette allocations, pointer tables and ROM headers are excluded from that pool.
Those bounds were checked against the original supplied project ROM and its live
portrait table; table locations and decoder behavior follow ulti-mage/FireEmblem4.
They are eligibility bounds, not a claim that every byte between them is free.

No gaps, abandoned tails, other half-banks, or merely zero-filled regions become
available automatically. Previously relocated portrait storage outside these
windows is left untouched. Its pixels can be moved back into the eligible pool,
but its old location is not reclaimed. Optional **Reserve space…** adds only the
range you explicitly designate as unused; blank bytes alone cannot prove that.

New compressed streams do not borrow compressed bytes from other portraits and
never cross a 32 KiB window. The planner decodes and checks all 248 outputs. It
also checks its writes against an exact byte allowlist. Text and animation edits
are applied separately, then portraits are checked again for conflicting writes.
Only the requested edits, portrait pointers/data, and ROM checksums may change.
The copier header is retained, and the input file cannot be overwritten.

## Limits

This is a supported-layout portrait relocator, not an arbitrary ROM relocator.
It does not move unrelated assets or code. Their references may be bank-relative,
computed or hard-coded, and a generic search for pointer-looking bytes would not
prove relocation safe. Hacks that deliberately reuse portrait bytes for another
subsystem require a separate ownership/profile audit; the editor cannot detect
all such hidden consumers from a byte scan.

Packing uses largest-first best-fit, with an existing-stream placement fallback.
If no placement fits, saving fails before writing the output. Fragmentation can
prevent a fit even when the sum of free bytes is sufficient. Reserving a verified
unused region or reducing portrait complexity can resolve this.

The unused balance shown in Preview belongs to the currently open ROM's pool.
On reopening a saved copy, only bytes still directly used by its portraits can be
rediscovered; unused tails are protected again. No persistent free-space map is
written into the ROM. Keep your source ROM and stage a batch together to retain
access to its full pool. Further edits can still trade the space occupied by the
portraits in the reopened copy.

## Validation

On FE4_Archanea_Hero_Hand_Axe_Test_v2.smc, a full no-content-change repack uses
186,170 bytes for 151 unique sheets across 248 slots, from 192,479 eligible
bytes, leaving 6,309 bytes in that plan. No reservation is needed for that case.
This budget changes with the input ROM and staged portraits.

`test_repack.py` exercises full round trips, exact preservation outside the
allowlist, reopening/repacking, larger/smaller replacements, graphics alias
splitting, shared-palette splitting, unknown gaps, decoder lookback tracking,
32 KiB boundaries, checksums, and failure without changing existing files.
Text and animation regression suites are also included. Tests do not substitute
for an emulator check; no interactive GUI or in-game test was performed here.
