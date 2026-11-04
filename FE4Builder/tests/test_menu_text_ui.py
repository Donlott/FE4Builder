import tempfile
import unittest
from unittest.mock import patch

from FE4Builder import App
from rom import Rom, Field
from menu_text import MenuText, catalogue
from menu_text_fixture import make_text_rom


class MenuTextWindowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = make_text_rom(self.directory.name)
        self.app = App()
        self.app.withdraw()
        self.app.rom = Rom(self.path)
        self.window = self.app.edit_menu_text()
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.directory.cleanup()

    def type(self, text):
        self.window.editor.delete('1.0', 'end')
        self.window.editor.insert('1.0', text)
        self.window.editor.edit_modified(True)
        self.window.changed()
        self.app.update_idletasks()

    def test_home_navigation_nonmodal_previews_and_live_dropdown_names(self):
        self.assertTrue(any(tool[1] == 'Menu Text Editor' for tool in self.app.home_tools))
        self.assertIsNone(self.app.grab_current())
        self.assertEqual(self.window.list.size(), 138)
        self.assertTrue(self.window.old_preview.find_all())
        self.type('B')
        self.assertTrue(self.window.pending())
        self.assertFalse(self.window.write_button.instate(['disabled']))
        self.assertTrue(self.window.save())
        self.assertFalse(self.window.pending())
        self.assertIn('B', self.window.list.get(0))
        field = Field('Name', 0, 1, {0: 'Old'}, reference='FE4 Weapon Names.txt')
        self.assertEqual(self.app.rom.field_options(field)[0], 'B')
        self.assertFalse(self.app.undo_button.instate(['disabled']))
        self.window.history(False)
        self.assertEqual(self.window.text(), 'A')
        self.window.history(True)
        self.assertEqual(self.window.text(), 'B')

    def test_failed_disk_save_rolls_back_rom_data_and_preserves_draft(self):
        before = bytes(self.app.rom.data)
        self.type('B')
        with (patch.object(self.app.rom, 'save_original', side_effect=OSError('disk fixture')),
              patch('menu_text_window.messagebox.showerror') as error):
            self.assertFalse(self.window.save())
        self.assertTrue(error.called)
        self.assertEqual(bytes(self.app.rom.data), before)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(self.window.pending())

    def test_invalid_text_search_and_cancelled_switch_preserve_draft(self):
        self.type('W' * 12)
        self.assertTrue(self.window.write_button.instate(['disabled']))
        self.window.search.set('not-a-match')
        self.assertEqual(self.window.list.size(), 0)
        self.assertEqual(self.window.text(), 'W' * 12)
        self.window.group.set('Skills')
        with patch('menu_text_window.ask_unsaved', return_value=None):
            self.window.change_category()
        self.assertEqual(self.window.group.get(), 'Item names')
        self.assertEqual(self.window.text(), 'W' * 12)
        with patch('menu_text_window.ask_unsaved', return_value=False):
            self.window.close()
        self.assertFalse(self.window.winfo_exists())

    def test_f5_uses_save_callback_and_wrong_rom_does_not_write(self):
        self.type('B')
        with patch.object(self.app, 'save_and_launch', return_value=True) as launch:
            self.assertTrue(self.window.launch())
            self.assertEqual(launch.call_args.kwargs['save_callback'], self.window.save)
        before = self.path.read_bytes()
        self.app.rom = Rom(self.path)
        with patch('menu_text_window.messagebox.showerror'):
            self.assertFalse(self.window.save())
        self.assertEqual(self.path.read_bytes(), before)

    def test_main_editor_draft_cancellation_prevents_text_write(self):
        before = self.path.read_bytes()
        self.type('B')
        with patch.object(self.app, 'settle', return_value=False):
            self.assertFalse(self.window.save())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(self.window.pending())


if __name__ == '__main__':
    unittest.main()
