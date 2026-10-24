import tempfile,unittest
from pathlib import Path
from tkinter import ttk,Toplevel
from rom import ROOT,Rom,character_modules
from ui_controls import skill_bits,set_skills

class PersonalRingSkillTests(unittest.TestCase):
    def test_named_personal_masks_preserve_existing_names_and_unknown_flags(self):
        for module in character_modules():
            field=next((f for f in module.fields if f.name=='Skills 3'),None)
            if field is None:continue
            bits=skill_bits(field)
            self.assertEqual(bits[8],'Recover');self.assertEqual(bits[32],'Return')
            self.assertEqual(bits[1],'Life');self.assertEqual(bits[2],'Elite')
            self.assertNotIn('Canto',bits.values())
            self.assertEqual(set_skills(0xc1,bits,{1,8,32}),0xe9)
            self.assertEqual(field.options[0x29],'Life + Recover + Return')
    def test_character_picker_stages_exact_byte_and_save_undo(self):
        from FE4Builder import App
        source=next(ROOT.glob('*.sfc'));original=source.read_bytes()
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            path=Path(folder)/'skills.sfc';path.write_bytes(original)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                app.show_editor('Character Editor');module=app.modules[0]
                field_index=next(i for i,f in enumerate(module.fields) if f.name=='Skills 3')
                picker=app.field_controls[field_index]['widget'];old=picker.value()
                picker.open();dialog=next(w for w in picker.winfo_children() if isinstance(w,Toplevel))
                checks={str(w['text']):w for w in descendants(dialog) if isinstance(w,ttk.Checkbutton)}
                self.assertIn('Recover',checks);self.assertIn('Return',checks)
                for name,bit in [('Recover',8),('Return',32)]:
                    if not old&bit:checks[name].invoke()
                next(w for w in descendants(dialog) if isinstance(w,ttk.Button) and w['text']=='Apply to draft').invoke()
                self.assertEqual(picker.value(),old|0x28);self.assertTrue(app.pending())
                self.assertEqual(path.read_bytes(),original)
                app.apply()
                address=app.rom.address(module,0)+module.fields[field_index].offset
                changed={i for i,(a,b) in enumerate(zip(original,app.rom.data)) if a!=b}
                self.assertEqual(changed,{address});self.assertEqual(app.rom.data[address],old|0x28)
                app.rom.save_original('Personal skill test',['Recover and Return'])
                self.assertEqual(path.read_bytes()[address],old|0x28)
                app.rom.undo();self.assertEqual(path.read_bytes(),original)
            finally:app.destroy()
        self.assertEqual(source.read_bytes(),original)
