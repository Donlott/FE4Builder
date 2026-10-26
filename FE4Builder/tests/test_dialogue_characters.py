import unittest
from pathlib import Path
from rom import ROOT,Rom
from dialogue_characters import portrait_command_at,character_choices

class CharacterPickerTests(unittest.TestCase):
    def test_target_is_local_and_preserves_unknown_ids(self):
        text='[Portrait 0001]Hello [Portrait FFFF][End]'
        self.assertEqual(portrait_command_at(text,3),(0,15,1))
        self.assertIsNone(portrait_command_at(text,17))
        self.assertEqual(portrait_command_at(text,0,(20,35))[2],65535)
        self.assertIsNone(portrait_command_at(text,0,(0,len(text))))

    def test_picker_names_preview_replace_insert_undo_without_rom_write(self):
        from FE4Builder import App
        from dialogue_window import DialogueWindow
        from tkinter import ttk
        import tkinter as tk
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
        before=bytes(app.rom.data)
        window=None
        try:
            choices=character_choices(app);self.assertIn('Sigurd',choices[1][0])
            window=DialogueWindow(app);window.withdraw()
            window.text.delete('1.0','end');window.text.insert('1.0','[Portrait 0001]Hello[End]');window.text.edit_reset()
            window.text.mark_set('insert','1.5');window.update_character()
            self.assertIn('Sigurd',window.character_info.get());self.assertIn('graphics 00',window.character_info.get())
            self.assertIsNotNone(window.character_image.photo)
            window.choose_character()
            picker=next(w for w in window.winfo_children() if isinstance(w,tk.Toplevel))
            search=next(w for w in picker.winfo_children() if isinstance(w,ttk.Entry));search.insert(0,'0003')
            button=next(w for w in picker.winfo_children() if isinstance(w,ttk.Button));button.invoke()
            self.assertEqual(window.contents(),'[Portrait 0003]Hello[End]')
            window.text.edit_undo();self.assertEqual(window.contents(),'[Portrait 0001]Hello[End]')
            window.text.mark_set('insert','1.15');window.choose_character(True)
            picker=next(w for w in window.winfo_children() if isinstance(w,tk.Toplevel))
            search=next(w for w in picker.winfo_children() if isinstance(w,ttk.Entry));search.insert(0,'0002')
            next(w for w in picker.winfo_children() if isinstance(w,ttk.Button)).invoke()
            self.assertEqual(window.contents(),'[Portrait 0001][Portrait 0002]Hello[End]')
            window.text.delete('1.0','end');window.text.insert('1.0','[Portrait BEEF][End]');window.text.mark_set('insert','1.4');window.update_character()
            self.assertIn('Unknown character',window.character_info.get())
            self.assertEqual(bytes(app.rom.data),before)
        finally:
            if window:
                if window.job is not None:window.after_cancel(window.job)
                window.destroy()
            app.destroy()
