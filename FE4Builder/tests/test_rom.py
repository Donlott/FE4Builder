import tempfile
import unittest
from pathlib import Path
from rom import Rom, ROOT, character_modules, army_modules, EDITOR_CATEGORIES, category_modules

class CharacterTests(unittest.TestCase):
    def test_equipment_names_follow_item_slots(self):
        field = next(f for f in self.modules[0].fields if f.name == 'Equipment 1')
        names = self.rom.field_options(field)
        self.assertEqual(names[90], 'Elwind')
        self.assertEqual(names[1], 'Iron Sword')
        self.assertEqual(names[140], 'Circlet')
        self.assertEqual(names[255], 'Nothing')
        self.assertFalse(any('Shop' in name for name in names.values()))
        self.rom.data[0x3f489 + 89] = 0
        self.assertEqual(self.rom.field_options(field)[90], 'Iron Sword')

    def test_all_module_categories_preserve_bytes_and_signed_fields(self):
        rom = Rom(next(ROOT.glob('*.sfc')))
        signed_seen = False
        for category in EDITOR_CATEGORIES:
            for module in category_modules(category):
                for index in range(module.count):
                    rom.write(module, index, rom.values(module, index))
                signed = next((i for i, f in enumerate(module.fields) if f.signed), None)
                if signed is not None:
                    signed_seen = True
                    before = bytes(rom.data)
                    values = rom.values(module, 0)
                    values[signed] = -1
                    rom.write(module, 0, values)
                    self.assertEqual(rom.values(module, 0)[signed], -1)
                    rom.data[:] = before
        self.assertTrue(signed_seen)
        self.assertFalse(rom.dirty)

    def setUp(self):
        self.modules = character_modules()
        self.source = next(ROOT.glob('*.sfc'))
        self.rom = Rom(self.source)

    def test_all_records_and_dropdowns(self):
        self.assertEqual(len(self.modules), 7)
        for module in self.modules:
            for index in range(module.count):
                values = self.rom.values(module, index)
                self.assertEqual(len(values), len(module.fields))
                self.rom.write(module, index, values)
        self.assertFalse(self.rom.dirty)

    def test_sigurd_and_isolated_edit(self):
        module = self.modules[0]
        values = self.rom.values(module, 0)
        self.assertEqual(values[1], 35)
        self.assertEqual(values[2], 4)
        before = bytes(self.rom.data)
        values[1] = 40
        self.rom.write(module, 0, values)
        changed = [i for i, (a, b) in enumerate(zip(before, self.rom.data)) if a != b]
        self.assertEqual(changed, [self.rom.address(module, 0) + 1])

    def test_headered_equivalence_and_save(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            headered = Path(directory) / 'headered.smc'
            headered.write_bytes(bytes(512) + self.rom.data)
            other = Rom(headered)
            for module in self.modules:
                for index in range(module.count):
                    self.assertEqual(self.rom.values(module, index), other.values(module, index))
            values = other.values(self.modules[0], 0)
            values[1] = 41
            other.write(self.modules[0], 0, values)
            target = Path(directory) / 'edited.smc'
            other.save_copy(target)
            self.assertEqual(Rom(target).values(self.modules[0], 0)[1], 41)
            self.assertEqual(target.stat().st_size, headered.stat().st_size)
            self.assertEqual(Rom(headered).values(self.modules[0], 0)[1], 35)
            with self.assertRaises(ValueError):
                other.save_copy(headered)

    def test_invalid_edit_is_atomic(self):
        module = self.modules[0]
        before = bytes(self.rom.data)
        values = self.rom.values(module, 0)
        values[1], values[-1] = 42, 256
        with self.assertRaises(ValueError):
            self.rom.write(module, 0, values)
        self.assertEqual(before, self.rom.data)

    def test_original_overwrite_and_external_change_guard(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory) / 'original.sfc'
            path.write_bytes(self.rom.data)
            rom = Rom(path)
            values = rom.values(self.modules[0], 0)
            values[1] = 43
            rom.write(self.modules[0], 0, values)
            rom.save_original()
            self.assertEqual(Rom(path).values(self.modules[0], 0)[1], 43)
            self.assertFalse(rom.dirty)
            changed = bytearray(path.read_bytes())
            changed[-1] ^= 1
            path.write_bytes(changed)
            with self.assertRaises(ValueError):
                rom.save_original()
            self.assertEqual(path.read_bytes(), changed)

    def test_army_split_records_and_pointers(self):
        units, pointers = army_modules()
        self.assertEqual((units.count, units.stride, pointers.count), (2000, 8, 72))
        self.assertEqual(self.rom.address(units, 1), 0x1c07c)
        for module in (units, pointers):
            self.rom.address(module, module.count - 1)
            before = bytes(self.rom.data)
            values = self.rom.values(module, 1)
            values[0] ^= 1
            self.rom.write(module, 1, values)
            differences = [i for i, (a, b) in enumerate(zip(before, self.rom.data)) if a != b]
            self.assertEqual(differences, [self.rom.address(module, 1)])

    def test_chapter_groups_and_terminators(self):
        chapters = army_modules(self.rom)
        self.assertEqual([m.count for m in chapters[:2]], [49, 86])
        self.assertEqual(chapters[-1].count, 58)
        addresses = [address for module in chapters[:-1] for address in module.addresses]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertEqual(len(addresses), 1328)
        for module in chapters[:-1]:
            for i in range(module.count):
                self.assertNotEqual(self.rom.values(module, i)[0], 0xffff)
        self.assertEqual(chapters[0].addresses[0], 0x1c074)
        self.assertIn('Evans', chapters[0].names[-1])

    def test_chapter_invalid_pointer_rejected(self):
        self.rom.data[0x1c000:0x1c002] = b'\x00\x00'
        with self.assertRaises(ValueError):
            army_modules(self.rom)

    def test_skill_bitmask_combinations(self):
        for module in self.modules[:4]:
            fields = {f.name: f for f in module.fields}
            self.assertEqual(fields['Skills 1'].options[66], 'Pursuit + Awareness')
            self.assertEqual(fields['Skills 2'].options[3], 'Critical + Ambush')
            self.assertEqual(fields['Skills 3'].options[19], 'Life + Elite + Bargain')
            self.assertIn('Unused (0x08)', fields['Skills 1'].options[10])
        module = self.modules[0]
        values = self.rom.values(module, 2)
        skill = next(i for i, f in enumerate(module.fields) if f.name == 'Skills 1')
        self.assertEqual(values[skill], 66)  # Alec
        before = bytes(self.rom.data)
        self.rom.write(module, 2, values)
        self.assertEqual(self.rom.data, before)

if __name__ == '__main__':
    unittest.main()
