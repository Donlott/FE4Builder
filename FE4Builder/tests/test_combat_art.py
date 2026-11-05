"""Physical animation aliases, bounded patch storage, preservation and repair UI."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rom import Rom
from combat_art import CombatArtwork, ARENA, SIZE, STYLES, LOOKUP, program
from item_art import ItemArt, ASSIGNMENTS
from icon_fixture import fixture


def combat_fixture(directory, header=False):
    path = fixture(directory, header);rom = Rom(path)
    def put(at, raw):rom.data[at + rom.header:at + rom.header + len(raw)] = raw
    _, hooks, _ = program()
    for at, (old, _) in hooks.items():put(at, old)
    guards = ((0x15A1F5, 'BF B9 83 99'), (0x16DC7C, 'DA E0 00 00 D0 05 A2 00 00 80 03 A2 0E 00'),
              (0x16DC91, 'BF 2D 83 99'), (0x16DCB6, 'BF 2E 83 99'), (0x16DCBC, 'BF 2F 83 99'),
              (0x1E8E36, 'BF C4 8E 9E'), (0x1E8E8F, 'BF C4 8E 9E'), (0x1586BB, 'BF 25 87 99'))
    for at, code in guards:put(at, bytes.fromhex(code))
    put(STYLES, b'\xff' * 126)
    art = ItemArt(rom)
    for item, style, sprite, reach in ((0x28, 0x23, 33, 1), (0x2C, 0x63, 38, 2),
                                       (0x2D, 0x63, 36, 2), (0x60, 0x86, 38, 1), (0x66, 0x86, 33, 2)):
        module, index = art.record(item);at = rom.address(module, index)
        stats = {'Type': 0, 'Weapon Type': 2, 'Minimum Range': 1, 'Maximum Range': reach, 'Rank': 255 if item == 0x2C else 1}
        for f in module.fields:
            if f.name in stats:rom.data[at + f.offset:at + f.offset + f.size] = stats[f.name].to_bytes(f.size, 'little')
        put(STYLES + item, bytes([style]));put(ASSIGNMENTS + item * 2, bytes([sprite, 20]))
    path.write_bytes(rom.data)
    return path


class CombatArtTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory();self.root = Path(self.folder.name)
        self.path = combat_fixture(self.root);self.rom = Rom(self.path);self.before = bytes(self.rom.data)
        self.preferences = patch('ui_common.DATA_DIR', self.root);self.preferences.start()

    def tearDown(self):self.preferences.stop();self.folder.cleanup()

    def test_opening_is_read_only_and_suggestions_match_sprite_and_range(self):
        model = CombatArtwork(self.rom)
        self.assertEqual(model.candidates(0x60)[0], 0x2C)
        self.assertEqual(model.candidates(0x66)[0], 0x2D)
        self.assertNotIn(0x28, model.candidates(0x66))
        self.assertEqual(model.plan(0x60, None), [])
        self.assertEqual(model.plan(0x28, 0x28), [])
        self.assertEqual(bytes(self.rom.data), self.before)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_repair_preserves_all_item_data_and_icons_and_reopens_with_both_aliases(self):
        for item, donor in ((0x60, 0x2C), (0x66, 0x2D)):
            model = CombatArtwork(self.rom);model.commit(item, donor)
        fresh = CombatArtwork(Rom(self.path))
        self.assertEqual(fresh.aliases[0x60], 0x2C);self.assertEqual(fresh.aliases[0x66], 0x2D)
        self.assertEqual(sum(v != 255 for v in fresh.aliases), 2)
        allowed = set(range(ARENA, ARENA + SIZE))
        for at, (old, new) in program()[1].items():
            allowed.update(range(at, at + len(new)))
            self.assertEqual(bytes(self.rom.data[at:at + len(new)]), new)
        changed = {i for i, (a, b) in enumerate(zip(self.before, self.rom.data)) if a != b}
        self.assertLessEqual(changed, allowed)
        self.assertEqual(bytes(self.rom.data[STYLES:STYLES + 126]), self.before[STYLES:STYLES + 126])
        self.assertEqual(bytes(self.rom.data[ASSIGNMENTS:ASSIGNMENTS + 250]), self.before[ASSIGNMENTS:ASSIGNMENTS + 250])

    def test_removing_one_alias_preserves_the_other_and_last_removal_restores_all_native_code(self):
        CombatArtwork(self.rom).commit(0x60, 0x2C);CombatArtwork(self.rom).commit(0x66, 0x2D)
        CombatArtwork(self.rom).commit(0x60, None)
        self.assertEqual(CombatArtwork(self.rom).aliases[0x66], 0x2D)
        CombatArtwork(self.rom).commit(0x66, None)
        self.assertEqual(bytes(self.rom.data), self.before)
        self.rom.undo();self.assertEqual(CombatArtwork(self.rom).aliases[0x66], 0x2D)

    def test_invalid_range_custom_code_storage_corruption_and_stale_models_are_atomic(self):
        with self.assertRaises(ValueError):CombatArtwork(self.rom).commit(0x66, 0x28)
        for at in (0x15A1ED, 0x16DC8A, 0x1E8E01, 0x16DC91, ARENA):
            self.rom.data[:] = self.before;self.rom.data[at] ^= 1
            before = bytes(self.rom.data)
            with self.assertRaises(ValueError):CombatArtwork(self.rom)
            self.assertEqual(bytes(self.rom.data), before)
        self.rom.data[:] = self.before;stale = CombatArtwork(self.rom)
        CombatArtwork(self.rom).commit(0x60, 0x2C)
        with self.assertRaisesRegex(ValueError, 'changed'):stale.commit(0x66, 0x2D)
        self.rom.data[ARENA + 0x300] ^= 1
        with self.assertRaisesRegex(ValueError, 'changed'):CombatArtwork(self.rom)

    def test_headered_ff_space_save_failure_and_backup_undo_redo(self):
        self.path = combat_fixture(self.root, True)
        raw = bytearray(self.path.read_bytes());raw[ARENA + 512:ARENA + 512 + SIZE] = b'\xff' * SIZE
        self.path.write_bytes(raw);rom = Rom(self.path);model = CombatArtwork(rom)
        with patch.object(rom, 'save_original', side_effect=OSError('disk fixture')):
            with self.assertRaises(OSError):model.commit(0x60, 0x2C)
        self.assertEqual(bytes(rom.data), bytes(raw));self.assertEqual(self.path.read_bytes(), bytes(raw))
        model.commit(0x60, 0x2C);saved = self.path.read_bytes()
        self.assertEqual(saved[:512], bytes(raw[:512]));self.assertEqual(rom.last_backup.read_bytes(), bytes(raw))
        self.assertEqual(CombatArtwork(Rom(self.path)).aliases[0x60], 0x2C)
        rom.undo();self.assertEqual(self.path.read_bytes(), bytes(raw))
        rom.redo();self.assertEqual(self.path.read_bytes(), saved)

    def test_ui_repairs_both_items_without_a_modal_grab_or_artwork_changes(self):
        from FE4Builder import App
        app = App();app.withdraw();app.rom = self.rom
        try:
            app.show_editor('Item Editor')
            table = next(i for i, m in enumerate(app.modules) if m.name == 'FE4 Weapon/Staff Editor 1')
            app.record = table, 0x60;app.render()
            window = app.edit_current_combat()
            self.assertIsNone(app.grab_current());self.assertIn(window, app.editor_windows)
            self.assertEqual(window.donors[window.donor.current() - 1], 0x2C)
            self.assertEqual(self.path.read_bytes(), self.before)
            self.assertTrue(window.save())
            window.item.current(window.items.index(0x66));window.refresh()
            self.assertEqual(window.donors[window.donor.current() - 1], 0x2D)
            self.assertTrue(window.save())
            self.assertEqual(CombatArtwork(self.rom).aliases[0x66], 0x2D)
            app.rom = Rom(combat_fixture(self.root, True))
            with patch('combat_art_window.messagebox.showerror') as error:
                self.assertFalse(window.save());self.assertTrue(error.called)
        finally:app.destroy()


if __name__ == '__main__':unittest.main()
