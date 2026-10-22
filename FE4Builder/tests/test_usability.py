import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom,Field
from ui_controls import set_skills,set_blood,skill_bits,blood_pairs,FlagPicker
from ui_common import ContextStore
from FE4Builder import App

class UsabilityTests(unittest.TestCase):
    def test_named_flags_preserve_unrepresented_bits(self):
        field=Field('Skills 1',0,1,{1:'Unused (0x01)',2:'Pursuit',4:'???',64:'Awareness'})
        bits=skill_bits(field)
        self.assertEqual(bits,{2:'Pursuit',64:'Awareness'})
        self.assertEqual(set_skills(67,bits,{2}),3)
        self.assertEqual(set_skills(67,bits,{2,64}),67)
        blood=Field('Blood 4',0,1,{1:'Loputous',2:'Loputous+'})
        pairs=blood_pairs(blood)
        self.assertEqual(set_blood(0x83,pairs,{0:3}),0x83)
        self.assertEqual(set_blood(0x83,pairs,{0:2}),0x82)
        self.assertEqual(set_blood(0x83,pairs,{0:0}),0x80)

    def test_context_isolated_per_rom_and_saved(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            from types import SimpleNamespace
            first=SimpleNamespace(path=Path(folder)/'first.sfc');second=SimpleNamespace(path=Path(folder)/'second.sfc')
            path=Path(folder)/'ui.json';store=ContextStore(path)
            store.put(first,'map',{'chapter':4,'zoom':'2x'},True)
            self.assertEqual(ContextStore(path).get(first,'map'),{'chapter':4,'zoom':'2x'})
            self.assertEqual(store.get(second,'map'),{})

    def test_save_copy_cancel_failure_success_preserve_draft_and_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            source=Path(folder)/'source.sfc';original=next(ROOT.glob('*.sfc')).read_bytes();source.write_bytes(original)
            app=App();app.withdraw();app.rom=Rom(source)
            try:
                app.show_editor('Character Editor');module=app.modules[0]
                index=next(i for i,f in enumerate(module.fields) if f.name=='Base HP')
                app.editors[index][0].set('42');baseline=app.loaded[:]
                with patch('FE4Builder.filedialog.asksaveasfilename',return_value=''):app.save()
                self.assertTrue(app.pending());self.assertFalse(app.rom.dirty);self.assertEqual(app.loaded,baseline)
                copy=Path(folder)/'copy.sfc'
                with patch('FE4Builder.filedialog.asksaveasfilename',return_value=str(copy)),patch.object(app.rom,'save_copy',side_effect=OSError('test failure')),patch('FE4Builder.messagebox.showerror'):app.save()
                self.assertTrue(app.pending());self.assertEqual(bytes(app.rom.data),original)
                with patch('FE4Builder.filedialog.asksaveasfilename',return_value=str(copy)):app.save()
                self.assertTrue(app.pending());self.assertFalse(app.rom.dirty);self.assertEqual(app.loaded,baseline)
                self.assertEqual(app.rom.path,source);self.assertEqual(source.read_bytes(),original)
                self.assertEqual(Rom(copy).values(module,0)[index],42)
                self.assertIsInstance(app.field_controls[next(i for i,f in enumerate(module.fields) if f.name=='Skills 1')]['widget'],FlagPicker)
            finally:app.destroy()

    def test_filter_keeps_current_record_and_reopening_remembers_it(self):
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
        try:
            app.show_editor('Character Editor');app.record=(0,2);app.render()
            app.search.set('Sigurd');app.populate()
            self.assertEqual(app.record,(0,2))
            app.show_menu();app.show_editor('Class Editor');app.show_menu();app.show_editor('Character Editor')
            self.assertEqual(app.record,(0,2));self.assertEqual(app.search.get(),'Sigurd')
            self.assertFalse(app.pending())
        finally:app.destroy()

    def test_tool_context_shortcuts_and_close_cleanup(self):
        import tkinter as tk
        from tkinter import ttk
        from ui_common import prepare_window
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
        try:
            class Tool(tk.Toplevel):
                def __init__(self):
                    super().__init__(app);self.chapter=ttk.Combobox(self,values=['Prologue','Chapter 1','Chapter 2']);self.chapter.current(0)
                    self.zoom=ttk.Combobox(self,values=['1x','2x']);self.zoom.set('1x');self.calls=0;self.title('Test tool')
                def pending(self):return True
                def save(self):self.calls+=1
            window=prepare_window(app,Tool());window.chapter.current(2);window.zoom.set('2x')
            self.assertTrue(window.bind('<Control-s>'));window.destroy()
            app.update()
            restored=prepare_window(app,Tool())
            self.assertEqual(restored.chapter.current(),2);self.assertEqual(restored.zoom.get(),'2x')
            self.assertTrue(restored.title().endswith(' *'))
            restored.destroy();app.update()
        finally:app.destroy()

    def test_known_reference_list_and_slot_owner_preview(self):
        from usage import UsageIndex
        from rom import class_modules
        from item_browser import ItemBrowser
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
        try:
            app.show_editor('Character Editor');module=app.modules[0];values=app.rom.values(module,0)
            field_index=next(i for i,f in enumerate(module.fields) if f.name=='Class')
            classes=class_modules()[0];index=values[field_index]
            users=UsageIndex(app.rom).for_record(classes,index,app.rom.values(classes,index))
            self.assertTrue(any(target==('Character Editor',module.name,0) for _,target in users))
            field_index=next(i for i,f in enumerate(module.fields) if f.name=='Equipment 1')
            field=module.fields[field_index]
            window=ItemBrowser(app,lambda _:None,field,app.rom.field_options(field),values[field_index])
            self.assertIn('Known slot users:',window.details.get());window.destroy()
        finally:app.destroy()

    def test_idle_tools_do_not_overwrite_shared_chapter(self):
        import time
        import tkinter as tk
        from tkinter import ttk
        from ui_common import prepare_window
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
        try:
            def tool(chapter):
                window=tk.Toplevel(app);window.chapter=ttk.Combobox(window,values=['Prologue','Chapter 1','Chapter 2'])
                window.chapter.current(chapter);return prepare_window(app,window,restore=False)
            first=tool(0);second=tool(2)
            time.sleep(.3);app.update()
            self.assertEqual(app.ui_context.get(app.rom,'workspace')['chapter'],2)
            first.destroy();second.destroy()
        finally:app.destroy()

    def test_army_save_copy_preserves_selected_record_and_draft(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
            try:
                app.show_editor('Army Editor');before=bytes(app.rom.data);selected=app.list.curselection();record=app.record
                index=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='X')
                original=app.rom.values(app.modules[0],0)[index];app.editors[index][0].set(str((original+1)%64))
                with patch('FE4Builder.filedialog.asksaveasfilename',return_value=str(Path(folder)/'army.sfc')):app.save()
                self.assertTrue(app.pending());self.assertEqual(bytes(app.rom.data),before)
                self.assertEqual(app.record,record);self.assertEqual(app.list.curselection(),selected)
            finally:app.destroy()
