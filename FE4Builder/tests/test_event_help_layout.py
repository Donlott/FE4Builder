import unittest
from rom import ROOT,Rom
from FE4Builder import App
from event_commands import catalogue,HELP

class EventHelpLayoutTests(unittest.TestCase):
    def test_parameterless_help_collapses_old_fields_resets_scroll_and_keeps_drafts(self):
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')));original=bytes(app.rom.data)
        try:
            entry=next(e for e in catalogue()['entries'] if {0x24,0x13,0xfd}.issubset({c['opcode'] for c in e['commands']}))
            w=app.edit_events(entry['id']);w.geometry('1000x650');app.update()
            def select(op):
                index=next(i for i,c in enumerate(w.model.commands) if c['opcode']==op)
                w.commands.selection_set(str(index));w.select_command();app.update();return index
            unit=select(0x24);old_frame=w.fields
            w.variables[2].set('15');w.parameter_canvas.yview_moveto(1);app.update()
            self.assertGreater(w.help_label.winfo_y(),200)
            restore=select(0x13)
            self.assertFalse(old_frame.winfo_exists());self.assertFalse(w.fields.winfo_manager())
            self.assertEqual(len(w.variables),0);self.assertEqual(w.help.get(),HELP[0x13])
            self.assertLess(w.help_label.winfo_y(),70);self.assertEqual(w.parameter_canvas.yview()[0],0)
            self.assertEqual(w.drafts[unit][2],'15');self.assertTrue(w.pending())
            self.assertFalse(w.model.commands[restore]['editable'])
            for opcode in (0xfd,0x29,0x2a):
                if any(c['opcode']==opcode for c in w.model.commands):
                    select(opcode);self.assertEqual(w.help.get(),HELP[opcode]);self.assertLess(w.help_label.winfo_y(),70)
            select(0x24);self.assertEqual(w.variables[2].get(),'15');self.assertTrue(w.fields.winfo_manager())
            # Repeated switches must not accumulate stale controls or gaps.
            for _ in range(3):
                select(0x13);self.assertLess(w.help_label.winfo_y(),70)
                select(0x24);self.assertEqual(len(w.variables),10)
            self.assertEqual(bytes(app.rom.data),original);w.destroy()
        finally:app.destroy()
