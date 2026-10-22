import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rom import ROOT,Rom
from reinforcements import catalogue,Reinforcement

class ReinforcementTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_every_supported_script_roundtrips_without_other_changes(self):
        before=bytes(self.rom.data)
        self.assertEqual(len(catalogue()['entries']),58)
        for i in range(58):
            model=Reinforcement(self.rom,i)
            values=[u['values'][:] for u in model.units];turns=[t['turn'] for t in model.triggers]
            model.write(values,turns);self.assertEqual(bytes(self.rom.data),before)
            changed=[[(v+1)%64 for v in row[:-1]]+[(row[-1]+1)%8] for row in values]
            model.write(changed,[4 for t in turns])
            expected=bytearray(before)
            for u,row in zip(model.units,changed):
                at=model.start+u['offset']+4;expected[at:at+len(row)]=bytes(row[:-1]+[row[-1]|u['speed_flags']])
            for t in model.triggers:expected[t['address']+1]=4
            self.assertEqual(self.rom.data,expected)
            edited=Reinforcement(self.rom,i);self.assertEqual([u['values'] for u in edited.units],changed)
            edited.write(values,turns);self.assertEqual(bytes(self.rom.data),before)

    def test_known_quan_spawn_and_turn(self):
        m=Reinforcement(self.rom,0)
        self.assertEqual([u['values'] for u in m.units],[[63,13,59,14,4],[63,13,60,14,4],[63,13,61,14,4]])
        self.assertEqual([t['turn'] for t in m.triggers],[3])

    def test_invalid_values_are_atomic(self):
        m=Reinforcement(self.rom,0);before=bytes(self.rom.data)
        for bad in (64,-1):
            values=[u['values'][:] for u in m.units];values[0][0]=12;values[-1][1]=bad
            with self.assertRaises(ValueError):m.write(values,[3])
            self.assertEqual(bytes(self.rom.data),before)
        with self.assertRaises(ValueError):m.write([u['values'] for u in m.units],[0])
        self.assertEqual(bytes(self.rom.data),before)

    def test_stale_and_custom_code_are_rejected(self):
        m=Reinforcement(self.rom,0);other=Reinforcement(self.rom,0)
        values=[u['values'][:] for u in m.units];values[0][0]=62;m.write(values,[2])
        with self.assertRaises(ValueError):other.write(values,[3])
        self.rom.data[m.start]^=1
        with self.assertRaises(ValueError):Reinforcement(self.rom,0)

    def test_relocated_and_headered_roms(self):
        headered=SimpleNamespace(data=bytearray(512)+self.rom.data,header=512)
        m=Reinforcement(headered,0);values=[u['values'][:] for u in m.units];values[0][0]=62
        m.write(values,[2]);self.assertEqual(headered.data[512+m.start+m.units[0]['offset']+4],62)
        at=0xfe8bf+m.entry['id']*3;self.rom.data[at:at+3]=(0x2f8020).to_bytes(3,'little')
        with self.assertRaises(ValueError):Reinforcement(self.rom,0)

    def test_ui_save_backup_undo_and_failure_rollback(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            target=Path(folder)/'test.sfc';target.write_bytes(self.rom.data);baseline=target.read_bytes()
            app=App();app.withdraw()
            try:
                app.rom=Rom(target);w=app.edit_reinforcements();app.update()
                w.variables[0].set('62');w.turn_vars[0].set('2')
                w.units.selection_clear(0,'end');w.units.selection_set(1);w.select_unit()
                self.assertEqual(w.drafts[0][0],'62');self.assertTrue(w.pending())
                self.assertTrue(w.save());self.assertNotEqual(target.read_bytes(),baseline)
                self.assertTrue(app.rom.last_backup.exists())
                self.assertEqual(Reinforcement(app.rom,0).triggers[0]['turn'],2)
                w.history(False);self.assertEqual(target.read_bytes(),baseline)
                w.variables[0].set('60');before=bytes(app.rom.data)
                with patch.object(app.rom,'save_original',side_effect=OSError('test failure')),patch('reinforcement_window.messagebox.showerror'):
                    self.assertFalse(w.save())
                self.assertEqual(bytes(app.rom.data),before);self.assertEqual(target.read_bytes(),baseline)
                w.destroy()
            finally:app.destroy()
