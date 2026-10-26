import tempfile,unittest
from pathlib import Path
from copy import copy
from unittest.mock import patch
from rom import ROOT,Rom
from event_commands import EventCommands,catalogue,group_units

class GroupLoadTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        from reinforcements import catalogue as reinforcements
        linked={e['id'] for e in reinforcements()['entries']}
        self.index=next(i for i,e in enumerate(catalogue()['entries']) if e['id'] in linked and any(c['opcode']==0x23 for c in e['commands']))
    def test_validated_pair_exact_writes_flags_headers_and_color_protection(self):
        original=bytes(self.rom.data);model=EventCommands(self.rom,self.index)
        command=next(i for i,c in enumerate(model.commands) if c['opcode']==0x23)
        at=model.profile['start']+model.commands[command]['offset']
        for bad in ([58,1,2,3,4],[0,0,2,3,4],[0,65535,2,3,4],[0,1,64,3,4],[0,1,2,-1,4],[0,1,2,3,8],[0,1,2,3]):
            with self.assertRaises(ValueError):model.write({command:bad})
            self.assertEqual(bytes(self.rom.data),original)
        self.rom.data[at+6]|=0x60;baseline=bytes(self.rom.data);model=EventCommands(self.rom,self.index)
        model.write({command:[1,1,5,15,4]})
        self.assertEqual(self.rom.data[at:at+7],bytes([0x23,1,1,0,5,15,0x64]))
        self.assertEqual(self.rom.data[:at],baseline[:at]);self.assertEqual(self.rom.data[at+7:],baseline[at+7:])
        self.assertEqual(EventCommands(self.rom,self.index).values(command),[1,1,5,15,4])
        self.rom.data[at+7]^=2
        with self.assertRaises(ValueError):EventCommands(self.rom,self.index)
        self.rom.data[:]=original
        headered=copy(self.rom);headered.header=512;headered.data=bytearray(512)+self.rom.data
        EventCommands(headered,self.index).write({command:[1,1,5,15,4]})
        self.assertEqual(EventCommands(headered,self.index).values(command),[1,1,5,15,4])
        model=EventCommands(self.rom,self.index);self.rom.data[0x1c000]^=8
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write({command:[1,1,5,15,4]})
        self.assertEqual(bytes(self.rom.data),before)
    def test_group_selector_updates_entry_labels_preview_save_and_undo(self):
        from FE4Builder import App
        from reinforcements import Reinforcement,catalogue as reinforcements
        original=bytes(self.rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            path=Path(folder)/'group-load.sfc';path.write_bytes(original)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                w=app.edit_events(catalogue()['entries'][self.index]['id'])
                command=next(i for i,c in enumerate(w.model.commands) if c['opcode']==0x23)
                w.commands.selection_set(str(command));w.select_command()
                self.assertEqual(len(w.variables),5)
                for group in (1,0,1):
                    w.variables[0].set(next(k for k,v in w.field_options[0].items() if v==group))
                    self.assertEqual(set(w.field_options[1].values()),set(group_units(app.rom,group)))
                w.variables[1].set(next(k for k,v in w.field_options[1].items() if v==1))
                self.assertIn('Army record (read-only here)',w.help.get());self.assertIn('destination',w.help.get())
                self.assertTrue(w.pending());self.assertEqual(path.read_bytes(),original)
                draft=list(map(int,w.drafts[command]));self.assertEqual(draft[:2],[1,1])
                with patch.object(app.rom,'save_original',side_effect=OSError('test')),patch('event_command_window.messagebox.showerror'):
                    self.assertFalse(w.save());self.assertEqual(bytes(app.rom.data),original);self.assertTrue(w.pending())
                self.assertTrue(w.save());self.assertEqual(EventCommands(app.rom,self.index).values(command),draft)
                self.assertEqual(app.rom.last_backup.read_bytes(),original)
                linked=next(i for i,e in enumerate(reinforcements()['entries']) if e['id']==w.model.entry['id'])
                other=Reinforcement(app.rom,linked);unit=next(u for u in other.units if u['offset']==w.model.commands[command]['offset'])
                self.assertEqual((unit['group'],unit['identity']),(1,1))
                w.history(False);self.assertEqual(path.read_bytes(),original)
                w.history(True);self.assertEqual(EventCommands(app.rom,self.index).values(command),draft)
                w.destroy()
            finally:app.destroy()
