import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rom import ROOT,Rom
from conversations import catalogue,Conversation

class ConversationTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_all_routes_and_recruitment_switches_roundtrip_exactly(self):
        before=bytes(self.rom.data);data=catalogue()
        self.assertEqual(len(data['entries']),164)
        self.assertEqual(sum(e['editable'] for e in data['entries']),53)
        for i,e in enumerate(data['entries']):
            m=Conversation(self.rom,i);m.write(*m.pair,m.enabled);self.assertEqual(bytes(self.rom.data),before)
            m.write(*m.pair,[False]*len(m.enabled));expected=bytearray(before)
            for r in e['recruits']:expected[r['address']:r['address']+5]=b'\xfd'*5
            self.assertEqual(self.rom.data,expected)
            Conversation(self.rom,i).write(*m.pair,m.enabled);self.assertEqual(bytes(self.rom.data),before)

    def test_every_editable_route_synchronizes_only_verified_fields(self):
        before=bytes(self.rom.data)
        for i,e in enumerate(catalogue()['entries']):
            if not e['editable']:continue
            m=Conversation(self.rom,i);a,b=m.pair
            for new in range(1,25):
                if new==a:continue
                try:m.write(new,b,m.enabled)
                except ValueError:continue
                break
            else:self.fail(f'No valid alternate initiator for {i}')
            expected=bytearray(before);words=new.to_bytes(2,'little')+b.to_bytes(2,'little')
            for at in e['checks']:expected[at+2:at+6]=words
            for at in e['tables']:expected[at+3:at+7]=words
            for marker in e['markers']:expected[marker['address']:marker['address']+2]=bytes([new,b])
            self.assertEqual(self.rom.data,expected)
            changed=Conversation(self.rom,i);self.assertEqual(changed.pair,(new,b))
            changed.write(a,b,m.enabled);self.assertEqual(bytes(self.rom.data),before)

    def test_invalid_collision_read_only_and_stale_edits_are_atomic(self):
        m=Conversation(self.rom,0);before=bytes(self.rom.data)
        for pair in ((1,1),(0,1),(10,1),(300,1)):
            with self.assertRaises(ValueError):m.write(*pair,m.enabled)
            self.assertEqual(bytes(self.rom.data),before)
        readonly=next(i for i,e in enumerate(catalogue()['entries']) if not e['editable'])
        r=Conversation(self.rom,readonly)
        with self.assertRaises(ValueError):r.write(4,5,r.enabled)
        m.write(3,1,m.enabled)
        with self.assertRaises(ValueError):m.write(4,1,m.enabled)

    def test_custom_layout_and_relocated_table_rejected(self):
        e=catalogue()['entries'][6];r=e['recruits'][0];self.rom.data[r['address']]=0
        with self.assertRaises(ValueError):Conversation(self.rom,6)
        self.rom=Rom(next(ROOT.glob('*.sfc')));self.rom.data[0x6c760+3]^=1
        with self.assertRaises(ValueError):Conversation(self.rom,6)

    def test_headered_rom_and_reinforcement_dialogue_compatibility(self):
        from reinforcements import Reinforcement
        from dialogue import Dialogue,catalogue as dialogues
        headered=SimpleNamespace(data=bytearray(512)+self.rom.data,header=512)
        c=Conversation(headered,0);c.write(3,1,c.enabled)
        self.assertEqual(Conversation(headered,0).pair,(3,1))
        r=Reinforcement(self.rom,0);units=[u['values'][:] for u in r.units];units[0][0]=62;r.write(units,[2])
        c=Conversation(self.rom,0);c.write(3,1,c.enabled)
        self.assertEqual(Reinforcement(self.rom,0).triggers[0]['turn'],2)
        scene=next(d for d in dialogues()['entries'] if d['address'] in c.entry['scenes'])
        d=Dialogue(self.rom,scene);d.write('Test.\n'+d.text)
        self.assertEqual(Conversation(self.rom,0).pair,(3,1));Reinforcement(self.rom,0)
        self.assertTrue(Dialogue(self.rom,scene).text.startswith('Test.'))

    def test_ui_save_undo_rollback_and_linked_editor(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            target=Path(folder)/'test.sfc';target.write_bytes(self.rom.data);baseline=target.read_bytes()
            app=App();app.withdraw()
            try:
                app.rom=Rom(target);w=app.edit_conversations();app.update()
                w.chapter.current(1);w.populate();w.load(6);self.assertTrue(w.scenes)
                w.recruit_vars[0].set(False);self.assertTrue(w.pending());self.assertTrue(w.save())
                self.assertFalse(Conversation(app.rom,6).enabled[0]);self.assertTrue(app.rom.last_backup.exists())
                w.history(False);self.assertEqual(target.read_bytes(),baseline)
                w.recruit_vars[0].set(False);before=bytes(app.rom.data)
                with patch.object(app.rom,'save_original',side_effect=OSError('test failure')),patch('conversation_window.messagebox.showerror'):
                    self.assertFalse(w.save())
                self.assertEqual(bytes(app.rom.data),before);self.assertEqual(target.read_bytes(),baseline)
                with patch('conversation_window.ask_unsaved',return_value=None):
                    self.assertFalse(w.settle());self.assertTrue(w.pending())
                w.recruit_vars[0].set(True);w.open_dialogue();app.update()
                from dialogue_window import DialogueWindow
                child=next(x for x in app.winfo_children() if isinstance(x,DialogueWindow));self.assertIn(child.model.ref,w.model.entry['scenes'])
                child.close();app.update();w.destroy()
            finally:app.destroy()
