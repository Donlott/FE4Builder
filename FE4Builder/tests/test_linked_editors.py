import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom,Field,character_modules,load_module,MODULES
from linked_editors import field_target

class LinkedEditorTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_equipment_resolves_slots_and_item_table_boundaries(self):
        player=Field('Equipment 1',0,1,{},reference='FE4 Player Equipment.txt')
        direct=Field('Equipment 1',0,1,{},reference='FE4 Weapon List.txt')
        slot=load_module(MODULES/'Item Editors'/'FE4 Player Weapon Editor.nmm')
        start=self.rom.address(slot,0)
        self.rom.data[start+89]=0x49
        self.assertEqual(field_target(self.rom,player,90),('Item Editor','FE4 Weapon/Staff Editor 1',0x49))
        for value,name,index in ((0x69,'FE4 Weapon/Staff Editor 1',0x69),(0x6a,'FE4 Ring Editor',0),(0x79,'FE4 Ring Editor',15),(0x7a,'FE4 Weapon/Staff Editor 2',0),(0x88,'FE4 Weapon/Staff Editor 2',14),(0x89,'FE4 Circlet Editor',0)):
            self.assertEqual(field_target(self.rom,direct,value),('Item Editor',name,index))
        self.assertIsNone(field_target(self.rom,player,255))
        self.assertIsNone(field_target(self.rom,direct,255))
        with self.assertRaises(ValueError):field_target(self.rom,player,0)
        with self.assertRaises(ValueError):field_target(self.rom,direct,0x90)

    def test_class_navigation_back_and_matching_equipment_record(self):
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        try:
            app.show_editor('Character Editor')
            module=app.modules[0]
            values=app.rom.values(module,0)
            expected_class=values[next(i for i,f in enumerate(module.fields) if f.name=='Class')]
            app.search.set('00');app.populate()
            before=bytes(self.rom.data)
            app.linked_buttons['Class'].invoke()
            self.assertEqual(app.mode,'Class Editor')
            self.assertEqual(app.record,(0,expected_class))
            self.assertEqual(len(app.navigation),1)
            app.back_button.invoke()
            self.assertEqual(app.mode,'Character Editor')
            self.assertEqual(app.record,(0,0))
            self.assertEqual(app.search.get(),'00')
            self.assertFalse(app.navigation)
            field=next(f for f in module.fields if f.name=='Equipment 1')
            value=values[next(i for i,f in enumerate(module.fields) if f.name=='Equipment 1')]
            mode,name,index=field_target(app.rom,field,value)
            app.linked_buttons['Equipment 1'].invoke()
            self.assertEqual(app.mode,mode)
            self.assertEqual(app.modules[app.record[0]].name,name)
            self.assertEqual(app.record[1],index)
            self.assertEqual(bytes(self.rom.data),before)
        finally:app.destroy()

    def test_pending_links_cancel_discard_and_save(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'linked.sfc';path.write_bytes(self.rom.data)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                app.show_editor('Character Editor')
                index=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Class')
                original=app.rom.values(app.modules[0],0)[index]
                app.editors[index][0].set('38')
                with patch('ui_common.ask_unsaved',return_value=None):
                    app.linked_buttons['Class'].invoke()
                self.assertEqual(app.mode,'Character Editor')
                self.assertTrue(app.pending())
                with patch('ui_common.ask_unsaved',return_value=False) as question:
                    app.linked_buttons['Class'].invoke()
                    question.assert_called_once()
                self.assertEqual(app.record,(0,original))
                app.back_button.invoke()
                app.editors[index][0].set('38')
                with patch('ui_common.ask_unsaved',return_value=True) as question:
                    app.linked_buttons['Class'].invoke()
                    question.assert_called_once()
                self.assertEqual(app.record,(0,38))
                self.assertEqual(Rom(path).values(character_modules()[0],0)[index],38)
                self.assertTrue(app.rom.history.can_undo)
                app.back_button.invoke()
                self.assertEqual(app.rom.values(app.modules[0],0)[index],38)
            finally:app.destroy()

    def test_click_portrait_opens_current_id_and_returns_to_character(self):
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        try:
            app.show_editor('Character Editor')
            self.assertTrue(app.portrait_label.bind('<Button-1>'))
            with patch('FE4Builder.App.edit_portrait') as opened:
                app.open_linked_portrait()
                opened.assert_called_once_with(0)
            self.assertEqual(app.mode,'Character Editor')
            self.assertEqual(app.record,(0,0))
        finally:app.destroy()

if __name__=='__main__':unittest.main()
