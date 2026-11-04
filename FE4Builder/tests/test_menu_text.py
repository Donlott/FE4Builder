import tempfile
import unittest
from pathlib import Path
from rom import Rom
from menu_text import (MenuText, MenuFont, catalogue, read, ARENA, SIZE, START,
                       pool_digest, pointer_fields, pack, unpack, EXTRA_SKILLS,
                       catalogue_fingerprint, legacy_fingerprint, SKILL_BANK_AT,
                       ITEM_HELP_READERS, ITEM_HELP_ORIGINAL, ITEM_HELP_CALL,
                       ITEM_HELP_HELPER, ITEM_HELP_CODE, item_help_plan, validate_pool)
from menu_text_fixture import make_text_rom


class MenuTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = make_text_rom(cls.directory.name)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.rom = Rom(self.path)

    def entry(self, category, index=0):
        return next(e for e in catalogue()['entries'] if e['category'] == category and e['id'] == index)

    def model(self, category='Item names', index=0):
        return MenuText(self.rom, self.entry(category, index))

    def test_catalogue_and_all_entries_noop_without_rom_mutation(self):
        entries = catalogue()['entries']
        self.assertEqual(len(entries), 710)
        self.assertEqual([e['key'] for e in entries], list(range(710)))
        before = bytes(self.rom.data)
        font = MenuFont(self.rom)
        for entry in entries:
            model = MenuText(self.rom, entry, font)
            self.assertEqual(model.text, '' if entry.get('default_text') else 'A', entry)
            self.assertEqual(model.plan(model.text)[1], [])
        self.assertEqual(bytes(self.rom.data), before)

    def test_each_category_roundtrips_exact_spelling_and_native_artwork(self):
        for category in dict.fromkeys(e['category'] for e in catalogue()['entries']):
            model = self.model(category)
            text = 'B\nA B' if category == 'Skills' else 'B I l'
            model.write(text)
            restored = self.model(category)
            self.assertEqual(restored.text, text, category)
            expected = restored.font.render_line(text.split('\n')[0])
            for y, row in enumerate(expected):
                self.assertEqual(restored.original_rows[y][:len(row)], row, category)
            self.assertEqual(restored.plan(text)[1], [])

    def test_shared_names_and_descriptions_are_isolated(self):
        one, other = self.model(), self.model(index=1)
        self.assertEqual(one.artwork[0].pointer, other.artwork[0].pointer)
        before_other = read(self.rom, other.entry['table'], 16)
        raw_other = other.artwork[0].raw
        one.write('B')
        self.assertEqual(self.model().text, 'B')
        self.assertEqual(self.model(index=1).text, 'A')
        self.assertEqual(read(self.rom, other.entry['table'], 16), before_other)
        self.assertEqual(self.model(index=1).artwork[0].raw, raw_other)
        self.model('Item descriptions').write('B')
        self.assertEqual(self.model('Item descriptions', 2).text, 'A')

    def test_item_help_masks_the_byte_count_on_every_native_display_path(self):
        self.model('Item names').write('B I l')
        self.model('Item descriptions', 1).write('Cripples Mages.')
        model = self.model('Item descriptions', 1)
        count = model.artwork[0].tiles * model.artwork[0].lines
        descriptor = read(self.rom, model.entry['table'], 4)
        self.assertEqual(descriptor[0], count)
        # An unaligned private pointer contaminated the native word read.
        self.assertNotEqual(int.from_bytes(descriptor[:2], 'little'), count)
        for at in ITEM_HELP_READERS:self.assertEqual(read(self.rom, at, 4), ITEM_HELP_CALL)
        self.assertEqual(read(self.rom, ITEM_HELP_HELPER, len(ITEM_HELP_CODE)), ITEM_HELP_CODE)
        validate_pool(read(self.rom, ARENA, SIZE))
        self.assertEqual(item_help_plan(self.rom), [])
        # Simulate an already-saved ROM from the previous editor: repair the
        # loader without reallocating any existing artwork or text records.
        for at in ITEM_HELP_READERS:self.rom.data[at:at + 4] = ITEM_HELP_ORIGINAL
        artwork = model.artwork[0].raw;pointer = model.artwork[0].pointer
        for at, raw in item_help_plan(self.rom):self.rom.data[at:at + len(raw)] = raw
        repaired = self.model('Item descriptions', 1)
        self.assertEqual(repaired.text, 'Cripples Mages.')
        self.assertEqual((repaired.artwork[0].pointer, repaired.artwork[0].raw), (pointer, artwork))

    def test_custom_item_help_code_is_rejected_before_writing_text(self):
        for at in ITEM_HELP_READERS:
            self.rom = Rom(self.path);self.rom.data[at] ^= 1
            before = bytes(self.rom.data)
            with self.assertRaisesRegex(ValueError, 'item-help loader'):
                self.model('Item descriptions', 1).write('Cripples Mages.')
            self.assertEqual(bytes(self.rom.data), before)

    def test_messages_have_separate_ids_and_do_not_mutate_menu_or_other_names(self):
        before = read(self.rom, 0x506700, 110 * 16)
        self.model(index=0x1C).write('B')
        self.assertEqual(read(self.rom, 0x506700, 110 * 16), before)
        self.model('Item names — messages', 0x1A).write('B')
        self.assertEqual(self.model('Item names — messages', 0x19).text, 'A')
        self.assertEqual(self.model(index=0x1A).text, 'A')

    def test_fit_encoding_and_invalid_input_are_atomic(self):
        for category, text in [('Item names', 'W' * 8), ('Item names', 'A\nB'),
                               ('Item names', ''), ('Item names', '😀'),
                               ('Item descriptions', 'A\nB'), ('Skills', 'W' * 7),
                               ('Skills', 'B\nA\nA\nA\nA'),
                               ('Item names — messages', 'i' * 16)]:
            before = bytes(self.rom.data)
            with self.assertRaises(ValueError, msg=(category, text)):
                self.model(category).write(text)
            self.assertEqual(bytes(self.rom.data), before)
        self.model('Item descriptions', 1).write('A\nB\nA')
        self.assertEqual(self.model('Item descriptions', 1).text, 'A\nB\nA')
        self.model('Item descriptions').write('A’s')
        self.assertEqual(self.model('Item descriptions').text, "A's")

    def test_unsupported_font_falls_back_in_existing_record_editors(self):
        from rom import Field
        self.rom.data[0x119971:0x119A21] = bytes(0xB0)
        field = Field('Name', 0, 1, {0: 'Reference label'}, reference='FE4 Weapon Names.txt')
        self.assertEqual(self.rom.field_options(field), {0: 'Reference label'})

    def test_only_planned_slices_change_and_other_reservations_are_preserved(self):
        before = bytes(self.rom.data)
        model = self.model('Skills')
        _, edits = model.plan('B\nA B')
        model.write('B\nA B')
        changed = {i for i, (a, b) in enumerate(zip(before, self.rom.data)) if a != b}
        allowed = {i for at, raw in edits for i in range(at, at + len(raw))}
        self.assertLessEqual(changed, allowed)
        for lo, hi in ((0x600000, 0x800000), (0x500000, 0x502400), (0x506200, 0x507000)):
            self.assertEqual(bytes(self.rom.data[lo:hi]), before[lo:hi])
        self.assertEqual(len(before), len(self.rom.data))

    def test_conflicting_storage_corruption_and_stale_models_are_rejected(self):
        model = self.model()
        self.rom.data[ARENA + 42] = 7
        before = bytes(self.rom.data)
        with self.assertRaises(ValueError): model.write('B')
        self.assertEqual(bytes(self.rom.data), before)
        self.rom.data[ARENA + 42] = 0
        model.write('B')
        self.rom.data[ARENA + START + 1] ^= 1
        before = bytes(self.rom.data)
        with self.assertRaises(ValueError): self.model()
        self.assertEqual(bytes(self.rom.data), before)
        self.rom = Rom(self.path)
        model = self.model()
        self.model().write('B')
        with self.assertRaises(ValueError): model.write('A B')

    def test_foreign_private_alias_cannot_be_reclaimed(self):
        self.model().write('B')
        at = pointer_fields(self.entry('Item names'))[0]
        other = pointer_fields(self.entry('Item names', 1))[0]
        self.rom.data[other:other + 3] = read(self.rom, at, 3)
        before = bytes(self.rom.data)
        with self.assertRaises(ValueError): self.model().write('B B')
        self.assertEqual(bytes(self.rom.data), before)

    def occupy_banks(self, all_banks=False):
        self.model().write('B')
        block = bytearray(read(self.rom, ARENA, SIZE))
        for i in range(5 if all_banks else 1):
            low, high = max(START, i * 0x10000), (i + 1) * 0x10000
            if not all_banks: high -= 10
            at = 128 + i * 8
            block[at:at + 8] = low.to_bytes(4, 'little') + (high - low).to_bytes(4, 'little')
        block[64:96] = pool_digest(block)
        self.rom.data[ARENA:ARENA + SIZE] = block

    def test_allocation_respects_banks_and_exhaustion_is_atomic(self):
        self.occupy_banks()
        self.model(index=6).write('B')
        self.assertEqual(self.model(index=6).artwork[0].pointer, ARENA + 0x10000)
        self.rom = Rom(self.path)
        self.occupy_banks(all_banks=True)
        before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, 'full'):
            self.model(index=6).write('B')
        self.assertEqual(bytes(self.rom.data), before)

    def test_compact_skill_exhaustion_does_not_partially_write(self):
        for i in range(18):
            at = 0x507A00 + i * 32
            self.rom.data[at:at + 14] = b'\x01\x20' * 7
        before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, 'no room'):
            self.model('Skills').write('B')
        self.assertEqual(bytes(self.rom.data), before)

    def test_rewrites_reuse_space_and_unrelated_pending_model_is_safe(self):
        pending = self.model('Class names')
        self.model().write('B')
        pending.write('A B')
        addresses = []
        for text in ('A B', 'B A', 'A B', 'B A'):
            self.model().write(text)
            addresses.append(self.model().artwork[0].pointer)
        self.assertEqual(len(set(addresses)), 1)

    def test_headered_save_reload_backup_undo_and_redo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = make_text_rom(directory, header=True)
            original = path.read_bytes()
            rom = Rom(path)
            entry = self.entry('Item names')
            MenuText(rom, entry).write('B I l')
            rom.save_original('Menu text test')
            self.assertEqual(MenuText(Rom(path), entry).text, 'B I l')
            self.assertTrue(rom.last_backup.exists())
            self.assertEqual(path.read_bytes()[:512], bytes(512))
            rom.undo()
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(MenuText(rom, entry).text, 'A')
            rom.redo()
            self.assertEqual(MenuText(rom, entry).text, 'B I l')

    def test_compact_skill_menu_preserves_other_names_and_type_labels(self):
        before = read(self.rom, 0x507A00, 18 * 32)
        old = read(self.rom, 0x450000, 0x1000)
        self.model('Skills').write('B B\nA')
        for i in range(18):
            self.assertEqual(read(self.rom, 0x507A00 + i * 32 + 14, 18), before[i * 32 + 14:i * 32 + 32])
            if i:
                new_tiles = [int.from_bytes(read(self.rom, 0x507A00 + i * 32 + j, 2), 'big') - 0x100
                             for j in range(0, 14, 2) if read(self.rom, 0x507A00 + i * 32 + j, 2) != b'\x81\x40']
                old_tile = 0x20 + i % 16 + i // 16 * 0x20
                self.assertEqual(len(new_tiles), 1)
                for y in range(2):
                    self.assertEqual(read(self.rom, 0x450000 + (new_tiles[0] + y * 16) * 16, 16),
                                     old[(old_tile + y * 16) * 16:(old_tile + y * 16 + 1) * 16])

    def test_canto_and_return_names_help_and_native_pointers(self):
        compact = read(self.rom, 0x507A00, 18 * 32)
        compact_art = read(self.rom, 0x450000, 0x1000)
        original_skills = {e['key']: (read(self.rom, e['pointer'], 3), self.model('Skills', e['id']).artwork[0].raw)
                           for e in catalogue()['entries'] if e['kind'] == 'skill' and not e.get('default_text')}
        for text_id, native_id, name, default in EXTRA_SKILLS:
            model = self.model('Skills', text_id)
            self.assertTrue(model.unassigned)
            self.assertEqual(model.text, '')
            self.assertEqual(model.plan('')[1], [])
            self.assertEqual(model.entry['pointer'], {1: 0x9AC59, 29: 0x9ACAD}[native_id])
            model.write(default)
            loaded = self.model('Skills', text_id)
            self.assertFalse(loaded.unassigned)
            self.assertEqual(loaded.text, default)
            self.assertEqual(loaded.text.splitlines()[0], name)
            self.assertTrue(ARENA <= loaded.artwork[0].pointer < ARENA + SIZE)
            self.assertEqual(read(self.rom, SKILL_BANK_AT, 5), b'\xEA' * 5)
            loaded.write(name + '\nNew help.')
            self.assertEqual(self.model('Skills', text_id).text, name + '\nNew help.')
        self.assertEqual(read(self.rom, 0x507A00, 18 * 32), compact)
        self.assertEqual(read(self.rom, 0x450000, 0x1000), compact_art)
        for key, (pointer, raw) in original_skills.items():
            entry = catalogue()['entries'][key]
            self.assertEqual(read(self.rom, entry['pointer'], 3), pointer)
            self.assertEqual(MenuText(self.rom, entry).artwork[0].raw, raw)

    def test_existing_canto_help_is_preserved_and_unknown_loader_is_rejected(self):
        extra = self.entry('Skills', 27)
        self.rom.data[extra['pointer']:extra['pointer'] + 3] = read(self.rom, self.entry('Skills')['pointer'], 3)
        model = self.model('Skills', 27)
        self.assertFalse(model.unassigned)
        self.assertEqual(model.text, 'A')
        self.assertEqual(model.plan('A')[1], [])
        for at in (SKILL_BANK_AT, 0x9A3F6):
            old = self.rom.data[at]
            self.rom.data[at] = 0
            before = bytes(self.rom.data)
            with self.assertRaisesRegex(ValueError, 'skill-help'):
                self.model('Skills', 27).write('B')
            self.assertEqual(bytes(self.rom.data), before)
            self.rom.data[at] = old

    def test_legacy_text_directory_migrates_without_losing_existing_edits(self):
        self.assertEqual(legacy_fingerprint().hex(), '71fc7b09c03454b73a9757a6de892422')
        self.model().write('B I l')
        old = self.model()
        pointer, artwork = old.artwork[0].pointer, old.artwork[0].raw
        block = bytearray(read(self.rom, ARENA, SIZE))
        block[16:32] = legacy_fingerprint()
        block[64:96] = pool_digest(block)
        self.rom.data[ARENA:ARENA + SIZE] = block
        before = bytes(self.rom.data)
        self.assertEqual(self.model().text, 'B I l')
        self.assertEqual(self.model().plan('B I l')[1], [])
        self.assertEqual(bytes(self.rom.data), before)
        self.model('Skills', 27).write(EXTRA_SKILLS[0][3])
        self.assertEqual(read(self.rom, ARENA + 16, 16), catalogue_fingerprint())
        restored = self.model()
        self.assertEqual(restored.text, 'B I l')
        self.assertEqual(restored.artwork[0].pointer, pointer)
        self.assertEqual(restored.artwork[0].raw, artwork)

    def test_legacy_directory_cannot_claim_new_entries(self):
        self.model().write('B')
        block = bytearray(read(self.rom, ARENA, SIZE))
        block[16:32] = legacy_fingerprint()
        block[128 + 708 * 8] = 1
        block[64:96] = pool_digest(block)
        self.rom.data[ARENA:ARENA + SIZE] = block
        before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.model()
        self.assertEqual(bytes(self.rom.data), before)

    def test_skill_help_uses_visible_96_pixel_width(self):
        model = self.model('Skills')
        model.render('B\n' + 'W' * 11)
        before = bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError, '96-pixel'):
            model.write('B\n' + 'W' * 12)
        self.assertEqual(bytes(self.rom.data), before)
        self.model('Item descriptions').render('W' * 12)


if __name__ == '__main__':
    unittest.main()
