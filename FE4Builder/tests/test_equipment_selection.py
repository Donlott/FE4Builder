"""Select item types absent from player slots, preserving native slot identity."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rom import Rom, character_modules, category_modules
from item_expansion import ItemExpansion, enabled, installed, record
from item_expansion_fixture import fixture
from item_browser import ItemBrowser


class EquipmentSelectionTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=fixture(self.root);self.rom=Rom(self.path)
        for module in (character_modules()[0],category_modules('Enemy Editor')[0],category_modules('Holy Character Editor')[0]):
            values=self.rom.values(module,0)
            for i,field in enumerate(module.fields):
                if field.reference in ('FE4 Player Equipment.txt','FE4 Weapon List.txt'):values[i]=255
            self.rom.write(module,0,values)
        self.path.write_bytes(self.rom.data);self.rom=Rom(self.path)
        self.preference=patch('ui_common.DATA_DIR',self.root);self.preference.start()
        from FE4Builder import App
        self.app=App();self.app.withdraw();self.app.rom=self.rom

    def tearDown(self):self.app.destroy();self.preference.stop();self.folder.cleanup()

    def add_item(self):
        ItemExpansion(self.rom).add_item(0,item=254);self.rom.save_original('Added type, no player slot')

    def open(self,mode='Character Editor'):
        self.app.show_editor(mode)
        return [i for i,f in enumerate(self.app.modules[0].fields) if f.reference=='FE4 Player Equipment.txt']

    def select_type(self,index,item):
        var,_=self.app.editors[index]
        label=next(label for label,value in self.app.equipment_type_choices[index].items() if value==item)
        var.set(label);self.app.field_controls[index]['widget'].event_generate('<<ComboboxSelected>>')
        return next(w for w in self.app.winfo_children() if isinstance(w,ItemBrowser))

    def new_slot(self,index,item):
        browser=self.select_type(index,item)
        label,(slot,_)=next((k,v) for k,v in browser.slot_options.items() if v[1])
        browser.slot_choice.set(label);browser.slot_details();browser.use_button.invoke()
        self.assertFalse(browser.winfo_exists());return slot

    def test_all_three_dropdowns_offer_all_types_and_new_slots_save_with_unit_undo_redo(self):
        self.add_item();indices=self.open();before=self.path.read_bytes()
        window=self.app.edit_items()
        slots=[]
        for index in indices:
            self.assertEqual(set(self.app.equipment_type_choices[index].values()),set(enabled(self.rom,'items')))
            self.assertNotIn(254,self.app.editors[index][1].values())
            slots.append(self.new_slot(index,254))
            self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(len(set(slots)),3)
        self.app.update_validation()
        self.assertFalse(any(i.severity=='Error' for i in self.app.current_issues))
        for index,slot in zip(indices,slots):
            self.assertEqual(self.app.read_draft()[index],slot)
            self.assertTrue(self.app.equipment_icons[index].cget('image'))
        self.assertTrue(self.app.write_original());after=self.path.read_bytes()
        reopened=Rom(self.path);assignments=ItemExpansion(reopened).assignments
        self.assertTrue(all(assignments[slot]==254 for slot in slots))
        self.assertEqual([reopened.values(self.app.modules[0],0)[i] for i in indices],slots)
        self.assertEqual(self.rom.last_backup.read_bytes(),before)
        self.assertFalse(self.app.pending());self.assertFalse(self.app.equipment_slots.assignments)
        window.view.current(1);window.change_view();self.assertTrue(all(s in window.visible for s in slots))
        self.app.history_step(False);self.assertEqual(self.path.read_bytes(),before)
        self.app.history_step(True);self.assertEqual(self.path.read_bytes(),after)

    def test_cancel_restores_previous_draft_and_browse_exposes_unassigned_types(self):
        self.add_item();index=self.open()[0]
        var,options=self.app.editors[index]
        var.set(next(k for k,v in options.items() if v==1));previous=var.get();before=bytes(self.rom.data)
        browser=self.select_type(index,254)
        self.assertTrue(browser.type_view);self.assertIn(254,[e[0] for e in browser.entries])
        self.assertEqual(var.get(),previous);browser.destroy()
        self.assertEqual(self.app.read_draft()[index],1);self.assertFalse(self.app.equipment_slots.assignments)
        field=self.app.modules[0].fields[index];browser=self.app.browse_equipment(field,var,options)
        browser.view.current(1);browser.load_entries()
        self.assertIn(254,[e[0] for e in browser.entries]);browser.destroy()
        self.assertEqual(bytes(self.rom.data),before)

    def test_existing_slot_choice_keeps_shared_identity_without_creating_another_slot(self):
        index=self.open()[0];before=self.path.read_bytes();slots=enabled(self.rom,'slots')
        browser=self.select_type(index,0)
        self.assertFalse(next(iter(browser.slot_options.values()))[1])
        browser.use_button.invoke()
        self.assertEqual(self.app.read_draft()[index],1);self.assertFalse(self.app.equipment_slots.assignments)
        self.assertTrue(self.app.write_original());self.assertFalse(installed(self.rom))
        self.assertEqual(enabled(self.rom,'slots'),slots)
        self.assertEqual(ItemExpansion(self.rom).assignments[1],0)
        self.app.history_step(False);self.assertEqual(self.path.read_bytes(),before)

    def test_failed_save_keeps_plan_and_save_copy_preserves_original_draft(self):
        self.add_item();index=self.open()[0];before=self.path.read_bytes();slot=self.new_slot(index,254)
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')),patch('FE4Builder.messagebox.showerror'):
            self.assertFalse(self.app.write_original())
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(self.app.pending());self.assertEqual(self.app.equipment_slots.assignments,{slot:254})
        target=self.root/'copy.smc'
        with patch('FE4Builder.filedialog.asksaveasfilename',return_value=str(target)):self.app.save()
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        copy=Rom(target);self.assertEqual(ItemExpansion(copy).assignments[slot],254)
        self.assertEqual(copy.values(self.app.modules[0],0)[index],slot);self.assertTrue(self.app.pending())
        self.assertTrue(self.app.write_original());self.assertFalse(self.app.pending())

    def test_first_extra_slot_warns_about_new_game_but_cancel_and_revert_do_not_install(self):
        index=self.open()[0];before=self.path.read_bytes()
        browser=self.select_type(index,1)
        self.assertIn('NEW GAME',browser.slot_note.get());self.assertFalse(installed(self.rom))
        browser.use_button.invoke();self.assertEqual(self.path.read_bytes(),before)
        self.assertFalse(installed(self.rom));self.assertTrue(installed(self.app.equipment_rom()))
        var,options=self.app.editors[index];var.set(next(k for k,v in options.items() if v==255))
        self.app.update_validation();self.assertFalse(self.app.equipment_slots.assignments)
        self.assertFalse(self.app.pending());self.assertEqual(bytes(self.rom.data),before)

    def test_enemy_direct_equipment_and_drops_keep_distinct_id_semantics(self):
        self.add_item();drop=self.open('Enemy Editor')[0];module=self.app.modules[0]
        direct=[i for i,f in enumerate(module.fields) if f.reference=='FE4 Weapon List.txt']
        for index in direct:
            var,options=self.app.editors[index];var.set(next(k for k,v in options.items() if v==254))
        slot=self.new_slot(drop,254);self.assertNotEqual(slot,254)
        self.assertTrue(self.app.write_original());values=Rom(self.path).values(module,0)
        self.assertTrue(all(values[i]==254 for i in direct));self.assertEqual(values[drop],slot)
        self.assertEqual(ItemExpansion(self.rom).assignments[slot],254)

    def test_stale_plan_and_unsupported_first_install_cannot_change_rom(self):
        index=self.open()[0];before=self.path.read_bytes()
        self.rom.data[0x7E31D]^=1
        browser=self.select_type(index,1);changed=bytes(self.rom.data)
        with patch('item_browser.messagebox.showerror') as error:browser.use_button.invoke();self.assertTrue(error.called)
        self.assertTrue(browser.winfo_exists());browser.destroy()
        self.assertFalse(self.app.equipment_slots.assignments);self.assertEqual(bytes(self.rom.data),changed)
        self.rom.data[:]=before;self.add_item();self.app.render();index=next(i for i,f in enumerate(self.app.modules[0].fields) if f.reference=='FE4 Player Equipment.txt')
        self.new_slot(index,254);self.rom.data[0x1000]^=1;changed=bytes(self.rom.data)
        with patch('FE4Builder.messagebox.showerror') as error:self.assertFalse(self.app.write_original());self.assertTrue(error.called)
        self.assertEqual(bytes(self.rom.data),changed);self.assertTrue(self.app.pending())

    def test_full_player_slot_capacity_keeps_unassigned_types_visible_and_disables_creation(self):
        self.add_item();model=ItemExpansion(self.rom)
        for slot in range(141,255):model.add_slot(0,slot=slot)
        self.rom.save_original('Full slot fixture');index=self.open()[0];before=bytes(self.rom.data)
        browser=self.select_type(index,254)
        self.assertIn(254,[e[0] for e in browser.entries]);self.assertFalse(browser.slot_options)
        self.assertTrue(browser.use_button.instate(['disabled']));self.assertIn('all 254',browser.slot_note.get())
        browser.use_button.invoke();self.assertEqual(bytes(self.rom.data),before)


if __name__=='__main__':unittest.main()
