import unittest
from unittest.mock import patch
from rom import ROOT,Rom,character_modules,class_modules,category_modules,army_modules
from validation import validate_record,validate_structure,shared_notes,explain_field,pointer_field

class ValidationTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_numeric_errors_holy_blood_and_unknown_skill_flags(self):
        module=character_modules()[0];values=self.rom.values(module,0)
        health=next(i for i,f in enumerate(module.fields) if f.name=='Base HP')
        values[health]=256
        self.assertTrue(any(i.severity=='Error' and i.field=='Base HP' for i in validate_record(self.rom,module,0,values)))
        values=self.rom.values(module,0)
        blood=next(i for i,f in enumerate(module.fields) if f.name=='Blood 1');values[blood]=3
        self.assertTrue(any('Minor and major' in i.message for i in validate_record(self.rom,module,0,values)))
        skills=next(i for i,f in enumerate(module.fields) if f.name.startswith('Skills'))
        field=module.fields[skills]
        unused=next((1<<bit for bit in range(field.size*8) if not field.options.get(1<<bit,'') or field.options[1<<bit].lower().startswith(('unused','unknown'))),None)
        if unused is not None:
            values[skills]=unused
            self.assertTrue(any('unknown/unused skill bits' in i.message for i in validate_record(self.rom,module,0,values)))

    def test_escape_flag_is_named_and_preservation_is_explained(self):
        module=character_modules()[0]
        skill=next(i for i,f in enumerate(module.fields) if f.name=='Skills 3')
        self.assertEqual(module.fields[skill].options[4],'Escape (retreat on defeat)')
        self.assertIn('Escape',module.fields[skill].options[5])
        for index in (4,5,16):
            values=self.rom.values(module,index)
            self.assertTrue(values[skill]&4)
            self.assertFalse(any(i.field=='Skills 3' and 'unknown/unused' in i.message for i in validate_record(self.rom,module,index,values)))
            values[skill]&=~4
            self.assertTrue(any('Escape protection is absent' in i.message for i in validate_record(self.rom,module,index,values)))
        self.assertIn('defeated/retreat',explain_field(module,module.fields[skill]))

    def test_pointer_validation_does_not_treat_code_patches_as_pointers(self):
        portrait=next(m for m in category_modules('Character Settings') if 'Portrait Definition Editor' in m.name)
        before=bytes(self.rom.data)
        issues=validate_record(self.rom,portrait,0,[0x7e0000])
        self.assertTrue(any(i.severity=='Error' for i in issues))
        self.assertEqual(bytes(self.rom.data),before)
        modules=[m for m in category_modules('Children Settings') if 'Inheritance Lock' in m.name]
        self.assertTrue(modules)
        self.assertFalse(pointer_field(modules[0],modules[0].fields[0]))

    def test_coordinates_preserve_existing_off_map_values_but_reject_new_ones(self):
        module=army_modules(self.rom)[0];values=self.rom.values(module,0)
        x=next(i for i,f in enumerate(module.fields) if f.name=='X')
        values[x]=70
        self.assertTrue(any(i.severity=='Error' and i.field=='X' for i in validate_record(self.rom,module,0,values)))
        self.rom.data[self.rom.address(module,0)+module.fields[x].offset]=70
        issues=validate_record(self.rom,module,0,values)
        self.assertTrue(any(i.severity=='Warning' and i.field=='X' for i in issues))
        self.assertFalse(any(i.severity=='Error' and i.field=='X' for i in issues))

    def test_invalid_army_group_pointer_and_weapon_class_mismatch(self):
        module=army_modules(self.rom)[-1]
        before=bytes(self.rom.data)
        self.assertTrue(any(i.severity=='Error' for i in validate_record(self.rom,module,0,[65535])))
        self.assertEqual(bytes(self.rom.data),before)
        character=character_modules()[0];values=self.rom.values(character,0)
        class_index=next(i for i,f in enumerate(character.fields) if f.name=='Class')
        values[class_index]=38 # Barbarian: no base sword access.
        issues=validate_record(self.rom,character,0,values)
        self.assertTrue(any('Base class has no Sword access' in i.message for i in issues))
        self.assertFalse(any(i.severity=='Error' for i in issues))

    def test_shared_notes_and_explanations(self):
        module=character_modules()[0]
        equipment=next(f for f in module.fields if f.name=='Equipment 1')
        self.assertIn('Inventory slot ID',explain_field(module,equipment))
        notes=shared_notes(self.rom,module,0,0)
        self.assertTrue(any('stored character records' in n for n in notes))
        self.assertTrue(any('palette pointer' in n for n in notes))
        self.assertTrue(any('stored character IDs' in n for n in shared_notes(self.rom,class_modules()[0],6)))
        item=category_modules('Item Editor')[0]
        self.assertTrue(any('inventory slots' in n for n in shared_notes(self.rom,item,0)))

    def test_structure_detects_bad_portrait_pointer_without_mutation(self):
        self.assertFalse(validate_structure(self.rom))
        from portraits import GRAPHICS_TABLE
        self.rom.data[GRAPHICS_TABLE+self.rom.header:GRAPHICS_TABLE+self.rom.header+3]=(0x7e0000).to_bytes(3,'little')
        before=bytes(self.rom.data)
        issues=validate_structure(self.rom)
        self.assertTrue(any(i.field=='Portrait 00' and i.severity=='Error' for i in issues))
        self.assertEqual(bytes(self.rom.data),before)

    def test_gui_errors_block_apply_warnings_allow_edits_and_reports_are_read_only(self):
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        try:
            app.show_editor('Character Editor')
            module=app.modules[0]
            health=next(i for i,f in enumerate(module.fields) if f.name=='Base HP')
            field=module.fields[health];app.explain_selected_field(module,field)
            self.assertIn('personal base stat',app.field_help.get())
            before=bytes(self.rom.data)
            app.editors[health][0].set('256')
            with patch('FE4Builder.messagebox.showerror') as message:
                self.assertFalse(app.apply());self.assertTrue(message.called)
            self.assertEqual(bytes(self.rom.data),before)
            with patch('FE4Builder.messagebox.askyesno',return_value=True):app.reload()
            blood=next(i for i,f in enumerate(module.fields) if f.name=='Blood 1')
            app.editors[blood][0].set('3')
            self.assertTrue(any(i.severity=='Warning' for i in app.update_validation()))
            with patch('FE4Builder.messagebox.showerror') as message:
                self.assertTrue(app.apply());message.assert_not_called()
            before=bytes(self.rom.data)
            app.check_current_record()
            self.assertEqual(bytes(self.rom.data),before)
            for window in app.winfo_children():
                if window.winfo_class()=='Toplevel':window.destroy()
        finally:app.destroy()

if __name__=='__main__':unittest.main()
