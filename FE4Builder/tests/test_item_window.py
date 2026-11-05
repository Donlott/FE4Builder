"""Combined item workspace: selection, high slots, navigation and safe writes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from rom import Rom, character_modules
from item_expansion import ItemExpansion, record, enabled
from item_expansion_fixture import fixture


class ItemWindowTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=fixture(self.root);self.rom=Rom(self.path)
        self.preference=patch('ui_common.DATA_DIR',self.root);self.preference.start()
        from FE4Builder import App
        self.app=App();self.app.withdraw();self.app.rom=self.rom

    def tearDown(self):self.app.destroy();self.preference.stop();self.folder.cleanup()

    def test_home_and_inventory_links_open_one_combined_modeless_editor(self):
        original=bytes(self.rom.data);window=self.app.edit_items()
        self.assertEqual(len(window.visible),138);self.assertIsNone(self.app.grab_current())
        self.assertIn(window,self.app.editor_windows)
        self.assertEqual(bytes(self.rom.data),original)
        self.assertIs(self.app.edit_items('slots',7),window)
        self.assertEqual(window.kind,'slots');self.assertEqual(window.current,7)
        self.assertEqual(len(window.visible),140)
        window.open_item(0);self.assertEqual(window.kind,'items');self.assertEqual(window.current,0)
        self.assertTrue(window.preview_picture.cget('image'))

    def test_sparse_fe_item_and_slot_save_reopen_and_failure_rolls_back(self):
        model=ItemExpansion(self.rom);model.add_item(0x28,254);model.add_slot(254,254);self.rom.save_original('Enable fixture')
        window=self.app.edit_items('items',254)
        field=next(i for i,f in enumerate(window.module.fields) if f.name=='Power')
        window.controls[field][0].set('17');self.assertTrue(window.pending())
        before=self.path.read_bytes()
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')),patch('item_window.messagebox.showerror'):
            self.assertFalse(window.save())
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(window.pending());self.assertTrue(window.save())
        self.assertEqual(record(Rom(self.path),254)[11],17)
        window=self.app.edit_items('slots',254)
        self.assertEqual(window.current,254);self.assertEqual(window.model.assignments[254],254)
        self.assertNotIn(141,window.visible)
        self.assertEqual(window.model.sizes()['save_item_bytes'],794)

    def test_pending_view_switch_saves_to_the_original_view(self):
        window=self.app.edit_items('items',0)
        i=next(i for i,f in enumerate(window.module.fields) if f.name=='Power')
        window.controls[i][0].set('17')
        window.view.current(1)
        with patch('item_window.ask_unsaved',return_value=True):window.change_view()
        self.assertEqual(window.kind,'slots');self.assertEqual(record(self.rom,0)[11],17)
        self.assertEqual(ItemExpansion(self.rom).assignments[1],0)

    def test_stale_form_cannot_overwrite_a_sibling_editor_after_search(self):
        window=self.app.edit_items('items',0)
        i=next(i for i,f in enumerate(window.module.fields) if f.name=='Power')
        window.controls[i][0].set('17');self.rom.data[0x3EAE4+11]=19
        window.search.set('A')
        before=bytes(self.rom.data)
        with patch('item_window.messagebox.showerror') as error:
            self.assertFalse(window.save());self.assertIn('another editor',error.call_args.args[1])
        self.assertEqual(bytes(self.rom.data),before)

    def test_high_slot_appears_in_event_and_character_choices_and_links_navigate(self):
        model=ItemExpansion(self.rom);model.add_slot(0,254);self.rom.save_original('Enable slot')
        from event_commands import player_item_options
        self.assertIn(254,player_item_options(self.rom));self.assertNotIn(141,player_item_options(self.rom))
        field=next(f for f in character_modules()[0].fields if f.reference=='FE4 Player Equipment.txt')
        self.assertIn(254,self.rom.field_options(field));self.assertNotIn(255,player_item_options(self.rom))
        window=self.app.edit_items('slots',254)
        target=('record','Character Editor',character_modules()[0].name,0)
        with patch.object(self.app,'go_to_record',return_value=True) as go:
            self.assertTrue(window.go_location(SimpleNamespace(target=target)))
            go.assert_called_once_with(*target[1:])


if __name__=='__main__':unittest.main()
