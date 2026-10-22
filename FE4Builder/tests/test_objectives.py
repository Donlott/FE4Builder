import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rom import ROOT,Rom
from objectives import Objective,DefeatRule,catalogue

class ObjectiveTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_all_triggers_roundtrip_exact_bytes(self):
        before=bytes(self.rom.data)
        self.assertEqual(len(catalogue()['entries']),105)
        self.assertEqual({e['chapter'] for e in catalogue()['entries'] if e['ending']},set(range(12)))
        self.assertTrue(any(e['chapter']==2 and e['ending'] and e['indirect_events'] for e in catalogue()['entries']))
        for i,e in enumerate(catalogue()['entries']):
            m=Objective(self.rom,i);m.write(m.kind,m.first,m.second)
            self.assertEqual(bytes(self.rom.data),before)
            # Use a free faction on the existing target to exercise every operand and reload.
            changed=False
            for faction in range(7):
                if faction==(m.first if m.kind==2 else m.second):continue
                first,second=(faction,m.second) if m.kind==2 else (m.first,faction)
                try:m.write(m.kind,first,second)
                except ValueError:continue
                changed=True;break
            self.assertTrue(changed,e)
            expected=bytearray(before);at=e['address']
            expected[at:at+6]=bytes([m.kind,m.flag])+first.to_bytes(2,'little')+second.to_bytes(2,'little')
            self.assertEqual(self.rom.data,expected)
            edited=Objective(self.rom,i);edited.write(m.kind,m.first,m.second)
            self.assertEqual(bytes(self.rom.data),before)

    def test_convert_seize_to_unit_defeat_and_back(self):
        before=bytes(self.rom.data);m=Objective(self.rom,0)
        self.assertEqual((m.kind,m.first,m.second),(2,0,1))
        m.write(15,2,0);edited=Objective(self.rom,0)
        self.assertEqual((edited.kind,edited.first,edited.second,edited.flag),(15,2,0,m.flag))
        edited.write(2,0,1);self.assertEqual(bytes(self.rom.data),before)

    def test_invalid_collision_stale_and_relocated_data_rejected(self):
        before=bytes(self.rom.data);m=Objective(self.rom,0)
        for args in ((1,0,1),(2,8,1),(2,0,99),(15,0,0),(15,2,9),(2,0,2),(15,6,1)):
            with self.assertRaises(ValueError):m.write(*args)
            self.assertEqual(bytes(self.rom.data),before)
        m.write(15,2,0)
        with self.assertRaises(ValueError):m.write(2,0,1)
        self.rom.data[m.entry['address']]=0
        with self.assertRaises(ValueError):Objective(self.rom,0)
        self.rom.data[:]=before;self.rom.data[0x6c739]^=1
        with self.assertRaises(ValueError):Objective(self.rom,0)

    def test_global_defeat_all_slots_header_and_stale_checks(self):
        before=bytes(self.rom.data);m=DefeatRule(self.rom);self.assertEqual(m.slot,1)
        for value in range(1,25):
            DefeatRule(self.rom).write(value)
            expected=bytearray(before);expected[m.address:m.address+2]=value.to_bytes(2,'little')
            self.assertEqual(self.rom.data,expected);self.assertEqual(DefeatRule(self.rom).slot,value)
        with self.assertRaises(ValueError):m.write(1)
        for value in (0,25,65535):
            with self.assertRaises(ValueError):DefeatRule(self.rom).write(value)
        h=SimpleNamespace(data=bytearray(512)+before,header=512)
        Objective(h,0).write(15,2,0);DefeatRule(h).write(2)
        self.assertEqual(DefeatRule(h).slot,2);self.assertEqual(Objective(h,0).kind,15)

    def test_event_editor_and_dialogue_compatibility(self):
        from reinforcements import Reinforcement
        from conversations import Conversation
        from dialogue import Dialogue,catalogue as dialogues
        r=Reinforcement(self.rom,0);r.write([u['values'] for u in r.units],[2])
        c=Conversation(self.rom,0);c.write(3,1,c.enabled)
        m=Objective(self.rom,0);m.write(15,2,0)
        self.assertEqual(Conversation(self.rom,0).pair,(3,1));Reinforcement(self.rom,0)
        e=Objective(self.rom,1).entry
        if e['scenes']:
            scene=next(d for d in dialogues()['entries'] if d['address'] in e['scenes'])
            d=Dialogue(self.rom,scene);d.write('Test.\n'+d.text);Objective(self.rom,1)
        DefeatRule(self.rom).write(2);Objective(self.rom,0)

    def test_ui_save_backup_undo_rollback_and_menu(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            target=Path(folder)/'test.sfc';target.write_bytes(self.rom.data);before=target.read_bytes()
            app=App();app.withdraw()
            try:
                app.rom=Rom(target);w=app.edit_objectives();app.update()
                self.assertEqual(next(t[0] for t in app.home_tools if t[1]=='Objectives & Progression'),'Maps & Events')
                self.assertFalse(w.help_label.winfo_manager())
                w.kind.set('Unit defeated');w.change_kind();w.faction.set('0 — Player')
                w.unit.set(next(label for label,value in w.unit_options.items() if value==2))
                w.slot.set(next(label for label,value in w.slot_options.items() if value==3))
                self.assertTrue(w.pending());self.assertTrue(w.save());self.assertEqual(DefeatRule(app.rom).slot,3)
                self.assertTrue(app.rom.last_backup.exists());self.assertEqual(Objective(app.rom,0).kind,15)
                w.history(False);self.assertEqual(target.read_bytes(),before)
                w.slot.set(next(label for label,value in w.slot_options.items() if value==2))
                with patch.object(app.rom,'save_original',side_effect=OSError('test failure')),patch('objective_window.messagebox.showerror'):
                    self.assertFalse(w.save())
                self.assertEqual(bytes(app.rom.data),before);self.assertEqual(target.read_bytes(),before)
                with patch('objective_window.ask_unsaved',return_value=None):self.assertFalse(w.settle())
                w.destroy()
            finally:app.destroy()
