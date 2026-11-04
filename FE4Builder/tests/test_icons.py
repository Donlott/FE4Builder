"""Artwork isolation, capacity/loader limits, packing and persistent baselines."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rom import Rom
from icons import (IconDocument, ARENA, SIZE, PRIVATE_GRAPHICS, SKILL_GRAPHICS, ITEM_GRAPHICS,
                   ITEM_LOOKUP, LOADERS, TABLES, SKILL_PALETTE_LOADERS, pack, unpack, read, tile, dma, split_atlas, join_atlas)
from icon_stats import IconSizeHistory, artwork_bytes
from portraits import pointer_for
from icon_fixture import fixture, icon


class IconTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory();self.root = Path(self.folder.name)
        self.path = fixture(self.root);self.rom = Rom(self.path);self.before = bytes(self.rom.data)
        self.doc = IconDocument(self.rom)

    def tearDown(self):self.folder.cleanup()

    def test_native_atlas_codec_and_opening_are_exact_noops(self):
        for kind in self.doc.art:
            for raw in self.doc.art[kind]:self.assertEqual(pack(unpack(raw)), raw)
            self.assertEqual(split_atlas(join_atlas(self.doc.art[kind])), self.doc.art[kind])
        self.assertFalse(self.doc.commit())
        self.assertEqual(bytes(self.rom.data), self.before)
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertFalse((self.root / 'FE4Builder Backups').exists())

    def test_skill_colors_follow_the_actual_palette_copy_sources(self):
        expected = [((15 - i) * 8, i * 8, ((i + 8) % 16) * 8) for i in range(16)]
        for context in range(3):self.assertEqual(self.doc.colors('skills', context), expected)
        inventory = [(i * 8,) * 3 for i in range(16)]
        self.assertEqual(self.doc.colors('items'), inventory)
        self.assertNotEqual(expected, inventory)
        # Repoint only the native copy-loop source operand. The editor must
        # follow the ROM rather than another guessed CGRAM-bank address.
        stat = [(31 - i, i, 8) for i in range(16)]
        compact = [(i, 31 - i, 16) for i in range(16)]
        for (at, _), source, colors in zip(SKILL_PALETTE_LOADERS, (0x1E02C0, 0x1E03C0), (stat, compact)):
            raw = b''.join((r | g << 5 | b << 10).to_bytes(2, 'little') for r, g, b in colors)
            self.rom.data[source:source + 32] = raw
            self.rom.data[at + 4:at + 7] = pointer_for(source - 2).to_bytes(3, 'little')
        fresh = IconDocument(self.rom)
        for context, colors in ((0, stat), (1, stat), (2, compact)):
            self.assertEqual(fresh.colors('skills', context), [tuple(c * 8 for c in rgb) for rgb in colors])
        self.assertEqual(fresh.colors('items'), inventory)

    def test_palette_loader_validation_and_copier_header(self):
        for at, _ in SKILL_PALETTE_LOADERS:
            self.rom.data[:] = self.before;self.rom.data[at] ^= 1
            before = bytes(self.rom.data)
            with self.assertRaisesRegex(ValueError, 'palette loader'):IconDocument(self.rom)
            self.assertEqual(bytes(self.rom.data), before)
        path = fixture(self.root, True);headered = IconDocument(Rom(path))
        expected = [((15 - i) * 8, i * 8, ((i + 8) % 16) * 8) for i in range(16)]
        self.assertEqual(headered.colors('skills'), expected)

    def test_private_item_variants_and_blank_library_survive_reopening(self):
        original = self.doc.art['items'][0]
        index = self.doc.add('items', icon(231));self.assertEqual(index, 111)
        self.doc.assign('items', 0, index)
        blank = self.doc.add('items', bytes(128))
        self.doc.commit();fresh = IconDocument(Rom(self.path))
        self.assertEqual(fresh.selected('items', 0), index)
        self.assertEqual(fresh.selected('items', 111), 0)
        self.assertEqual(fresh.art['items'][0], original)
        self.assertIn(blank, fresh.active('items'))
        self.assertEqual(fresh.art['items'][index], icon(231))

    def test_skill_addition_expands_all_dma_paths_without_overlapping_neighbors(self):
        original = read(self.rom, SKILL_GRAPHICS, 0xC00)
        index = self.doc.add('skills', icon(220));self.assertEqual(index, 24)
        self.doc.assign('skills', 1, index)
        self.doc.commit();fresh = IconDocument(Rom(self.path))
        self.assertEqual(fresh.selected('skills', 1, 0), 24)
        self.assertEqual(fresh.selected('skills', 1, 1), 24)
        self.assertEqual(fresh.selected('skills', 1, 2), 24)
        self.assertEqual(read(self.rom, SKILL_GRAPHICS, 0xC00), original)
        self.assertEqual(len(fresh.art['skills']), 32)
        for mirror in (0, 0x400000):
            for at, destination in LOADERS:
                self.assertEqual(read(self.rom, at + mirror, 9), dma(pointer_for(PRIVATE_GRAPHICS), 0x1000, destination))
        # Stat-screen upload ends exactly where the next native upload starts.
        self.assertEqual(0x6800 + len(fresh.art['skills']) * 128 // 2, 0x7000)
        self.assertEqual(self.path.stat().st_size, len(self.before))

    def test_capacity_and_invalid_assignments_fail_before_mutation(self):
        for _ in range(9):self.doc.add('items', icon(200))
        for _ in range(8):self.doc.add('skills', icon(210))
        baseline = deepcopy((self.doc.art, self.doc.refs, self.doc.flags))
        for kind in self.doc.art:
            with self.assertRaisesRegex(ValueError, 'full'):self.doc.add(kind, icon(201))
        for args in (('skills', 0, 0, 2), ('skills', 50, 0, 0), ('items', 0, 128, 0)):
            with self.assertRaises(ValueError):self.doc.assign(*args)
        self.assertEqual((self.doc.art, self.doc.refs, self.doc.flags), baseline)
        self.assertEqual(bytes(self.rom.data), self.before)

    def test_sprite_tile_numbers_do_not_overflow_into_palette_bits(self):
        for kind, base in (('items', 0x3620), ('skills', 0x3E80)):
            capacity = 120 if kind == 'items' else 32
            for index in range(capacity):
                for delta in (0, 1, 16, 17):
                    value = base + tile(index) + delta
                    self.assertEqual(value & 0xFE00, base & 0xFE00)
        # Physical padding in the inventory upload is not a usable new icon.
        self.assertNotEqual((0x3620 + tile(120)) & 0xFE00, 0x3620 & 0xFE00)
        padding = self.before[ITEM_GRAPHICS + 0x3C00:ITEM_GRAPHICS + 0x4000]
        self.doc.add('items', icon(235));self.doc.commit(optimize=True)
        self.assertEqual(read(self.rom, ITEM_GRAPHICS + 0x3C00, 0x400), padding)

    def test_optimization_shares_duplicates_preserves_appearance_and_reclaims_expansion(self):
        duplicate = self.doc.add('skills', self.doc.art['skills'][0])
        self.doc.assign('skills', 1, duplicate)
        duplicate_item = self.doc.add('items', self.doc.art['items'][2]);self.doc.assign('items', 0, duplicate_item)
        expected = {kind:[self.doc.art[kind][i] for i in self.doc.references(kind)] for kind in self.doc.art}
        before_size = self.doc.sizes();self.doc.commit();expanded = self.path.read_bytes()
        fresh = IconDocument(self.rom);fresh.commit(optimize=True)
        packed = IconDocument(self.rom)
        for kind in packed.art:self.assertEqual([packed.art[kind][i] for i in packed.references(kind)], expected[kind])
        self.assertEqual(len(packed.art['skills']), 24)
        self.assertEqual(artwork_bytes(before_size) - artwork_bytes(packed.sizes()), 256)
        for at, destination in LOADERS:self.assertEqual(read(self.rom, at, 9), dma(0xDE34C0, 0xC00, destination))
        self.assertEqual(read(self.rom, PRIVATE_GRAPHICS, 0x1000), bytes(0x1000))
        self.rom.undo();self.assertEqual(self.path.read_bytes(), expanded)
        self.rom.undo();self.assertEqual(self.path.read_bytes(), self.before)

    def test_only_planned_ranges_change_and_save_failure_rolls_back(self):
        self.doc.add('skills', icon(250));self.doc.replace('items', 1, [[3] * 16 for _ in range(16)])
        edits, _ = self.doc.plan();allowed = {i for at, raw in edits for i in range(at, at + len(raw))}
        with patch.object(self.rom, 'save_original', side_effect=OSError('disk fixture')):
            with self.assertRaises(OSError):self.doc.commit()
        self.assertEqual(bytes(self.rom.data), self.before);self.assertEqual(self.path.read_bytes(), self.before)
        self.doc.commit();after = bytes(self.rom.data)
        changed = {i for i, (a, b) in enumerate(zip(self.before, after)) if a != b}
        self.assertLessEqual(changed, allowed)
        for start, end in ((0x600000, ARENA), (ARENA + SIZE, 0x800000), (0x4FF20, 0x50000)):
            self.assertEqual(after[start:end], self.before[start:end])

    def test_stale_models_tampering_and_custom_loaders_are_guarded(self):
        stale = IconDocument(self.rom);self.doc.add('items', icon(240));self.doc.commit()
        stale.add('items', icon(241));before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, 'changed'):stale.commit()
        self.assertEqual(bytes(self.rom.data), before)
        self.rom.data[ARENA + 100] ^= 1
        with self.assertRaisesRegex(ValueError, 'invalid'):IconDocument(self.rom)
        for at in (0xBD70, 0x40C57A, 0xBD63, 0xCDEC, 0x9A397, 0xBDB5A):
            self.rom.data[:] = self.before;self.rom.data[at] ^= 1
            with self.assertRaises(ValueError, msg=hex(at)):IconDocument(self.rom)
        self.rom.data[:] = self.before;self.rom.data[ARENA] = 7
        occupied = IconDocument(self.rom);occupied.add('items', icon(230));before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, 'occupied'):occupied.commit()
        self.assertEqual(bytes(self.rom.data), before)

    def test_headered_ff_storage_backup_undo_redo(self):
        path = fixture(self.root, True);data = bytearray(path.read_bytes());data[ARENA + 512:ARENA + 512 + SIZE] = b'\xff' * SIZE;path.write_bytes(data)
        rom = Rom(path);doc = IconDocument(rom);doc.add('skills', icon(240));doc.commit();saved = path.read_bytes()
        self.assertEqual(saved[:512], bytes([43]) * 512)
        self.assertEqual(rom.last_backup.read_bytes(), bytes(data))
        self.assertTrue(IconDocument(Rom(path)).expanded)
        rom.undo();self.assertEqual(path.read_bytes(), bytes(data))
        rom.redo();self.assertEqual(path.read_bytes(), saved)

    def test_baselines_preferences_and_first_report_persist_without_overwriting_bad_config(self):
        config = self.root / 'sizes.json';history = IconSizeHistory(self.doc, config)
        expected = history.original.copy();history.update(True, True)
        self.doc.add('skills', icon(250));self.doc.commit(baseline=history.original)
        fresh = IconDocument(self.rom);restored = IconSizeHistory(fresh, config)
        self.assertEqual(restored.original, expected);self.assertTrue(restored.optimize);self.assertTrue(restored.report_shown)
        # Moving a patched ROM retains its original accounting in ROM metadata.
        moved = IconSizeHistory(fresh, self.root / 'moved.json');self.assertEqual(moved.original, expected)
        config.write_text('{broken');bad = IconSizeHistory(fresh, config)
        self.assertIsNotNone(bad.error);bad.update(True)
        self.assertEqual(config.read_text(), '{broken')


if __name__ == '__main__':unittest.main()
