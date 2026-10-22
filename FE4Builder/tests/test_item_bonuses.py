import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import Rom,ROOT,category_modules
from item_bonuses import BonusEditor,weapon_bonuses,ring_bonuses,CODE_EFFECTS


class ItemBonusTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_profile_changes_only_six_boost_bytes_and_updates_dropdowns(self):
        before=bytes(self.rom.data)
        model=BonusEditor(self.rom,'weapon',1)
        self.assertEqual(model.values,[0,0,10,10,0,20])
        self.assertTrue(model.users())
        model.write([3,2,1,4,5,6])
        changed={i for i,(a,b) in enumerate(zip(before,self.rom.data)) if a!=b}
        self.assertEqual(changed,{at[0] for at in model.locations})
        self.assertEqual(BonusEditor(self.rom,'weapon',1).values,[3,2,1,4,5,6])
        self.assertIn('+3 Strength',weapon_bonuses(self.rom)[1])
        self.assertIn('+6 Resistance',weapon_bonuses(self.rom)[1])
        for value in range(2,14):
            peer=BonusEditor(self.rom,'weapon',value)
            self.assertEqual([before[at[0]] for at in peer.locations],peer.values)

    def test_all_native_amounts_and_both_movement_paths(self):
        for key in CODE_EFFECTS:
            model=BonusEditor(self.rom,*key)
            before=bytes(self.rom.data)
            amount=2 if key==('ring',6) else 9
            model.write([amount])
            expected=bytearray(before)
            for at in model.locations[0]:expected[at:at+2]=amount.to_bytes(2,'little')
            self.assertEqual(self.rom.data,expected)
            self.assertEqual(BonusEditor(self.rom,*key).values,[amount])
            labels=ring_bonuses(self.rom) if key[0]=='ring' else weapon_bonuses(self.rom)
            self.assertIn(f'+{amount} ',labels[key[1]])

    def test_invalid_stale_and_conflicting_code_are_atomic(self):
        model=BonusEditor(self.rom,'weapon',1);before=bytes(self.rom.data)
        for values in ([256]*6,[-1]*6,[1.5]*6,[1]):
            with self.assertRaises(ValueError):model.write(values)
            self.assertEqual(bytes(self.rom.data),before)
        model.write([1]*6);before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write([2]*6)
        self.assertEqual(bytes(self.rom.data),before)
        with self.assertRaises(ValueError):BonusEditor(self.rom,'ring',6).write([4])
        self.rom.data[0x49d7b]=2
        with self.assertRaises(ValueError):BonusEditor(self.rom,'ring',6)
        self.rom.data[0x49ca3]=0
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):BonusEditor(self.rom,'weapon',14)
        self.assertEqual(bytes(self.rom.data),before)

    def test_headered_roundtrip_backup_undo_redo(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'bonuses.smc';path.write_bytes(bytes(512)+self.rom.data)
            rom=Rom(path);before=path.read_bytes()
            model=BonusEditor(rom,'weapon',5)
            rom.save_original('Bonus profile',model.write([1,2,3,4,5,6]))
            self.assertEqual(rom.last_backup.read_bytes(),before)
            self.assertEqual(BonusEditor(Rom(path),'weapon',5).values,[1,2,3,4,5,6])
            rom.undo();self.assertEqual(path.read_bytes(),before)
            rom.redo();self.assertEqual(BonusEditor(rom,'weapon',5).values,[1,2,3,4,5,6])
            self.assertEqual(len(path.read_bytes()),len(before))

    def test_bonus_window_link_selection_save_and_failure(self):
        from FE4Builder import App
        from bonus_window import BonusWindow
        app=App();app.withdraw();app.update_idletasks();app.rom=self.rom
        try:
            app.show_editor('Item Editor')
            index=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Stat Bonus')
            var,options=app.editors[index]
            var.set(next(label for label,value in options.items() if value==14))
            with patch.object(app,'settle',return_value=True):window=app.edit_selected_bonus(index)
            self.assertEqual(window.key,('weapon',14))
            window.variables[0].set('9');before=bytes(self.rom.data)
            with patch.object(self.rom,'save_original',side_effect=OSError('Cannot write')),patch('bonus_window.messagebox.showerror'):
                self.assertFalse(window.save())
            self.assertEqual(bytes(self.rom.data),before)
            with patch('bonus_window.ask_unsaved',return_value=None):
                self.assertFalse(window.settle())
            window.destroy()
            window=BonusWindow(app,'ring',6)
            self.assertEqual(window.model.fields,['Movement'])
            window.destroy()
        finally:app.destroy()
