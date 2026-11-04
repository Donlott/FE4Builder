"""ROM-free PNG/palette and nonmodal icon workspace regressions."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
import zlib

from FE4Builder import App
from rom import Rom
from icons import IconDocument, import_png, pack, unpack, SKILL_PALETTE_LOADERS, ITEM_LOOKUP, ITEM_STATUS_LOOKUP, WEAPON_TYPE_LOOKUP, tile
from portraits import export_png
from intro_graphics import indexed_png
from icon_fixture import fixture


class IconUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory();self.root = Path(self.folder.name)
        self.path = fixture(self.root);self.rom = Rom(self.path)
        self.preferences = patch('icon_stats.DATA_DIR', self.root);self.preferences.start()
        self.context = patch('ui_common.DATA_DIR', self.root);self.context.start()
        self.app = App();self.app.rom = self.rom

    def tearDown(self):
        self.app.destroy();self.preferences.stop();self.context.stop();self.folder.cleanup()

    def window(self, kind='items', record=0):return self.app.edit_icons(kind, record)

    def png(self, document, kind='items', index=0):
        path = self.root / 'icon.png';path.write_bytes(document.png(kind, index));return path

    def test_all_indexed_icons_roundtrip_exactly_and_dimensions_and_alpha_are_guarded(self):
        doc = IconDocument(self.rom)
        for kind in doc.art:
            for i, original in enumerate(doc.art[kind]):
                path = self.png(doc, kind, i);raw, reduced = import_png(self.app, path, doc.colors(kind))
                self.assertEqual(raw, original);self.assertFalse(reduced)
        path.write_bytes(export_png([[0] * 32 for _ in range(16)], doc.colors('items')))
        with self.assertRaisesRegex(ValueError, '16 x 16'):import_png(self.app, path, doc.colors('items'))
        def chunk(kind, raw):return struct.pack('>I', len(raw)) + kind + raw + struct.pack('>I', zlib.crc32(kind + raw) & 0xFFFFFFFF)
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 6, 0, 0, 0))
        path.write_bytes(png + chunk(b'IDAT', zlib.compress((b'\0' + bytes([40, 40, 40, 128]) * 16) * 16)) + chunk(b'IEND', b''))
        with self.assertRaisesRegex(ValueError, 'partial transparency'):import_png(self.app, path, doc.colors('items'))

    def test_color_reduction_is_explicit_and_does_not_modify_rom(self):
        doc = IconDocument(self.rom);colors = doc.colors('items');rows = [[0] * 16 for _ in range(16)];rows[4][4] = 1
        colors[1] = (255, 1, 15);path = self.root / 'foreign.png';path.write_bytes(export_png(rows, colors))
        before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, 'outside'):import_png(self.app, path, doc.colors('items'))
        raw, reduced = import_png(self.app, path, doc.colors('items'), True)
        self.assertTrue(reduced);self.assertNotEqual(raw, bytes(128));self.assertEqual(bytes(self.rom.data), before)

    def test_default_skill_preview_thumbnails_and_png_use_the_in_game_colors(self):
        window = self.window('skills', 0)
        before = bytes(self.rom.data)
        expected = [((15 - i) * 8, i * 8, ((i + 8) % 16) * 8) for i in range(16)]
        self.assertEqual(window.context.current(), 0)
        self.assertEqual(window.document.colors('skills'), expected)
        rows = unpack(window.document.art['skills'][window.index])
        x, y = next((x, y) for y, line in enumerate(rows) for x, value in enumerate(line) if value)
        self.assertEqual(window.photos[0].get(x, y), expected[rows[y][x]])
        rectangle = window.canvas.find_all()[y * 16 + x]
        self.assertEqual(window.canvas.itemcget(rectangle, 'fill'), '#%02x%02x%02x' % expected[rows[y][x]])
        path = self.root / 'export.png'
        with patch('icon_window.filedialog.asksaveasfilename', return_value=str(path)):window.export()
        exported, palette = indexed_png(path)
        self.assertEqual(palette, expected);self.assertEqual(exported, rows)
        with patch('icon_window.filedialog.askopenfilename', return_value=str(path)):window.import_image()
        self.assertFalse(window.pending());self.assertEqual(bytes(self.rom.data), before)

    def test_context_changes_refresh_thumbnails_and_missing_entries_use_help_palette(self):
        at = SKILL_PALETTE_LOADERS[1][0]
        self.rom.data[at + 4:at + 7] = bytes.fromhex('BE 02 DE')
        self.rom.data[0x1E02C0:0x1E02E0] = b''.join((i | (31 - i) << 5 | 16 << 10).to_bytes(2, 'little') for i in range(16))
        window = self.window('skills', 1);before = bytes(self.rom.data)
        window.context.current(2);window.context.event_generate('<<ComboboxSelected>>')
        self.assertEqual(window.current, 1)
        self.assertEqual(window.index, window.document.refs['skills'][2][0])
        rows = unpack(window.document.art['skills'][window.index])
        x, y = next((x, y) for y, line in enumerate(rows) for x, value in enumerate(line) if value)
        thumb = window.photos[list(window.list.get_children()).index('1')]
        expected = [(i * 8, (31 - i) * 8, 128) for i in range(16)]
        self.assertEqual(thumb.get(x, y), expected[rows[y][x]])
        path = self.root / 'compact.png'
        with patch('icon_window.filedialog.asksaveasfilename', return_value=str(path)):window.export()
        self.assertEqual(indexed_png(path)[1], expected)
        # Canto is absent from the compact menu; its fallback artwork must use
        # stat-help colors, not the selected but unavailable compact context.
        window.populate(0)
        with patch('icon_window.filedialog.asksaveasfilename', return_value=str(path)):window.export()
        self.assertEqual(indexed_png(path)[1], [((15 - i) * 8, i * 8, ((i + 8) % 16) * 8) for i in range(16)])
        self.assertFalse(window.pending());self.assertEqual(bytes(self.rom.data), before)

    def test_pixel_edits_are_private_and_save_retains_optimization_and_undo(self):
        window = self.window();self.app.update()
        self.assertIsNone(self.app.grab_current());self.assertIn(window, self.app.editor_windows)
        original = window.document.art['items'][0]
        window.paint(SimpleNamespace(x=80, y=80))
        self.assertTrue(window.pending());self.assertEqual(window.document.refs['items'][111], 0)
        self.assertEqual(window.document.art['items'][0], original)
        self.assertNotEqual(window.document.refs['items'][0], 0)
        window.optimize.set(True);window.preference()
        with patch('icon_window.messagebox.showinfo') as info:self.assertTrue(window.save());self.assertEqual(info.call_count, 1)
        self.assertTrue(window.optimize.get());self.assertFalse(window.pending())
        self.assertTrue(window.size_history.report_shown);self.assertTrue(self.app.undo_button.instate(['!disabled']))
        saved = self.path.read_bytes();window.history(False)
        self.assertNotEqual(self.path.read_bytes(), saved);self.assertTrue(window.optimize.get())
        window.history(True);self.assertEqual(self.path.read_bytes(), saved)
        window.close();self.assertNotIn(window, self.app.editor_windows)

    def test_saved_item_display_repair_is_available_without_repainting_and_undoable(self):
        self.rom.data[ITEM_LOOKUP:ITEM_LOOKUP + 2] = tile(40).to_bytes(2, 'little')
        before = bytes(self.rom.data);self.path.write_bytes(before)
        self.app.rom = self.rom = Rom(self.path)
        window = self.window();window.optimize.set(False);window.update_space()
        self.assertTrue(window.pending());self.assertFalse(window.document.dirty)
        self.assertFalse(window.write_button.instate(['disabled']))
        self.assertIn('Display repair available', window.status.get())
        self.assertEqual(self.path.read_bytes(), before)
        with patch('icon_window.messagebox.showinfo'):self.assertTrue(window.save())
        self.assertFalse(window.pending())
        self.assertEqual(bytes(self.rom.data[ITEM_STATUS_LOOKUP:ITEM_STATUS_LOOKUP + 2]), (tile(40) * 32).to_bytes(2, 'little'))
        self.assertEqual(self.rom.last_backup.read_bytes(), before)
        window.history(False);self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(window.pending())
        with patch('icon_window.ask_unsaved', side_effect=AssertionError('repair is not a staged draft')):
            self.assertTrue(window.settle())
            window.history(True)
        self.assertFalse(window.pending())

    def test_private_item_painting_preserves_shared_weapon_type_artwork(self):
        self.rom.data[WEAPON_TYPE_LOOKUP:WEAPON_TYPE_LOOKUP + 2] = (tile(110) * 32).to_bytes(2, 'little')
        window = self.window(record=110);old = window.document.art['items'][110]
        self.assertEqual(window.document.users('items', 110), [(110, None)])
        window.paint(SimpleNamespace(x=80, y=80))
        self.assertNotEqual(window.document.selected('items', 110), 110)
        self.assertEqual(window.document.art['items'][110], old)

    def test_skill_contexts_new_icon_assignment_and_failed_import_are_atomic(self):
        window = self.window('skills', 1)
        path = self.png(window.document, 'skills', 2)
        with patch('icon_window.filedialog.askopenfilename', return_value=str(path)):
            window.add_image()
        self.assertEqual(len(window.document.art['skills']), 32)
        self.assertEqual(window.document.selected('skills', 1, 2), 24)
        self.assertIn('+1,024', window.warning.get())
        window.context.current(2);window.populate(0)
        before = deepcopy((window.document.art, window.document.refs, window.document.flags))
        with (patch('icon_window.filedialog.askopenfilename', return_value=str(path)),
              patch('icon_window.messagebox.showerror') as error):
            window.add_image();self.assertTrue(error.called)
        self.assertEqual((window.document.art, window.document.refs, window.document.flags), before)

    def test_write_failure_and_sibling_editor_changes_preserve_staged_artwork(self):
        window = self.window();window.paint(SimpleNamespace(x=80, y=80));before = bytes(self.rom.data)
        with (patch.object(self.rom, 'save_original', side_effect=OSError('disk fixture')),
              patch('icon_window.messagebox.showerror') as error):
            self.assertFalse(window.save());self.assertTrue(error.called)
        self.assertEqual(bytes(self.rom.data), before);self.assertTrue(window.pending())
        self.rom.data[0x8000] ^= 1
        with patch('icon_window.messagebox.showerror') as error:
            self.assertFalse(window.save());self.assertIn('changed', error.call_args.args[1])
        self.assertTrue(window.pending())

    def test_painting_a_shared_skill_grows_the_picker_and_keeps_hidden_skills_hidden(self):
        window = self.window('skills', 0)
        window.document.refs['skills'][0][0] = None
        original = window.document.art['skills'][0]
        window.display();window.paint(SimpleNamespace(x=80, y=80))
        self.assertEqual(len(window.document.art['skills']), 32)
        self.assertEqual(len(window.assignment['values']), 32)
        self.assertEqual(window.document.art['skills'][0], original)
        self.assertIsNone(window.document.refs['skills'][0][0])
        self.assertEqual(window.document.refs['skills'][1][0], 24)

    def test_new_editor_navigation_and_no_rom_message(self):
        names = [row[1] for row in self.app.home_tools]
        self.assertIn('Icon Editor', names)
        self.app.rom = None
        with patch('icon_window.messagebox.showinfo') as info:
            self.assertIsNone(self.app.edit_icons());self.assertTrue(info.called)


if __name__ == '__main__':unittest.main()
