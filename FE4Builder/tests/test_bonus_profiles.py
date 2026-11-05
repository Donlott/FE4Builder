"""Independent custom bonuses, safe storage ownership, assignments and editor saves."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rom import Rom
from item_bonuses import BonusEditor,weapon_bonuses,CODE_EFFECTS
from item_expansion import ItemExpansion,record,item_pointer,put,read
from bonus_profiles import BonusProfiles,ARENA,SIZE,HOOK,READER,NATIVE,VALUES,FLAGS,FIRST,LIMIT,program,require_profile
from bonus_profile_fixture import fixture


class BonusProfileTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=fixture(self.root);self.rom=Rom(self.path)
        self.preference=patch('ui_common.DATA_DIR',self.root);self.preference.start()

    def tearDown(self):self.preference.stop();self.folder.cleanup()

    def test_opening_is_read_only_and_first_add_preserves_all_original_bonus_data(self):
        before=bytes(self.rom.data);model=BonusProfiles(self.rom)
        self.assertFalse(model.installed);self.assertEqual(model.profiles,{})
        self.assertEqual(list(weapon_bonuses(self.rom)),list(range(16)))
        self.assertEqual(bytes(self.rom.data),before)
        self.assertEqual(model.add([1,2,3,4,5,6]),16)
        self.assertTrue(model.installed);self.assertEqual(model.profiles[16],(1,2,3,4,5,6))
        expected=bytearray(before)
        for at,size in ((ARENA,SIZE),(HOOK,5),(0xFFDC,4),(0x40FFDC,4)):
            expected[self.rom.header+at:self.rom.header+at+size]=read(self.rom,at,size)
        self.assertEqual(self.rom.data,expected)
        for value in range(1,14):
            old=Rom(self.path);self.assertEqual(BonusEditor(self.rom,'weapon',value).values,BonusEditor(old,'weapon',value).values)
        self.assertIn('+1 Strength',weapon_bonuses(self.rom)[16])
        self.assertEqual(read(self.rom,HOOK,5),program()[1]);self.assertEqual(read(self.rom,0xFFD8,1),before[0xFFD8:0xFFD9])

    def test_clone_edit_and_native_profile_changes_stay_independent(self):
        model=BonusProfiles(self.rom);model.add(source=1)
        self.assertEqual(BonusEditor(self.rom,'weapon',16).values,[0,0,10,10,0,20])
        BonusEditor(self.rom,'weapon',16).write([0,0,3,3,0,5])
        self.assertEqual(BonusEditor(self.rom,'weapon',1).values,[0,0,10,10,0,20])
        BonusEditor(self.rom,'weapon',1).write([1]*6)
        self.assertEqual(BonusEditor(self.rom,'weapon',16).values,[0,0,3,3,0,5])
        model=BonusProfiles(self.rom);self.assertEqual(model.add(source=16,profile=255),255)
        self.assertEqual(model.profiles[255],(0,0,3,3,0,5))
        self.assertEqual(model.add(source=14,profile=17),17)
        self.assertEqual(model.profiles[17],(0,0,0,0,5,0))

    def test_sparse_ids_reuse_and_final_removal_restore_native_reader_and_storage(self):
        original=read(self.rom,READER,len(NATIVE));model=BonusProfiles(self.rom)
        model.add(profile=255);model.add(profile=16);model.add(profile=17)
        model.remove(16);self.assertEqual(set(model.profiles),{17,255})
        self.assertNotIn(16,weapon_bonuses(self.rom));self.assertEqual(model.add(),16)
        model.remove(16);model.remove(17);self.assertTrue(model.installed)
        model.remove(255);self.assertFalse(model.installed)
        self.assertEqual(read(self.rom,ARENA,SIZE),bytes(SIZE));self.assertEqual(read(self.rom,READER,len(NATIVE)),original)

    def test_all_240_custom_ids_fit_and_a_241st_addition_is_atomic(self):
        model=BonusProfiles(self.rom)
        for i in range(FIRST,LIMIT):self.assertEqual(model.add([i,0,1,2,3,255]),i)
        self.assertEqual(len(model.profiles),240);before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.add()
        self.assertEqual(bytes(self.rom.data),before)
        for i in range(FIRST,LIMIT):self.assertEqual(BonusEditor(self.rom,'weapon',i).values,[i,0,1,2,3,255])
        self.assertEqual(len(weapon_bonuses(self.rom)),256)

    def test_occupied_storage_custom_reader_and_invalid_inputs_never_change_data(self):
        before=bytes(self.rom.data)
        for kwargs in ({'profile':15},{'profile':256},{'profile':True},{'values':[1]*5},{'values':[-1]*6},{'values':[256]*6},{'values':[1.5]*6},{'source':256}):
            with self.assertRaises(ValueError):BonusProfiles(self.rom).add(**kwargs)
            self.assertEqual(bytes(self.rom.data),before)
        put(self.rom,ARENA+100,b'\x12');before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'occupied'):BonusProfiles(self.rom).add()
        self.assertEqual(bytes(self.rom.data),before)
        put(self.rom,ARENA+100,b'\0');put(self.rom,HOOK,b'\xEA');before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'custom code'):BonusProfiles(self.rom).add()
        self.assertEqual(bytes(self.rom.data),before)

    def test_stale_and_corrupt_metadata_code_flags_values_and_hooks_are_rejected(self):
        model=BonusProfiles(self.rom);model.add();stale=BonusProfiles(self.rom)
        model.add(profile=17);before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'changed'):stale.write(16,[1]*6)
        self.assertEqual(bytes(self.rom.data),before)
        for address in (ARENA,ARENA+17,ARENA+32,ARENA+0x40,FLAGS+16,VALUES,HOOK):
            self.rom.data[:]=before;self.rom.data[self.rom.header+address]^=1
            broken=bytes(self.rom.data)
            with self.assertRaises(ValueError):BonusProfiles(self.rom)
            self.assertEqual(bytes(self.rom.data),broken)

    def test_assignments_and_reference_checks_include_original_shared_and_added_items(self):
        model=BonusProfiles(self.rom);model.add(profile=255)
        art=__import__('item_art').ItemArt(self.rom);module,index=art.record(0)
        values=self.rom.values(module,index);field=next(i for i,f in enumerate(module.fields) if f.name=='Stat Bonus')
        values[field]=255;self.rom.write(module,index,values)
        self.assertTrue(BonusEditor(self.rom,'weapon',255).users()[0].startswith('00 '))
        expansion=ItemExpansion(self.rom);expansion.add_item(0,item=254)
        users=BonusEditor(self.rom,'weapon',255).users();self.assertEqual({u.split()[0] for u in users},{'00','FE'})
        model=BonusProfiles(self.rom);before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'Reassign'):model.remove(255)
        self.assertEqual(bytes(self.rom.data),before)
        raw=bytearray(record(self.rom,0));raw[5]=0;ItemExpansion(self.rom).write_record(0,raw)
        with self.assertRaisesRegex(ValueError,'Reassign'):BonusProfiles(self.rom).remove(255)
        expansion=ItemExpansion(self.rom);raw=bytearray(record(self.rom,254));raw[5]=0;expansion.write_record(254,raw)
        BonusProfiles(self.rom).remove(255)
        values[field]=255;before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'disabled'):self.rom.write(module,index,values)
        self.assertEqual(bytes(self.rom.data),before)
        raw[5]=255
        with self.assertRaisesRegex(ValueError,'disabled'):ItemExpansion(self.rom).write_record(254,raw)
        self.assertEqual(bytes(self.rom.data),before)

    def test_headered_roundtrip_backup_undo_redo_and_failed_save(self):
        for header in (False,True):
            folder=self.root/str(header);folder.mkdir();path=fixture(folder,header);rom=Rom(path);before=path.read_bytes()
            BonusProfiles(rom).add([1,2,3,4,5,6],profile=255)
            rom.save_original('Add custom weapon bonus')
            self.assertEqual(rom.last_backup.read_bytes(),before)
            self.assertEqual(BonusProfiles(Rom(path)).profiles[255],(1,2,3,4,5,6))
            rom.undo();self.assertEqual(path.read_bytes(),before)
            rom.redo();self.assertEqual(BonusProfiles(rom).profiles[255],(1,2,3,4,5,6))
            self.assertEqual(len(path.read_bytes()),len(before))


class BonusProfileWindowTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=fixture(self.root);self.rom=Rom(self.path)
        self.preference=patch('ui_common.DATA_DIR',self.root);self.preference.start()
        from FE4Builder import App
        self.app=App();self.app.withdraw();self.app.rom=self.rom

    def tearDown(self):self.app.destroy();self.preference.stop();self.folder.cleanup()

    def test_add_link_assign_edit_and_remove_used_guard_in_combined_item_editor(self):
        item=self.app.edit_items('items',0)
        field=next(i for i,f in enumerate(item.module.fields) if f.name=='Stat Bonus')
        window=item.edit_bonus(field)
        self.assertEqual(window.key,('weapon',1));before=self.path.read_bytes()
        self.assertTrue(window.add_profile([1,2,3,4,5,6],profile=255))
        self.assertEqual(window.key,('weapon',255));self.assertEqual(self.rom.last_backup.read_bytes(),before)
        self.assertIn(255,item.controls[field][1].values())
        item.controls[field][0].set('255');self.assertTrue(item.save())
        window.load(('weapon',255));self.assertTrue(window.users.get(0).startswith('00 '))
        with patch('bonus_window.messagebox.showinfo') as info:
            self.assertFalse(window.remove());self.assertTrue(info.called)
        window.variables[0].set('4');self.assertTrue(window.save())
        self.assertEqual(BonusEditor(self.rom,'weapon',255).values,[4,2,3,4,5,6])
        self.assertIn('+4 Strength',next(k for k,v in item.controls[field][1].items() if v==255))
        item.controls[field][0].set('0');self.assertTrue(item.save())
        with patch('bonus_window.messagebox.askyesno',return_value=True):self.assertTrue(window.remove())
        self.assertNotIn(255,item.controls[field][1].values());self.assertFalse(BonusProfiles(self.rom).installed)

    def test_create_and_edit_failure_roll_back_without_losing_draft(self):
        window=self.app.edit_stat_bonuses();before=bytes(self.rom.data)
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')),patch('bonus_window.messagebox.showerror'):
            self.assertFalse(window.add_profile([1]*6))
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(window.add_profile([1]*6));window.variables[0].set('3');before=bytes(self.rom.data)
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')),patch('bonus_window.messagebox.showerror'):
            self.assertFalse(window.save())
        self.assertEqual(bytes(self.rom.data),before);self.assertTrue(window.pending());self.assertEqual(window.variables[0].get(),'3')

    def test_cancel_switch_and_undo_redo_rebuild_the_profile_choices(self):
        window=self.app.edit_stat_bonuses();self.assertTrue(window.add_profile([1]*6,profile=255))
        window.variables[0].set('3')
        with patch('bonus_window.ask_unsaved',return_value=None):
            window.selector.current(0);window.change()
        self.assertEqual(window.key,('weapon',255));self.assertEqual(window.variables[0].get(),'3')
        window.variables[0].set(window.loaded[0]);window.history(False)
        self.assertNotIn(('weapon',255),window.keys)
        window.history(True);self.assertIn(('weapon',255),window.keys)
        window.load(('weapon',255));self.assertEqual(window.variables[0].get(),'1')


if __name__=='__main__':unittest.main()
