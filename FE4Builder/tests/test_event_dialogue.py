import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom
from event_commands import EventCommands,catalogue

class EventDialogueTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        self.index=next(i for i,e in enumerate(catalogue()['entries']) if any(c['opcode']==12 for c in e['commands']))
    def test_three_byte_pointer_exact_write_and_invalid_selection(self):
        original=bytes(self.rom.data);model=EventCommands(self.rom,self.index)
        command=next(i for i,c in enumerate(model.commands) if c['opcode']==12)
        at=model.profile['start']+model.commands[command]['offset']+1
        pointer=next(o['pointer'] for o in model.dialogues() if o['pointer']!=model.values(command)[0])
        self.assertGreater(pointer,65535)
        model.write({command:[pointer]})
        self.assertEqual(self.rom.data[at:at+3],pointer.to_bytes(3,'little'))
        self.assertEqual(self.rom.data[:at],original[:at]);self.assertEqual(self.rom.data[at+3:],original[at+3:])
        self.assertEqual(EventCommands(self.rom,self.index).values(command),[pointer])
        with self.assertRaises(ValueError):EventCommands(self.rom,self.index).write({command:[123]})
    def test_search_preview_draft_and_linked_text_edit(self):
        from FE4Builder import App
        from dialogue_picker import DialoguePicker
        from dialogue_window import DialogueWindow
        from dialogue import Dialogue
        original=bytes(self.rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            path=Path(folder)/'dialogue-events.sfc';path.write_bytes(original)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                window=app.edit_events(catalogue()['entries'][self.index]['id'])
                command=next(i for i,c in enumerate(window.model.commands) if c['opcode']==12)
                window.commands.selection_set(str(command));window.select_command()
                window.choose_dialogue()
                picker=next(w for w in window.winfo_children() if isinstance(w,DialoguePicker))
                choice=next(o for o in window.model.dialogues() if o['pointer']!=window.model.values(command)[0] and o['text'].strip())
                picker.search.set(choice['entry']['label']);self.assertTrue(picker.visible)
                index=next(i for i,o in enumerate(picker.visible) if o==choice)
                picker.list.selection_set(index);picker.preview();self.assertIn(choice['text'],picker.text.get('1.0','end'))
                picker.choose();self.assertTrue(window.pending());self.assertEqual(path.read_bytes(),original)
                self.assertTrue(window.save());self.assertEqual(EventCommands(app.rom,self.index).values(command),[choice['pointer']])
                window.commands.selection_set(str(command));window.select_command();window.open_dialogue()
                child=next(w for w in app.winfo_children() if isinstance(w,DialogueWindow))
                reference=window.model.profile['start']+window.model.commands[command]['offset']+1
                self.assertEqual(child.model.ref-app.rom.header,reference)
                self.assertEqual(int.from_bytes(child.model.pointer,'little'),choice['pointer'])
                self.assertTrue(child.model.text)
                child.text.delete('1.0','end');child.text.insert('1.0','Hello![End]')
                self.assertTrue(child.save())
                self.assertEqual(Dialogue(app.rom,child.model.entry).text,'Hello![End]')
                child.destroy();app.update()
                self.assertEqual(window.model.values(command)[0],int.from_bytes(app.rom.data[reference:reference+3],'little'))
                self.assertFalse(window.pending());window.destroy()
                self.assertEqual(app.rom.last_backup.exists(),True)
            finally:app.destroy()
