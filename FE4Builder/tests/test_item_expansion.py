"""Boundary IDs, sparse identity, space reclamation and editor interoperability."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rom import Rom, character_modules
from item_expansion import (ItemExpansion, ARENA, SIZE, record, item_pointer, enabled,
                            put, read, text_entries, DESCRIPTIONS, ICONS, DONORS)
from item_art import ItemArt
from menu_text import MenuText, catalogue, storage_entries, ARENA as TEXT, validate_pool, SIZE as TEXT_SIZE
from item_expansion_fixture import fixture


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=fixture(self.folder.name)
        self.rom=Rom(self.path);self.before=bytes(self.rom.data)

    def tearDown(self):self.folder.cleanup()

    def test_open_is_read_only_and_true_original_slot_count_is_140(self):
        model=ItemExpansion(self.rom)
        self.assertEqual(len(model.items),138);self.assertEqual(len(model.slots),140)
        self.assertEqual(bytes(self.rom.data),self.before)
        self.assertEqual(self.path.read_bytes(),self.before)

    def test_sparse_highest_item_and_slot_preserve_all_original_records(self):
        model=ItemExpansion(self.rom);old={i:record(self.rom,i) for i in model.items}
        model.add_item(0x28,0xFE);model.add_slot(0xFE,0xFE)
        self.assertEqual(enabled(self.rom,'items'),list(range(138))+[254])
        self.assertEqual(enabled(self.rom,'slots'),list(range(1,141))+[254])
        self.assertEqual({i:record(self.rom,i) for i in range(138)},old)
        self.assertEqual(ItemArt(self.rom).stats(254)['Name'],254)
        self.assertEqual(ItemArt(self.rom).resolve(character_modules()[0].fields[-1],255),None)
        self.assertEqual(model.sizes()['save_item_bytes'],794)
        with self.assertRaises(ValueError):model.add_item(0,255)
        with self.assertRaises(ValueError):model.add_slot(0,0)

    def test_private_name_and_description_clone_edit_remove_reclaims_only_own_payload(self):
        for category,text in (('Item names','B'),('Item descriptions','A B')):
            entry=next(e for e in catalogue()['entries'] if e['category']==category and e['id']==0)
            MenuText(self.rom,entry).write(text)
        model=ItemExpansion(self.rom);item=model.add_item(0)
        new=next(e for e in text_entries() if e['id']==item and e['category']=='Item names')
        self.assertEqual(MenuText(self.rom,new).text,'B')
        MenuText(self.rom,new).write('B A')
        self.assertEqual(MenuText(self.rom,new).text,'B A')
        self.assertEqual(MenuText(self.rom,catalogue()['entries'][0]).text,'B')
        original_pointer=MenuText(self.rom,catalogue()['entries'][0]).artwork[0].pointer
        model=ItemExpansion(self.rom);before=model.sizes()['record_bytes'];model.remove('items',item)
        self.assertGreater(before,model.sizes()['record_bytes'])
        self.assertEqual(MenuText(self.rom,catalogue()['entries'][0]).artwork[0].pointer,original_pointer)
        validate_pool(read(self.rom,TEXT,TEXT_SIZE))
        for entry in text_entries()[:3]:self.assertEqual(read(self.rom,TEXT+128+entry['key']*8,8),bytes(8))

    def test_removed_hole_is_reused_and_live_references_block_removal(self):
        model=ItemExpansion(self.rom);item=model.add_item();slot=model.add_slot(item)
        with self.assertRaisesRegex(ValueError,'Player item slot'):model.remove('items',item)
        model.assign(slot,0);model.remove('items',item)
        self.assertEqual(model.add_item(),item)
        table=character_modules()[0];field=next(f for f in table.fields if f.name=='Equipment 1')
        put(self.rom,self.rom.address(table,0)-self.rom.header+field.offset,bytes([slot]))
        # Appearance readers require valid event tables; isolate the reference
        # collection here and cover real high-slot readers in the UI tests.
        from types import SimpleNamespace
        with patch('player_items.SlotLocations',return_value=SimpleNamespace(rows={slot:[SimpleNamespace(kind='starting',title='Character inventory')]})):
            with self.assertRaisesRegex(ValueError,'Character inventory'):ItemExpansion(self.rom).remove('slots',slot)

    def test_icon_and_combat_editors_share_expanded_assignments(self):
        model=ItemExpansion(self.rom);item=model.add_item(0x28)
        from icons import IconDocument
        document=IconDocument(self.rom);document.assign('items',item,2)
        for at,raw in document.plan()[0]:put(self.rom,at,raw)
        self.assertEqual(IconDocument(self.rom).selected('items',item),2)
        ItemExpansion(self.rom)
        from combat_art import CombatArtwork
        combat=CombatArtwork(self.rom)
        donor=combat.candidates(item)[0]
        for at,raw in combat.plan(item,donor):put(self.rom,at,raw)
        self.assertEqual(CombatArtwork(self.rom).aliases[item],donor)
        ItemExpansion(self.rom)

    def test_custom_code_occupied_storage_and_stale_state_fail_without_partial_writes(self):
        for at in (ARENA,0x7E31D,0xD187,0x3F7C4):
            self.rom.data[:]=self.before;self.rom.data[at]^=1;before=bytes(self.rom.data)
            with self.assertRaises(ValueError):ItemExpansion(self.rom).add_item()
            self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[:]=self.before;stale=ItemExpansion(self.rom)
        ItemExpansion(self.rom).add_item()
        before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'changed'):stale.add_slot()
        self.assertEqual(bytes(self.rom.data),before)

    def test_all_117_added_weapon_records_fit_and_final_native_pointer_table_is_reclaimed(self):
        model=ItemExpansion(self.rom)
        for item in range(138,255):self.assertEqual(model.add_item(0),item)
        self.assertEqual(model.sizes()['record_bytes'],117*19)
        self.assertLess(item_pointer(self.rom,254),0x3EAE4)
        old=record(self.rom,0);self.assertEqual(record(self.rom,254),bytes([254])+old[1:])
        model.remove('items',200)
        self.assertEqual(model.sizes()['record_bytes'],116*19)
        self.assertEqual(model.add_item(),200)

    def test_headered_persistence_checksum_backup_and_undo_redo(self):
        path=fixture(self.folder.name,True);rom=Rom(path);before=path.read_bytes()
        model=ItemExpansion(rom);model.add_item(0,254);model.add_slot(254,254)
        rom.save_original('Expansion fixture');after=path.read_bytes()
        self.assertEqual(rom.last_backup.read_bytes(),before)
        self.assertEqual(after[:512],before[:512])
        self.assertEqual(int.from_bytes(read(rom,0xFFDE,2),'little'),sum(rom.data[512:])&65535)
        self.assertEqual(ItemExpansion(Rom(path)).assignments[254],254)
        rom.undo();self.assertEqual(path.read_bytes(),before)
        rom.redo();self.assertEqual(path.read_bytes(),after)

    def test_village_reward_writer_accepts_enabled_high_slot_and_retains_slot_identity(self):
        from villages import Village
        from village_scripts import signature
        from portraits import pointer_for
        ItemExpansion(self.rom).add_slot(0,254)
        raw=bytes.fromhex('4A 57 FF FF 07 FF FF');start=0x110000;ref=0xFE8BF+3
        put(self.rom,start,raw);put(self.rom,ref,pointer_for(start).to_bytes(3,'little'))
        entry=dict(chapter=0,label='Generated reward',start=start,length=len(raw),reward=0,signature=signature(raw),ref=ref,event_id=1)
        with patch('villages.entries',return_value=[entry]):
            Village(self.rom,0).write(254,0,reward_type='item')
            self.assertEqual(Village(self.rom,0).item,254)
            with self.assertRaises(ValueError):Village(self.rom,0).write(253,0,reward_type='item')
            self.rom.save_original('Village fixture')
            from icons import IconDocument
            from villages import pool,ARENA as VILLAGES,digest as village_digest,SIZE as VILLAGE_SIZE
            document=IconDocument(self.rom);document.assign('items',0,2)
            for at,raw in document.plan()[0]:put(self.rom,at,raw)
            # A known independently-owned icon library is the only difference;
            # the original village checksum can be reproduced exactly.
            self.assertEqual(Village(self.rom,0).item,254)
            self.rom.save_original('Icon fixture')
            block=read(self.rom,VILLAGES,VILLAGE_SIZE)
            self.assertEqual(block[64:96],village_digest(block))
            self.assertEqual(Village(self.rom,0).item,254)
            # Later edits start with a checksum which already includes icons.
            document=IconDocument(self.rom);document.assign('items',0,3)
            for at,raw in document.plan()[0]:put(self.rom,at,raw)
            self.rom.save_original('Second icon fixture')
            self.assertEqual(Village(self.rom,0).item,254)
            put(self.rom,VILLAGES+0x8025,b'\xCC')
            with self.assertRaises(ValueError):pool(self.rom)


if __name__=='__main__':unittest.main()
