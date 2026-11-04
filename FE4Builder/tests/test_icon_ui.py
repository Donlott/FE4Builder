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
from icons import IconDocument, import_png, pack
from portraits import export_png
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
