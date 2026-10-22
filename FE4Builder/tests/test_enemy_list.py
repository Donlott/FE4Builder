import unittest
from rom import ROOT,Rom,category_modules
from FE4Builder import App
from names import NameEditor


class EnemyListTests(unittest.TestCase):
    def test_numbered_tables_and_item_priorities(self):
        names=[m.name for m in category_modules('Enemy Editor')]
        numbers=[int(name.rsplit(' ',1)[1]) for name in names]
        self.assertEqual(numbers,sorted(numbers))
        self.assertLess(names.index('FE4 Enemy Editor 2'),names.index('FE4 Enemy Editor 10'))
        self.assertEqual([m.name for m in category_modules('Item Editor')][:2],
                         ['FE4 Weapon/Staff Editor 1','FE4 Weapon/Staff Editor 2'])

    def test_names_search_and_live_name_references_without_rom_writes(self):
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')))
        before=bytes(app.rom.data)
        try:
            app.show_editor('Enemy Editor')
            self.assertEqual(app.list.get(0),'00  Gerrard')
            self.assertIn('Gerrard',app.heading.cget('text'))
            for module in app.modules:
                fi=next(i for i,f in enumerate(module.fields) if f.reference=='FE4 Character Name Numbers.txt')
                field=module.fields[fi]
                for row in range(module.count):
                    name_id=app.rom.values(module,row)[fi]
                    try:expected=NameEditor(app.rom,name_id).current
                    except ValueError:expected=field.options.get(name_id) or f'Unknown name 0x{name_id:04X}'
                    self.assertEqual(app.record_name(module,row),expected)
            app.search.set('DiMaggio');self.assertEqual(app.visible,[1])
            self.assertEqual(app.list.get(0),'01  DiMaggio')
            self.assertEqual(bytes(app.rom.data),before)
            # An enemy's label follows its stored name ID, not its row number.
            module=app.modules[0];field=next(f for f in module.fields if f.reference=='FE4 Character Name Numbers.txt')
            address=app.rom.address(module,0)+field.offset
            app.rom.data[address:address+field.size]=(0).to_bytes(field.size,'little')
            self.assertEqual(app.record_name(module,0),NameEditor(app.rom,0).current)
            app.rom.data[address:address+field.size]=(0xffff).to_bytes(field.size,'little')
            self.assertEqual(app.record_name(module,0),'Unknown name 0xFFFF')
        finally:
            app.rom.data[:]=before
            app.destroy()
