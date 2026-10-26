"""ROM-free regressions for sibling editors and temporary modal prompts."""
import tempfile
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from unittest.mock import patch
import unittest
from FE4Builder import App
from rom import Rom
from dialogue import encode
from portrait_document import PortraitDocument
from portraits import decode_palette, pointer_for
from test_portrait_workspace import fixture
from ui_common import ask_unsaved
import dialogue_storage


class EditorWindowTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=self.root/'generated.sfc';self.raw,self.palette=fixture(self.path)
        data=bytearray(self.path.read_bytes());payload=encode('[Start]Hello[End]')
        data[0x600000:0x600003]=pointer_for(0x601000).to_bytes(3,'little')
        data[0x601000:0x601000+len(payload)]=payload;self.path.write_bytes(data)
        self.rom=Rom(self.path)
        entry={'address':0x600000,'group':'Prologue','label':'Generated scene'}
        self.patches=[patch.object(PortraitDocument,'validate_profile',return_value=False),
                      patch('portrait_window.PortraitWindow.slot_names',return_value={0:'Generated portrait'}),
                      patch('portrait_stats.DATA_DIR',self.root),patch('ui_common.DATA_DIR',self.root),
                      patch('dialogue.check_profile'),patch('dialogue_window.check_profile'),
                      patch('dialogue_window.catalogue',return_value={'entries':[entry]}),
                      patch('dialogue_storage.catalogue',return_value={'entries':[entry]})]
        for item in self.patches:item.start()
        self.app=App();self.app.rom=self.rom;self.app.update()

    def tearDown(self):
        if self.app.winfo_exists():self.app.destroy()
        for item in reversed(self.patches):item.stop()
        self.folder.cleanup()

    def prompt_choice(self,label,observed):
        def choose():
            prompt=self.app.grab_current()
            self.assertIsNotNone(prompt)
            self.assertEqual(prompt.title(),'Unsaved changes')
            observed.append(prompt)
            body=prompt.winfo_children()[0]
            buttons=body.winfo_children()[-1]
            next(button for button in buttons.winfo_children() if button.cget('text')==label).invoke()
        self.app.after_idle(choose)

    def stage_portrait(self,window):
        window.document.stage(0,[[0]*128 for _ in range(32)],decode_palette(self.palette))
        window.document.reserve(0x7c0000,0x7c8000)

    def test_both_opening_orders_leave_menu_and_both_editors_interactive(self):
        for portrait_first in (True,False):
            if portrait_first:
                portrait=self.app.edit_portrait(0);dialogue=self.app.edit_dialogue()
            else:
                dialogue=self.app.edit_dialogue();portrait=self.app.edit_portrait(0)
            self.app.update();self.assertIsNone(self.app.grab_current())
            self.assertEqual(set(self.app.editor_windows),{portrait,dialogue})
            dialogue.text.focus_force();dialogue.text.mark_set('insert','end-1c');self.app.update()
            dialogue.text.event_generate('<KeyPress-a>');self.app.update()
            self.assertTrue(dialogue.contents().endswith('a'))
            dialogue.text.delete('1.0','end');dialogue.text.insert('1.0',dialogue.loaded)
            search=next(w for w in portrait.winfo_children()[1].winfo_children()[0].winfo_children() if w.winfo_class()=='TEntry')
            search.focus_force();self.app.update();search.event_generate('<KeyPress-a>');self.app.update()
            self.assertEqual(portrait.search.get(),'a');portrait.search.set('')
            clicked=[];button=ttk.Button(self.app,text='Menu input test');button.pack()
            button.bind('<Button-1>',lambda _:clicked.append(True));self.app.update()
            button.event_generate('<Button-1>',x=2,y=2);self.app.update();self.assertTrue(clicked);button.destroy()
            # Legacy child-close callbacks may call grab_set on their editor.
            portrait.grab_set();dialogue.grab_set();self.assertIsNone(self.app.grab_current())
            dialogue.close();portrait.close();self.assertEqual(self.app.editor_windows,[])

    def test_unsaved_prompt_is_modal_only_until_dismissed(self):
        portrait=self.app.edit_portrait(0);self.stage_portrait(portrait);self.app.update()
        observed=[];self.prompt_choice('Stay here',observed);portrait.close()
        self.assertTrue(portrait.winfo_exists());self.assertTrue(portrait.pending())
        self.assertEqual(len(observed),1);self.assertIsNone(self.app.grab_current())
        self.prompt_choice('Discard changes',observed);portrait.close()
        self.assertFalse(portrait.winfo_exists());self.assertIsNone(self.app.grab_current())

    def test_unsaved_prompt_restores_a_real_picker_grab(self):
        picker=tk.Toplevel(self.app);picker.grab_set();picker.update()
        observed=[];self.prompt_choice('Stay here',observed)
        self.assertIsNone(ask_unsaved(picker))
        self.assertIs(self.app.grab_current(),picker)
        picker.destroy();self.assertIsNone(self.app.grab_current())

    def test_exit_respects_each_editor_unsaved_changes(self):
        portrait=self.app.edit_portrait(0);self.stage_portrait(portrait)
        observed=[];self.prompt_choice('Stay here',observed);self.app.close()
        self.assertTrue(self.app.winfo_exists());self.assertTrue(portrait.winfo_exists())
        self.assertTrue(portrait.pending());self.assertIsNone(self.app.grab_current())
        self.prompt_choice('Discard changes',observed)
        self.assertTrue(self.app.close_editor_windows());self.assertEqual(self.app.editor_windows,[])

    def test_rom_switch_cancellation_keeps_old_editor_and_rom(self):
        portrait=self.app.edit_portrait(0);self.stage_portrait(portrait)
        other=self.root/'other.sfc';other.write_bytes(self.path.read_bytes())
        observed=[];self.prompt_choice('Stay here',observed)
        self.assertFalse(self.app.open_rom(str(other)))
        self.assertIs(self.app.rom,self.rom);self.assertTrue(portrait.winfo_exists());self.assertTrue(portrait.pending())
        self.prompt_choice('Discard changes',observed)
        with patch('rom_selector.remember'):
            self.assertTrue(self.app.open_rom(str(other)))
        self.assertFalse(portrait.winfo_exists());self.assertEqual(self.app.rom.path,other)
        self.assertEqual(self.app.editor_windows,[])

    def test_reopening_same_rom_keeps_portrait_saved_by_close_prompt(self):
        portrait=self.app.edit_portrait(0);self.stage_portrait(portrait)
        before=self.path.read_bytes();observed=[]
        self.prompt_choice('Write changes',observed)
        with patch('rom_selector.remember'):
            self.assertTrue(self.app.open_rom(str(self.path)))
        self.assertNotEqual(self.path.read_bytes(),before)
        self.assertEqual(self.app.rom.original,self.path.read_bytes())
        self.assertEqual(PortraitDocument(self.app.rom).portraits[0].raw,bytes(2048))
        self.assertEqual(self.app.editor_windows,[])

    def test_old_portrait_window_cannot_write_or_launch_another_rom(self):
        portrait=self.app.edit_portrait(0);self.stage_portrait(portrait)
        other=self.root/'other.sfc';other.write_bytes(self.path.read_bytes())
        self.app.rom=Rom(other);before=other.read_bytes()
        with patch('portrait_window.messagebox.showerror') as error,patch.object(self.app,'save_and_launch') as launch:
            self.assertFalse(portrait.save());self.assertFalse(portrait.launch())
            self.assertEqual(error.call_count,2);launch.assert_not_called()
        self.assertEqual(other.read_bytes(),before);self.assertTrue(portrait.pending())

    def test_sibling_dialogue_save_preserves_portrait_draft_and_stale_guard(self):
        portrait=self.app.edit_portrait(0);dialogue=self.app.edit_dialogue();self.stage_portrait(portrait)
        dialogue.text.delete('1.0','end');dialogue.text.insert('1.0','[Start]Changed[End]')
        self.assertTrue(dialogue.save());after=self.path.read_bytes()
        self.assertIsNone(self.app.grab_current());self.assertTrue(portrait.pending())
        with patch('portrait_window.messagebox.showerror') as error:
            self.assertFalse(portrait.save());error.assert_called_once()
        self.assertEqual(self.path.read_bytes(),after);self.assertTrue(portrait.pending())


if __name__=='__main__':unittest.main()
