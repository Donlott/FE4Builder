import unittest
from rom import ROOT,Rom,army_modules
from map_sprites import MapSprites,compose_frame

class MapSpriteTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_all_deployments_resolve_to_native_sprites(self):
        sprites=MapSprites(self.rom)
        count=0
        for chapter in army_modules(self.rom)[:12]:
            for index in range(chapter.count):
                character=self.rom.values(chapter,index)[0]
                rows,colors,assignment=sprites.sprite(character)
                size=24 if assignment&0x8000 else 16
                self.assertEqual(len(rows),size)
                self.assertTrue(all(len(row)==16 for row in rows))
                self.assertEqual(len(colors),16)
                count+=1
        self.assertEqual(count,1328)

    def test_all_class_variants_have_standing_and_walking_sheets(self):
        sprites=MapSprites(self.rom)
        before=bytes(self.rom.data)
        for class_id in range(72):
            for _,_,assignment in sprites.variants(class_id):
                standing,colors=sprites.frames(assignment,True)
                walking,_=sprites.frames(assignment,False)
                self.assertEqual(len(standing),3)
                self.assertEqual(len(walking),16)
                self.assertEqual(len(standing[0][0]),16)
                self.assertEqual(len(walking[0]),32 if assignment&0x8000 else 24)
        self.assertEqual(bytes(self.rom.data),before)

    def test_class_sprite_viewer(self):
        from FE4Builder import App
        from sprite_window import SpriteWindow
        app=App();app.withdraw();app.rom=self.rom
        try:
            window=SpriteWindow(app,6)
            app.update_idletasks()
            self.assertEqual(len(window.sheets),2)
            self.assertEqual(len(window.photos),19)
            window.variant.current(1);window.palette.current(2);window.refresh()
            self.assertEqual(len(window.photos),19)
            window.destroy()
        finally:
            app.destroy()

    def test_native_composition_includes_legs_and_overlapping_pieces(self):
        def tiles(count):
            data=bytearray()
            for tile in range(count):
                value=1+tile%15
                for pair in (0,2):
                    for _ in range(8):
                        data.extend((255 if value&(1<<pair) else 0,255 if value&(1<<(pair+1)) else 0))
            return bytes(data)
        data=memoryview(self.rom.data)[self.rom.header:]
        short=compose_frame(tiles(10),bytes(data[0x8cc5f:0x8cc5f+22]),False)
        self.assertEqual((len(short),len(short[0])),(24,24))
        self.assertEqual(short[0][0],1)
        self.assertEqual(short[0][16],5)
        self.assertEqual(short[8][8],3) # overlapping main-body piece has priority
        self.assertEqual(short[16][0],10) # foot tile previously omitted
        self.assertEqual(short[23][23],9)
        tall=compose_frame(tiles(16),bytes(data[0x8cc49:0x8cc49+22]),True)
        self.assertEqual((len(tall),len(tall[0])),(32,32))
        self.assertEqual(tall[0][16],3)
        self.assertEqual(tall[16][0],5)
        self.assertEqual(tall[31][31],1)

    def test_gender_and_character_specific_variants_follow_rom(self):
        sprites=MapSprites(self.rom)
        self.assertEqual(sprites.assignment(1)[0],0x800a) # Sigurd's Lord Knight
        # Verify a class edit affects the resolver, rather than using static names.
        address=0x3b267+self.rom.header
        self.rom.data[address+9]=38 # Barbarian
        self.assertEqual(MapSprites(self.rom).assignment(1)[0],6)
        self.assertNotEqual(sprites.sprite(69,0)[1],sprites.sprite(69,1)[1])

    def test_canvas_units_are_images_and_group_badges_remain(self):
        from FE4Builder import App
        from map_window import MapWindow
        app=App()
        app.withdraw()
        try:
            app.rom=self.rom
            window=MapWindow(app,0)
            app.update_idletasks()
            self.assertTrue(window.items)
            self.assertFalse(window.sprite_errors)
            self.assertTrue(all(window.canvas.type(item)=='image' for item in window.items.values()))
            before=bytes(self.rom.data)
            window.unit_palette.current(3)
            window.draw()
            self.assertEqual(bytes(self.rom.data),before)
            window.destroy()
        finally:
            app.update_idletasks()
            app.destroy()

if __name__=='__main__':
    unittest.main()
