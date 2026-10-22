import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom
from chapter_maps import ChapterMap
from tileset_window import TilesetWindow,graphics_tiles,sheet

class TilesetTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_sheet_tiles_match_map_rendering_and_shared_definitions(self):
        for chapter in range(12):
            model=ChapterMap(self.rom,chapter)
            tiles=model.tiles()
            self.assertEqual(len(tiles),1024)
            self.assertEqual(len(graphics_tiles(model,1)),768)
            atlas=sheet(tiles)
            self.assertEqual((len(atlas[0]),len(atlas)),(512,512))
            # Verify the atlas contains each full tile without swapping quadrants.
            for index in (0,255,256,1023):
                self.assertEqual([row[index%32*16:(index%32+1)*16] for row in atlas[index//32*16:(index//32+1)*16]],tiles[index])
        a,b=ChapterMap(self.rom,0),ChapterMap(self.rom,2)
        self.assertEqual(a.graphics,b.graphics)
        self.assertEqual(a.definitions,b.definitions)
        self.assertNotEqual(a.palette,b.palette)

    def test_view_filters_selection_and_export_do_not_modify_rom(self):
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        before=bytes(self.rom.data)
        try:
            window=TilesetWindow(app)
            app.update_idletasks()
            for view,count,first in ((0,1024,0),(1,256,0),(2,768,256),(3,768,0),(4,128,640),(5,640,0)):
                window.view.current(view);window.draw()
                self.assertEqual(len(window.tiles),count)
                self.assertEqual(window.ids[0],first)
                window.selected=count-1;window.details()
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                path=Path(folder)/'sheet.png'
                with patch('tileset_window.filedialog.asksaveasfilename',return_value=str(path)):
                    window.export_sheet()
                self.assertTrue(path.read_bytes().startswith(b'\x89PNG'))
                # PNG dimensions: 32 columns x 20 rows of 8px shared graphics.
                import struct
                self.assertEqual(struct.unpack('>II',path.read_bytes()[16:24]),(256,160))
                with patch('tileset_window.filedialog.asksaveasfilename',return_value=str(path)):
                    window.export_tile()
                self.assertEqual(struct.unpack('>II',path.read_bytes()[16:24]),(8,8))
            window.chapter.current(11);window.load()
            self.assertEqual(window.model.chapter,11)
            self.assertEqual(bytes(self.rom.data),before)
            window.destroy()
        finally:app.destroy()

if __name__=='__main__':unittest.main()
