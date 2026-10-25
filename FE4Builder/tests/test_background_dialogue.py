import tempfile,unittest
from pathlib import Path
from copy import copy
from rom import ROOT,Rom
from event_commands import EventCommands,catalogue

class BackgroundDialogueTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        self.index=next(i for i,e in enumerate(catalogue()['entries']) if any(c['opcode']==0x14 for c in e['commands']))
    def test_exact_operands_protected_mode_invalid_values_and_headers(self):
        original=bytes(self.rom.data);model=EventCommands(self.rom,self.index)
        command=next(i for i,c in enumerate(model.commands) if c['opcode']==0x14)
        at=model.profile['start']+model.commands[command]['offset']
        pointer=next(o['pointer'] for o in model.dialogues() if o['pointer']!=model.values(command)[0])
        for bad in ([123,2,2],[pointer,6,2],[pointer,-1,2],[pointer,2,0],[pointer,2,256],[pointer,2]):
            with self.assertRaises(ValueError):model.write({command:bad})
            self.assertEqual(bytes(self.rom.data),original)
        model.write({command:[pointer,2,4]})
        self.assertEqual(EventCommands(self.rom,self.index).values(command),[pointer,2,4])
        self.assertEqual(self.rom.data[at],0x14);self.assertEqual(self.rom.data[at+5],original[at+5])
        allowed={at+1,at+2,at+3,at+4,at+6}
        self.assertTrue({i for i,(a,b) in enumerate(zip(original,self.rom.data)) if a!=b}<=allowed)
        self.rom.data[at+5]^=1
        with self.assertRaises(ValueError):EventCommands(self.rom,self.index)
        self.rom.data[:]=original
        headered=copy(self.rom);headered.header=512;headered.data=bytearray(512)+self.rom.data
        EventCommands(headered,self.index).write({command:[pointer,2,4]})
        self.assertEqual(EventCommands(headered,self.index).values(command),[pointer,2,4])
    def test_ui_named_background_save_undo_and_linked_dialogue(self):
        from FE4Builder import App
        from dialogue_window import DialogueWindow
        original=bytes(self.rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            path=Path(folder)/'background.sfc';path.write_bytes(original)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                w=app.edit_events(catalogue()['entries'][self.index]['id'])
                command=next(i for i,c in enumerate(w.model.commands) if c['opcode']==0x14)
                w.commands.selection_set(str(command));w.select_command()
                self.assertEqual(len(w.variables),3);self.assertEqual(len(w.field_options[1]),6)
                pointer=next(o['pointer'] for o in w.model.dialogues() if o['pointer']!=w.model.values(command)[0])
                for i,value in enumerate((pointer,2)):
                    w.variables[i].set(next(k for k,v in w.field_options[i].items() if v==value))
                w.variables[2].set('4');self.assertTrue(w.pending());self.assertEqual(path.read_bytes(),original)
                self.assertTrue(w.save());self.assertEqual(EventCommands(app.rom,self.index).values(command),[pointer,2,4])
                self.assertEqual(app.rom.last_backup.read_bytes(),original)
                w.history(False);self.assertEqual(path.read_bytes(),original)
                w.history(True)
                w.commands.selection_set(str(command));w.select_command();w.open_dialogue()
                child=next(x for x in app.winfo_children() if isinstance(x,DialogueWindow))
                at=w.model.profile['start']+w.model.commands[command]['offset']+1
                self.assertEqual(child.model.ref-app.rom.header,at)
                self.assertEqual(int.from_bytes(child.model.pointer,'little'),pointer)
                child.destroy();app.update();self.assertFalse(w.pending());w.destroy()
            finally:app.destroy()
