import unittest
from rom import ROOT,Rom,character_modules
from item_art import ItemArt,ITEM_COUNT,held_pose,item_for_record,INVENTORY_GRAPHICS,INVENTORY_PALETTE,INVENTORY_LOOKUP

class ItemArtTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_all_items_resolve_and_icons_are_read_only(self):
        before=bytes(self.rom.data);art=ItemArt(self.rom)
        for item in range(ITEM_COUNT):
            self.assertTrue(art.name(item))
            rows,colors,note=art.art(item)
            self.assertEqual(len(colors),16)
            self.assertTrue(all(0<=v<16 for row in rows for v in row))
            icon,_=art.icon(item);self.assertEqual((len(icon),len(icon[0])),(16,16))
            self.assertTrue(any(v for row in icon for v in row))
            module,index=art.record(item)
            self.assertEqual(item_for_record(module,index),item)
        self.assertEqual(bytes(self.rom.data),before)
        self.assertIn('Native',art.art(0)[2])
        self.assertIn('Native inventory icon',art.art(0x49)[2])
        self.assertIn('Native inventory icon',art.art(0x6b)[2])

    def test_inventory_iron_sword_matches_the_provided_sprite(self):
        import hashlib
        # Fixture contains the exact four native tiles found from the user image.
        raw=bytes.fromhex('0000000000000001000100000000000000000000000001010101000000000101000000000084c8c0000020c0082888ac000006000a001c08f810d0c0f0e07020010102020405080a1014202840500020020205040b0916122c245848b090e02000580080000000000000000000000000d8588080000000000000000000000000')
        palette=bytes.fromhex('00389d6fd756ef356204bb020d00c3406949525a4419092eea108f2987043201')
        lookup=INVENTORY_LOOKUP+self.rom.header
        self.rom.data[lookup:lookup+2]=bytes(2)
        base=INVENTORY_GRAPHICS+self.rom.header
        self.rom.data[base:base+64]=raw[:64]
        self.rom.data[base+512:base+576]=raw[64:]
        p=INVENTORY_PALETTE+self.rom.header
        self.rom.data[p:p+32]=palette
        art=ItemArt(self.rom);rows,colors=art.icon(0)
        rgb=b''.join(bytes(colors[v]) if v else bytes(3) for row in rows for v in row)
        self.assertEqual(hashlib.sha256(rgb).hexdigest(),'93bcb36c59ac5a71c71b433df8e74bd280d0a1ce1e6304a4028022077027bc8f')
        # Palette changes must be visible even when an icon was already cached.
        self.rom.data[p+2:p+4]=bytes(2)
        self.assertNotEqual(art.icon(0)[1],colors)

    def test_inventory_lookup_aliases_and_corrupt_reference(self):
        art=ItemArt(self.rom)
        data=self.rom.data;header=self.rom.header
        entries=[int.from_bytes(data[INVENTORY_LOOKUP+header+i*2:INVENTORY_LOOKUP+header+i*2+2],'little') for i in range(ITEM_COUNT)]
        self.assertEqual(entries[0],0)
        self.assertEqual(entries[-1],0x1ac) # Circlet, not the slot after the item table.
        self.assertLess(len(set(entries)),ITEM_COUNT) # Shared native icons.
        for item in (0x49,0x6f,0x79,0x7a,0x88,0x89):
            self.assertTrue(any(v for row in art.icon(item)[0] for v in row))
        first=INVENTORY_LOOKUP+header
        data[first:first+2]=(65535).to_bytes(2,'little')
        with self.assertRaises(ValueError):art.icon(0)

    def test_native_obj_rows_and_staff_head_are_composed(self):
        raw=bytearray()
        for t in range(32):
            value=1+t%15
            for pair in (0,2):
                for _ in range(8):raw.extend((255 if value&(1<<pair) else 0,255 if value&(1<<(pair+1)) else 0))
        weapon=held_pose(raw)
        self.assertEqual((len(weapon),len(weapon[0])),(16,32))
        self.assertEqual(weapon[0][0],1)
        self.assertEqual(weapon[0][16],3)
        self.assertEqual(weapon[8][0],2)
        staff=held_pose(raw,True)
        self.assertEqual((len(staff),len(staff[0])),(32,16))
        self.assertEqual(staff[0][0],9)
        self.assertEqual(staff[16][0],1)
        self.assertEqual(staff[24][0],2)

    def test_inventory_slots_and_rom_resizing(self):
        art=ItemArt(self.rom);field=next(f for f in character_modules()[0].fields if f.name=='Equipment 1')
        self.rom.data[self.rom.address(art.player,0)+89]=0x49
        self.assertEqual(art.resolve(field,90),0x49)
        self.assertIsNone(art.resolve(field,255))
        art.icon(0)
        self.rom.data.extend(bytes(32)) # Engine must not retain a memoryview lock.
        self.assertEqual(len(self.rom.data)%0x8000,32)

    def test_equipment_browser_selection_and_item_navigation(self):
        from FE4Builder import App
        from item_browser import ItemBrowser
        app=App();app.withdraw();app.rom=self.rom
        try:
            app.show_editor('Character Editor')
            self.assertEqual(len(app.equipment_icons),3)
            field_index=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Equipment 1')
            field=app.modules[0].fields[field_index];var,options=app.editors[field_index]
            before=bytes(self.rom.data)
            app.browse_equipment(field,var,options)
            browser=next(w for w in app.winfo_children() if isinstance(w,ItemBrowser))
            row=next(i for i,e in enumerate(browser.entries) if e[0]==90)
            browser.list.selection_set(str(row));browser.pick()
            self.assertEqual(options[var.get()],90)
            self.assertEqual(bytes(self.rom.data),before)
            app.update_validation()
            self.assertTrue(app.equipment_icons[field_index].cget('image'))
            # Discard the draft for navigation and browse from Item Editor.
            app.render();app.show_editor('Item Editor')
            self.assertEqual(app.item_preview_view.current(),0)
            self.assertIn('Native inventory icon',app.item_description.get())
            app.item_preview_view.current(1);app.update_equipment_visuals()
            self.assertIn('Native held-weapon',app.item_description.get())
            app.item_preview_view.current(0)
            weapon_type=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Weapon Type')
            app.editors[weapon_type][0].set('-99')
            self.assertTrue(any(i.severity=='Error' for i in app.update_validation()))
            app.render()
            app.browse_items()
            browser=next(w for w in app.winfo_children() if isinstance(w,ItemBrowser))
            row=next(i for i,e in enumerate(browser.entries) if e[0]==0x6b)
            browser.list.selection_set(str(row));browser.pick()
            self.assertEqual(app.modules[app.record[0]].name,'FE4 Ring Editor')
            self.assertEqual(app.record[1],1)
            self.assertTrue(app.item_picture.cget('image'))
            self.assertIn('Native inventory icon',app.item_description.get())
            app.back_button.invoke()
            self.assertEqual(app.modules[app.record[0]].name,'FE4 Weapon/Staff Editor 1')
        finally:app.destroy()

if __name__=='__main__':unittest.main()
