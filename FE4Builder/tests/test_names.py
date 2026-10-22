import tempfile
import unittest
from pathlib import Path
from rom import ROOT,Rom
from names import NameEditor,NameNeedsSpace,packed_graphics,ENCODE

def prepare_name_fixture(rom):
    """Keep tests independent of name edits made to the user's working ROM."""
    model=NameEditor(rom,0)
    model.write('Sigurd',allow_expand=True)
    rom.data[model.base+rom.header]=4
    rom.data[model.question+rom.header]=5
    offset=0x50a000+rom.header
    rom.data[offset+8:offset+16]=bytes(8)
    NameEditor(rom,0).write('Sigurd')
    rom.original=bytes(rom.data)

class NameTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        prepare_name_fixture(self.rom)

    def test_profiles_and_original_font(self):
        for i in range(63):
            NameEditor(self.rom,i)
        editor=NameEditor(self.rom,0)
        self.assertTrue(editor.current)
        for right in (False,True):
            self.assertEqual(packed_graphics(editor.render(editor.current),editor.tiles,right),
                             editor.read(editor.graphics+256*right,256))

    def test_rename_only_changes_planned_slices(self):
        editor=NameEditor(self.rom,0)
        before=bytes(self.rom.data)
        _,edits=editor.plan('Arthur')
        allowed={i for offset,data in edits for i in range(offset,offset+len(data))}
        editor.write('Arthur')
        self.assertEqual(len(self.rom.data),len(before))
        self.assertEqual(NameEditor(self.rom,0).current,'Arthur')
        for i,(old,new) in enumerate(zip(before,self.rom.data)):
            if old!=new:
                self.assertIn(i,allowed)
        encoded=bytes(ENCODE[c] for c in 'Arthur')
        self.assertEqual(editor.read(0x505c00,8),b'\x09'+encoded+b'\x01')

    def test_oversized_or_invalid_name_is_atomic(self):
        editor=NameEditor(self.rom,0)
        before=bytes(self.rom.data)
        for name in ('','WWWWWWWW','NineChars','A B','Álvis'):
            with self.assertRaises(ValueError):
                editor.write(name)
            self.assertEqual(self.rom.data,before)

    def test_finn_aliases_and_headered_save(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'test.smc'
            path.write_bytes(bytes(512)+self.rom.data)
            rom=Rom(path)
            size=len(rom.data)
            NameEditor(rom,33).write('Lex')
            rom.save_original()
            loaded=Rom(path)
            self.assertEqual(len(loaded.data),size)
            self.assertEqual(NameEditor(loaded,4).current,'Lex')
            self.assertEqual(NameEditor(loaded,33).current,'Lex')
            self.assertEqual(loaded.data[:512],bytes(512))

    def test_wider_name_repacking_preserves_other_names(self):
        def tiles(editor):
            return [editor.read(editor.menu_base+(tile+y*16)*16,16)
                    for y in range(2) for tile in editor.menu_tiles]
        others={i:tiles(NameEditor(self.rom,i)) for i in range(1,24)}
        before=bytes(self.rom.data)
        editor=NameEditor(self.rom,0)
        with self.assertRaises(NameNeedsSpace):
            editor.write('Beowulf')
        self.assertEqual(self.rom.data,before)
        editor.write('Beowulf',allow_expand=True)
        renamed=NameEditor(self.rom,0)
        self.assertEqual(renamed.current,'Beowulf')
        self.assertEqual(renamed.tiles,5)
        self.assertEqual(len(self.rom.data),len(before))
        self.assertEqual(renamed.read(renamed.graphics,256),packed_graphics(renamed.render('Beowulf'),5))
        for i,original in others.items():
            self.assertEqual(tiles(NameEditor(self.rom,i)),original)
        renamed.write('Lex')
        self.assertEqual(NameEditor(self.rom,0).current,'Lex')

    def test_wider_shared_name_survives_save_reload(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'expanded.smc'
            path.write_bytes(bytes(512)+self.rom.data)
            rom=Rom(path)
            NameEditor(rom,33).write('Beowulf',allow_expand=True)
            rom.save_original()
            loaded=Rom(path)
            for i in range(63):
                NameEditor(loaded,i)
            for i in (4,33):
                model=NameEditor(loaded,i)
                self.assertEqual(model.current,'Beowulf')
                self.assertEqual(model.tiles,5)

if __name__=='__main__':
    unittest.main()
