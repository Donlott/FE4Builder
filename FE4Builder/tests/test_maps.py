import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rom import ROOT,Rom
from chapter_maps import ChapterMap

class MapTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_all_chapters_render_from_rom_and_boundaries(self):
        for chapter in range(12):
            model=ChapterMap(self.rom,chapter)
            pixels=model.pixels()
            self.assertEqual(len(pixels),1024)
            self.assertTrue(all(len(row)==1024 for row in pixels))
            self.assertEqual(model.bounds,(0,0,64,32 if chapter==0 else 64))
            self.assertTrue(model.png(terrain=True).startswith(b'\x89PNG'))
        self.assertEqual(ChapterMap(self.rom,0).tile_info(5,13)[0],9) # Evans guarding tile

    def test_moves_write_only_coordinate_bytes_and_are_atomic(self):
        model=ChapterMap(self.rom,0)
        before=bytes(self.rom.data)
        x,y=model.positions[0]
        model.move(0,(x+1)%64,(y+1)%32)
        model.write()
        address=self.rom.address(model.units,0)
        changed=[i for i,(a,b) in enumerate(zip(before,self.rom.data)) if a!=b]
        self.assertEqual(changed,[address+2,address+3])
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):
            model.move(1,-1,100)
        self.assertEqual(self.rom.data,before)

    def test_multiple_moves_validate_before_writing_and_detect_stale_data(self):
        model=ChapterMap(self.rom,0)
        before=bytes(self.rom.data)
        model.move(0,2,3)
        model.positions[1]=(-1,3)
        with self.assertRaises(ValueError):
            model.write()
        self.assertEqual(self.rom.data,before)
        model.positions[1]=model.original_positions[1]
        address=self.rom.address(model.units,0)
        self.rom.data[address+2]^=1
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):
            model.write()
        self.assertEqual(self.rom.data,before)

    def test_map_drag_save_undo_and_chapter_selection(self):
        from FE4Builder import App
        from map_window import MapWindow
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'map-test.sfc'
            path.write_bytes(self.rom.data)
            app=App()
            app.withdraw()
            try:
                app.rom=Rom(path)
                window=MapWindow(app,0)
                window.zoom.current(0)
                window.draw()
                app.update()
                index=0
                x,y=window.model.positions[index]
                s=window.scale
                # Select and raise the exact unit, including overlapping markers.
                window.selected=index
                window.draw()
                start=SimpleNamespace(x=(x+.5)*s-window.canvas.canvasx(0),y=(y+.5)*s-window.canvas.canvasy(0))
                end=SimpleNamespace(x=(x+1+.5)*s-window.canvas.canvasx(0),y=(y+1+.5)*s-window.canvas.canvasy(0))
                before=path.read_bytes()
                window.press(start)
                self.assertEqual(window.dragging,index)
                window.motion(end)
                window.release(end)
                self.assertEqual(window.model.positions[index],(x+1,y+1))
                self.assertEqual(path.read_bytes(),before)
                self.assertTrue(window.save())
                after=path.read_bytes()
                self.assertNotEqual(after,before)
                self.assertEqual(app.rom.last_backup.read_bytes(),before)
                window.history_step(False)
                self.assertEqual(path.read_bytes(),before)
                window.history_step(True)
                self.assertEqual(path.read_bytes(),after)
                window.group.current(1)
                window.populate()
                window.model.move(0,1,1)
                window.chapter.current(1)
                with patch('map_window.ask_unsaved',return_value=False):
                    window.change_chapter()
                self.assertEqual(window.model.chapter,1)
                self.assertEqual(path.read_bytes(),after)
                window.view.current(1)
                window.draw()
                window.destroy()
            finally:
                app.update_idletasks()
                app.destroy()

if __name__=='__main__':
    unittest.main()
