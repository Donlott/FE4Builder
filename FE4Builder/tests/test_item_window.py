"""Combined item workspace: selection, high slots, navigation and safe writes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from rom import Rom, character_modules, category_modules, MODULES, load_module
from item_expansion import ItemExpansion, record, enabled, table, read
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

    def open_module(self,window,name,index=0):
        window.module_selector.set(name);window.change_module()
        if index:window.load(index)
        return window.module

    def seed_held_art(self):
        from fe4_codec import compress
        from portraits import pointer_for
        from item_art import GRAPHICS, PALETTES
        from item_expansion import put
        # Distinct native 4bpp graphics and palettes make stale previews visible.
        for sprite in (0,1):
            raw=bytes([255,0] if sprite==0 else [0,255])*8+bytes(16)
            at=0x218000+sprite*0x100
            put(self.rom,at,compress(raw*32))
            put(self.rom,GRAPHICS+sprite*3,pointer_for(at).to_bytes(3,'little'))
        for palette,colors in enumerate(((31,31<<5),(31<<10,31|(31<<10)))):
            put(self.rom,PALETTES+palette*30,b''.join(c.to_bytes(2,'little') for c in (*colors,*([0]*13))))
        put(self.rom,table(self.rom,'held'),bytes(250))
        self.path.write_bytes(self.rom.data)
        self.rom=Rom(self.path);self.app.rom=self.rom

    def test_inventory_and_held_previews_show_draft_sprite_palette_and_staff_layout(self):
        self.seed_held_art();before=bytes(self.rom.data)
        window=self.app.edit_items('items',0)
        self.assertTrue(window.preview_picture.cget('image'))
        self.assertTrue(window.held_picture.cget('image'))
        self.assertEqual(window.held_preview.get(0,0),(255,0,0))
        self.assertEqual((window.held_preview.width(),window.held_preview.height()),(128,64))
        sprite,palette=window.controls[window.stat_count:window.stat_count+2]
        sprite[0].set('1');self.assertEqual(window.held_preview.get(0,0),(0,255,0))
        palette[0].set('1');self.assertEqual(window.held_preview.get(0,0),(255,0,255))
        type_field=next(i for i,f in enumerate(window.module.fields) if f.name=='Type')
        window.controls[type_field][0].set('1')
        self.assertEqual((window.held_preview.width(),window.held_preview.height()),(64,128))
        palette[0].set('36')
        self.assertFalse(window.held_picture.cget('image'));self.assertTrue(window.preview_picture.cget('image'))
        self.assertIn('unavailable',window.held_caption.get())
        palette[0].set('0');sprite[0].set('255')
        self.assertFalse(window.held_picture.cget('image'));self.assertIn('no held',window.held_caption.get())
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)

    def test_original_item_modules_keep_native_previews_and_record_icons(self):
        from item_art import item_for_record
        self.seed_held_art();before=bytes(self.rom.data);window=self.app.edit_items('modules')
        modules=[m for m in category_modules('Item Editor',self.rom) if m.name!='FE4 Expanded Item Editor' and item_for_record(m,0) is not None]
        self.assertEqual(len(modules),6)
        for module in modules:
            self.open_module(window,module.name)
            self.assertTrue(window.preview_picture.cget('image'),module.name)
            self.assertTrue(window.list.item('0','image'),module.name)
            item=item_for_record(module,0)
            if item<125:self.assertTrue(window.held_picture.cget('image'),module.name)
            else:self.assertIn('no held',window.held_caption.get())
        self.open_module(window,'FE4 Item Sprite Editor by Lorena')
        window.controls[0][0].set('1');window.controls[1][0].set('1')
        self.assertEqual(window.held_preview.get(0,0),(255,0,255))
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)

    def test_equipment_field_icons_and_player_slot_preview_follow_unsaved_assignments(self):
        self.seed_held_art();before=bytes(self.rom.data);window=self.app.edit_items('modules')
        self.open_module(window,'FE4 Broken Weapon Editor')
        self.assertEqual(len(window.equipment_icons),40)
        for label,field in window.equipment_icons.values():self.assertTrue(label.cget('image'),field.name)
        window.controls[0][0].set('255')
        self.assertFalse(window.equipment_icons[0][0].cget('image'))
        self.assertEqual(window.equipment_icons[0][0].cget('text'),'—')
        window.controls[0][0].set('nonsense')
        self.assertEqual(window.equipment_icons[0][0].cget('text'),'?')
        window.controls[0][0].set(window.initial[0])
        self.open_module(window,'FE4 Player Weapon Editor')
        window.controls[0][0].set('255')
        self.assertFalse(window.preview_picture.cget('image'));self.assertFalse(window.held_picture.cget('image'))
        self.assertEqual(window.preview_caption.get(),'Nothing')
        window.controls[0][0].set('125')
        self.assertTrue(window.preview_picture.cget('image'));self.assertFalse(window.held_picture.cget('image'))
        window.controls[0][0].set('1')
        self.assertTrue(window.held_picture.cget('image'))
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)

    def test_expanded_previews_follow_private_tables_and_refresh_after_save_undo_redo(self):
        self.seed_held_art();model=ItemExpansion(self.rom);model.add_item(0,254);model.add_slot(254,254)
        self.rom.save_original('Expanded preview fixture');before=bytes(self.rom.data)
        window=self.app.edit_items('modules');self.open_module(window,'FE4 Item Sprite Editor by Lorena',254)
        window.controls[1][0].set('1');self.assertEqual(window.held_preview.get(0,0),(0,0,255))
        self.assertEqual(bytes(self.rom.data),before)
        self.assertTrue(window.save());self.assertEqual(window.held_preview.get(0,0),(0,0,255))
        window.history(False);self.assertEqual(window.held_preview.get(0,0),(255,0,0))
        self.assertEqual(window.current,254)
        window.history(True);self.assertEqual(window.held_preview.get(0,0),(0,0,255))
        self.assertEqual(window.current,254)
        self.open_module(window,'FE4 Player Weapon Editor',253)
        self.assertTrue(window.preview_picture.cget('image'));self.assertEqual(window.held_preview.get(0,0),(0,0,255))
        self.assertIn('Item FE',window.preview_caption.get())
        window.controls[0][0].set('0');self.assertEqual(window.held_preview.get(0,0),(255,0,0))

    def test_all_twenty_original_modules_are_visible_in_the_same_modeless_window(self):
        window=self.app.edit_items();before=bytes(self.rom.data)
        window.view.current(2);window.change_view()
        expected={load_module(path).name for path in (MODULES/'Item Editors').glob('*.nmm')}
        self.assertEqual(len(expected),20)
        self.assertEqual(set(window.module_selector.cget('values')),expected)
        self.assertTrue(window.module_panel.winfo_manager());self.assertFalse(window.entry_actions.winfo_manager())
        for name in sorted(expected):
            module=self.open_module(window,name)
            self.assertEqual(len(window.controls),len(module.fields),name)
            self.assertEqual(window.values(),self.rom.values(module,0),name)
            self.assertFalse(window.pending());self.assertIsNone(self.app.grab_current())
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        window.view.current(0);window.change_view()
        self.assertTrue(window.entry_actions.winfo_manager());self.assertFalse(window.module_panel.winfo_manager())

    def test_every_original_module_writes_only_the_selected_field_and_reopens(self):
        window=self.app.edit_items('modules')
        for name in window.module_selector.cget('values'):
            module=self.open_module(window,name)
            before=self.path.read_bytes();field=module.fields[0]
            value=0 if window.values()[0] else 1
            window.controls[0][0].set(str(value))
            self.assertTrue(window.save(),name)
            at=self.rom.address(module,0)+field.offset
            expected=bytearray(before);expected[at:at+field.size]=value.to_bytes(field.size,'little',signed=field.signed)
            self.assertEqual(self.path.read_bytes(),bytes(expected),name)
            self.assertEqual(self.rom.last_backup.read_bytes(),before,name)
            self.assertEqual(self.rom.values(module,0)[0],value,name)
            self.assertEqual(window.values()[0],value,name)
            if name=='FE4 Minimum Damage Editor by DefaultFormat':
                after=self.path.read_bytes();window.history(False);self.assertEqual(self.path.read_bytes(),before)
                window.history(True);self.assertEqual(self.path.read_bytes(),after)

    def test_module_and_view_switches_preserve_unsaved_fields_when_cancelled(self):
        window=self.app.edit_items('modules')
        name=window.module.name;window.controls[0][0].set('1')
        target=next(m.name for m in category_modules('Item Editor') if m.name!=name)
        with patch('item_window.ask_unsaved',return_value=None):
            window.module_selector.set(target);window.change_module()
            self.assertEqual(window.module_selector.get(),name);self.assertEqual(window.module.name,name)
            self.assertEqual(window.controls[0][0].get(),'1')
            window.view.current(0);window.change_view();self.assertEqual(window.kind,'modules')
        with patch('item_window.ask_unsaved',return_value=True):
            window.module_selector.set(target);window.change_module()
        self.assertEqual(window.module.name,target)
        module=next(m for m in category_modules('Item Editor',self.rom) if m.name==name)
        self.assertEqual(self.rom.values(module,0)[0],1)

    def test_advanced_module_writes_follow_expanded_slot_and_sprite_tables(self):
        model=ItemExpansion(self.rom);model.add_item(0x28,254);model.add_slot(254,254);self.rom.save_original('Expanded fixture')
        window=self.app.edit_items('modules')
        original_sprites=read(self.rom,0x198725,250)
        self.open_module(window,'FE4 Item Sprite Editor by Lorena',254)
        self.assertEqual(self.rom.address(window.module,254),table(self.rom,'held')+254*2)
        window.controls[1][0].set('3');self.assertTrue(window.save())
        self.assertEqual(read(self.rom,table(self.rom,'held')+254*2+1,1),b'\x03')
        self.assertEqual(read(self.rom,0x198725,250),original_sprites)
        original_slots=read(self.rom,0x3F489,142)
        self.open_module(window,'FE4 Player Weapon Editor',253)
        self.assertNotIn(140,window.visible);self.assertIn(253,window.visible)
        window.controls[0][0].set('0');self.assertTrue(window.save())
        self.assertEqual(ItemExpansion(self.rom).assignments[254],0)
        self.assertEqual(read(self.rom,0x3F489,142),original_slots)

    def test_external_undo_refreshes_native_module_addresses_before_record_selection(self):
        model=ItemExpansion(self.rom);model.add_slot(0,254);self.rom.save_original('Enable expansion')
        window=self.app.edit_items('modules')
        self.open_module(window,'FE4 Player Weapon Editor')
        self.assertEqual(self.rom.address(window.module,0),table(self.rom,'players'))
        self.rom.undo()
        window.list.selection_set('1');window.select()
        self.assertEqual(window.current,1)
        self.assertEqual(self.rom.address(window.module,1),0x3F48A)
        window.controls[0][0].set('1');self.assertTrue(window.save())
        self.assertEqual(read(self.rom,0x3F48A,1),b'\x01')


if __name__=='__main__':unittest.main()
