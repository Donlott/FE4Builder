"""Patch transactions, independent type assignments and the combined item UI."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from rom import Rom, category_modules
from item_expansion import ItemExpansion, record, read, put
from patch_window import save_patch
from weapon_skill_fixture import fixture
import weapon_skills as ws


class WeaponSkillTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=fixture(self.root);self.rom=Rom(self.path);self.before=bytes(self.rom.data)
        self.app=SimpleNamespace(rom=self.rom,refresh_after_history=lambda:None)

    def tearDown(self):self.folder.cleanup()

    def test_read_only_open_install_and_exact_removal_preserve_native_flags(self):
        self.assertFalse(ws.WeaponSkills(self.rom).installed)
        self.assertEqual(bytes(self.rom.data),self.before)
        native=read(self.rom,0x7A280,60)
        ws.install(self.rom);model=ws.WeaponSkills(self.rom)
        self.assertTrue(model.installed);self.assertEqual(model.flags,bytes(256))
        self.assertEqual(read(self.rom,0x7A280,60),native)
        expected=bytearray(self.before)
        areas=[(ws.ARENA,ws.SIZE),(0xFFDC,4),(0x40FFDC,4)]+[(at,len(new)) for at,(_,new) in ws.program()[1].items()]
        for at,size in areas:expected[at:at+size]=read(self.rom,at,size)
        self.assertEqual(bytes(self.rom.data),bytes(expected));self.assertEqual(len(self.rom.data),len(self.before))
        ws.uninstall(self.rom);self.assertEqual(bytes(self.rom.data),self.before)
        self.assertEqual(self.path.read_bytes(),self.before)

    def test_all_32_combinations_and_invalid_assignments(self):
        ws.install(self.rom);model=ws.WeaponSkills(self.rom)
        for value in range(32):model.assign(0,value);self.assertEqual(model.get(0),value)
        before=bytes(self.rom.data)
        for item,value in ((0,-1),(0,32),(255,1),(254,1),(True,1),(0,True)):
            with self.assertRaises(ValueError):model.assign(item,value)
            self.assertEqual(bytes(self.rom.data),before)
        self.assertIn('Adept',model.users()[0]);self.assertIn('Sol',model.users()[0])
        with self.assertRaisesRegex(ValueError,'Clear additional'):ws.uninstall(self.rom)
        model.assign(0,0);ws.uninstall(self.rom)

    def test_headered_ff_storage_backup_undo_redo_and_removal(self):
        folder=self.root/'headered';folder.mkdir();path=fixture(folder,True,255);rom=Rom(path)
        app=SimpleNamespace(rom=rom,refresh_after_history=lambda:None);before=path.read_bytes()
        save_patch(app,patch_name='weapon_skills');after=path.read_bytes()
        self.assertEqual(rom.last_backup.read_bytes(),before);self.assertTrue(ws.installed(Rom(path)))
        rom.undo();self.assertEqual(path.read_bytes(),before)
        rom.redo();self.assertEqual(path.read_bytes(),after)
        save_patch(app,True,patch_name='weapon_skills');self.assertEqual(path.read_bytes(),before)
        self.assertEqual(len(before),len(after));self.assertEqual(before[:512],after[:512])

    def test_unknown_code_mapping_storage_and_layout_fail_before_mutation(self):
        for address in [*ws.GUARDS,ws.ARENA+200,0x7A28A]:
            self.rom.data[:]=self.before;self.rom.data[address]^=1;before=bytes(self.rom.data)
            with self.assertRaises(ValueError,msg=hex(address)):ws.install(self.rom)
            self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[:]=self.before;self.rom.data[0xFFD5]=0x21;before=bytes(self.rom.data)
        with self.assertRaises(ValueError):ws.install(self.rom)
        self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[:]=self.before[:0x400000];before=bytes(self.rom.data)
        with self.assertRaises(ValueError):ws.install(self.rom)
        self.assertEqual(bytes(self.rom.data),before)

    def test_duplicate_install_corrupt_metadata_and_stale_assignments_are_atomic(self):
        ws.install(self.rom);baseline=bytes(self.rom.data)
        with self.assertRaises(ValueError):ws.install(self.rom)
        stale=ws.WeaponSkills(self.rom);ws.WeaponSkills(self.rom).assign(0,1);before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'changed'):stale.assign(0,2)
        self.assertEqual(bytes(self.rom.data),before)
        for address in (ws.ARENA,ws.ARENA+17,ws.ARENA+32,ws.FLAGS,ws.FLAGS+255,ws.CODE,0x7A2EF,0x4E239):
            self.rom.data[:]=baseline;self.rom.data[address]^=1;broken=bytes(self.rom.data)
            with self.assertRaises(ValueError):ws.uninstall(self.rom)
            self.assertEqual(bytes(self.rom.data),broken)

    def test_copy_delete_and_independent_high_item_ids(self):
        ws.install(self.rom);ws.WeaponSkills(self.rom).assign(0,31)
        expansion=ItemExpansion(self.rom);expansion.add_item(0,item=254)
        model=ws.WeaponSkills(self.rom);self.assertEqual(model.get(254),31)
        model.assign(254,2);self.assertEqual(model.get(0),31);self.assertEqual(model.get(254),2)
        ItemExpansion(self.rom).remove('items',254)
        self.assertEqual(ws.WeaponSkills(self.rom).get(254),0)
        self.assertEqual(ws.WeaponSkills(self.rom).get(0),31)

    def test_weapon_type_changes_can_clear_or_assign_skills_in_one_transaction(self):
        ws.install(self.rom);ws.WeaponSkills(self.rom).assign(0,24)
        raw=bytearray(record(self.rom,0));raw[10]=1;before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'sword'):ItemExpansion(self.rom).write_record(0,raw)
        self.assertEqual(bytes(self.rom.data),before)
        ItemExpansion(self.rom).write_record(0,raw,skills=0)
        self.assertEqual(ws.WeaponSkills(self.rom).get(0),0)
        raw[10]=0;ItemExpansion(self.rom).write_record(0,raw,skills=31)
        self.assertEqual(ws.WeaponSkills(self.rom).get(0),31)
        raw[1]=1;before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'staff'):ItemExpansion(self.rom).write_record(0,raw)
        self.assertEqual(bytes(self.rom.data),before)
        ItemExpansion(self.rom).write_record(0,raw,skills=0)
        with self.assertRaisesRegex(ValueError,'staff'):ws.WeaponSkills(self.rom).assign(0,1)

    def test_original_module_writes_cannot_invalidate_skill_targets_or_native_mappings(self):
        ws.install(self.rom);ws.WeaponSkills(self.rom).assign(0,24)
        modules=category_modules('Item Editor',self.rom)
        weapon=next(m for m in modules if m.name=='FE4 Weapon/Staff Editor 1')
        values=self.rom.values(weapon,0);i=next(i for i,f in enumerate(weapon.fields) if f.name=='Weapon Type');values[i]=1
        before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'sword'):self.rom.write(weapon,0,values)
        self.assertEqual(bytes(self.rom.data),before)
        mapping=next(m for m in modules if m.name=='FE4 Item Skill Table Editor by Lorena')
        values=self.rom.values(mapping,0);i=next(i for i,f in enumerate(mapping.fields) if f.name=='Adept');values[i]=4
        with self.assertRaisesRegex(ValueError,'separate item table'):self.rom.write(mapping,0,values)
        self.assertEqual(bytes(self.rom.data),before)

    def test_failed_install_and_removal_disk_writes_roll_back(self):
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')):
            with self.assertRaises(OSError):save_patch(self.app,patch_name='weapon_skills')
        self.assertEqual(bytes(self.rom.data),self.before);self.assertEqual(self.path.read_bytes(),self.before)
        save_patch(self.app,patch_name='weapon_skills');before=bytes(self.rom.data)
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')):
            with self.assertRaises(OSError):save_patch(self.app,True,patch_name='weapon_skills')
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)


class WeaponSkillWindowTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=fixture(self.root);self.rom=Rom(self.path)
        self.preference=patch('ui_common.DATA_DIR',self.root);self.preference.start()
        from FE4Builder import App
        self.app=App();self.app.withdraw();self.app.rom=self.rom

    def tearDown(self):self.app.destroy();self.preference.stop();self.folder.cleanup()

    def controls(self):
        from tkinter import ttk
        window=self.app.edit_patches();tabs=next(w for w in window.winfo_children() if isinstance(w,ttk.Notebook))
        self.assertEqual(tabs.tab(2,'text'),'Additional weapon skills');panel=window.nametowidget(tabs.tabs()[2])
        def children(widget):
            for child in widget.winfo_children():yield child;yield from children(child)
        buttons={str(w['text']):w for w in children(panel) if isinstance(w,ttk.Button)}
        return buttons['Install: Additional weapon skills'],buttons['Remove patch']

    def test_patch_tab_unlocks_checkboxes_and_removal_requires_clear_assignments(self):
        item=self.app.edit_items('items',0);self.assertFalse(item.weapon_skill_vars)
        install,remove=self.controls();self.assertTrue(remove.instate(['disabled']))
        install.invoke();self.assertEqual(len(item.weapon_skill_vars),5);self.assertIsNone(self.app.grab_current())
        self.assertTrue(install.instate(['disabled']));self.assertFalse(remove.instate(['disabled']))
        item.weapon_skill_vars[1].set(True);item.weapon_skill_vars[8].set(True);self.assertTrue(item.pending())
        self.assertTrue(item.save());self.assertEqual(ws.WeaponSkills(self.rom).get(0),9)
        with patch('patch_window.messagebox.showerror') as error:remove.invoke();self.assertTrue(error.called)
        self.assertTrue(ws.installed(self.rom))
        for var in item.weapon_skill_vars.values():var.set(False)
        self.assertTrue(item.save());remove.invoke()
        self.assertFalse(ws.installed(self.rom));self.assertFalse(item.weapon_skill_vars)
        self.assertTrue(item.preview_picture.cget('image'))

    def test_cancel_switch_save_failure_and_undo_redo_preserve_extra_skill_drafts(self):
        item=self.app.edit_items('items',0);save_patch(self.app,patch_name='weapon_skills')
        item.weapon_skill_vars[16].set(True)
        with patch('item_window.ask_unsaved',return_value=None):item.view.current(1);item.change_view()
        self.assertEqual(item.kind,'items');self.assertTrue(item.weapon_skill_vars[16].get())
        before=bytes(self.rom.data)
        with patch.object(self.rom,'save_original',side_effect=OSError('disk fixture')),patch('item_window.messagebox.showerror'):
            self.assertFalse(item.save())
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(item.pending());self.assertTrue(item.weapon_skill_vars[16].get())
        self.assertTrue(item.save());item.history(False)
        self.assertEqual(ws.WeaponSkills(self.rom).get(0),0);self.assertFalse(item.weapon_skill_vars[16].get())
        item.history(True);self.assertTrue(item.weapon_skill_vars[16].get())

    def test_non_sword_and_staff_controls_disable_inapplicable_skills(self):
        item=self.app.edit_items('items',0);save_patch(self.app,patch_name='weapon_skills')
        weapon=next(i for i,f in enumerate(item.module.fields) if f.name=='Weapon Type')
        kind=next(i for i,f in enumerate(item.module.fields) if f.name=='Type')
        item.controls[weapon][0].set('1')
        self.assertTrue(item.weapon_skill_checks[8].instate(['disabled']))
        self.assertFalse(item.weapon_skill_checks[1].instate(['disabled']))
        item.weapon_skill_vars[1].set(True);item.controls[kind][0].set('1')
        self.assertFalse(item.weapon_skill_checks[1].instate(['disabled']))
        item.weapon_skill_vars[1].set(False);item.draw_preview()
        self.assertTrue(all(w.instate(['disabled']) for w in item.weapon_skill_checks.values()))
        self.assertTrue(item.save());self.assertEqual(record(self.rom,0)[1],1)


if __name__=='__main__':unittest.main()
