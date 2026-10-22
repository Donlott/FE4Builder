import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import Rom,ROOT,character_modules,category_modules
from FE4Builder import App
from promotions import TABLE,character_id,address


class CharacterPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path=Path(self.temp.name)/'promotion.sfc'
        self.path.write_bytes(next(ROOT.glob('*.sfc')).read_bytes())
        self.app=App();self.app.withdraw();self.app.update_idletasks()
        self.app.rom=Rom(self.path);self.app.show_editor('Character Editor')

    def tearDown(self):self.app.destroy();self.temp.cleanup()

    def choose(self,value):
        promotion=self.app.promotion
        promotion['var'].set(next(label for label,key in promotion['options'].items() if key==value))

    def test_promotion_and_stats_commit_together_backup_undo_redo(self):
        app=self.app;rom=app.rom;before=self.path.read_bytes()
        self.assertEqual(app.promotion['id'],1)
        self.assertEqual(rom.data[app.promotion['address']],255)
        module=app.modules[0];fi=next(i for i,f in enumerate(module.fields) if f.name=='Base HP')
        app.editors[fi][0].set('42');self.choose(8)
        self.assertTrue(app.pending());self.assertTrue(app.write_original())
        self.assertFalse(app.pending())
        self.assertEqual(rom.last_backup.read_bytes(),before)
        changed={i for i,(a,b) in enumerate(zip(before,self.path.read_bytes())) if a!=b}
        self.assertEqual(changed,{TABLE,rom.address(module,0)+module.fields[fi].offset})
        self.assertEqual(rom.data[TABLE],8)
        self.assertTrue(any('Promotion Class' in detail for detail in rom.history.state['entries'][-1]['details']))
        rom.undo();app.refresh_after_history()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(app.promotion['options'][app.promotion['var'].get()],255)
        rom.redo();app.refresh_after_history()
        self.assertEqual(app.promotion['options'][app.promotion['var'].get()],8)
        promotion_module=next(m for m in category_modules('Character Settings') if m.name=='FE4 Promotion Editor')
        self.assertEqual(rom.values(promotion_module,0)[0],8)

    def test_failed_save_invalid_value_and_cancel_keep_edits_pending(self):
        app=self.app;before=self.path.read_bytes();self.choose(9)
        with patch.object(app.rom,'save_original',side_effect=OSError('Read only')),patch('FE4Builder.messagebox.showerror'):
            self.assertFalse(app.write_original())
        self.assertEqual(bytes(app.rom.data),before)
        self.assertTrue(app.pending())
        with patch('ui_common.ask_unsaved',return_value=None):self.assertFalse(app.settle())
        self.assertTrue(app.pending())
        app.promotion['var'].set('100')
        with patch('FE4Builder.messagebox.showerror'):
            self.assertFalse(app.apply())
        self.assertEqual(bytes(app.rom.data),before)
        with patch('FE4Builder.messagebox.askyesno',return_value=True):app.reload()
        self.assertFalse(app.pending())

    def test_all_playable_tables_use_ids_and_no_field_in_other_editors(self):
        app=self.app;seen=set()
        for table,module in enumerate(character_modules()):
            for index in range(module.count):
                identity=character_id(module,app.rom.values(module,index))
                self.assertIsNotNone(identity);seen.add(identity)
            app.record=(table,0);app.table.current(table);app.render()
            identity=character_id(module,app.rom.values(module,0))
            self.assertEqual(app.promotion['id'],identity)
            self.assertEqual(app.promotion['address'],TABLE+identity-1)
        self.assertEqual(seen,set(range(1,64)))
        app.show_editor('Enemy Editor');self.assertIsNone(app.promotion)

    def test_copier_header_and_character_id_conflict(self):
        app=self.app
        before=self.path.read_bytes();self.path.write_bytes(bytes(512)+before)
        app.rom=Rom(self.path);app.render();self.choose(7)
        self.assertTrue(app.write_original())
        self.assertEqual(app.rom.data[:512],bytes(512))
        self.assertEqual(app.rom.data[TABLE+512],7)
        self.choose(9)
        field=next(i for i,f in enumerate(app.modules[0].fields) if f.reference=='FE4 Character Numbers.txt')
        var,options=app.editors[field]
        var.set(next(label for label,value in options.items() if value==2))
        saved=bytes(app.rom.data)
        with patch('FE4Builder.messagebox.showerror'):
            self.assertFalse(app.apply())
        self.assertEqual(bytes(app.rom.data),saved)
