import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rom import ROOT,Rom
from chapter_maps import ChapterMap
from map_layout import ARENA,slot

class MapPaintTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_paint_preserves_flags_and_changes_terrain(self):
        model=ChapterMap(self.rom,0)
        old=model.map[5*64+5]
        tile=next(i for i,t in enumerate(model.terrain) if t!=model.terrain[old&1023])
        model.paint(5,5,tile)
        self.assertEqual(model.map[5*64+5]&0xfc00,old&0xfc00)
        self.assertEqual(model.tile_info(5,5)[0],model.terrain[tile])
        self.assertTrue(model.dirty)
        with self.assertRaises(ValueError):model.paint(64,0,0)
        with self.assertRaises(ValueError):model.paint(0,0,1024)

    def test_private_layout_roundtrip_unit_moves_undo_and_redo(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'paint.sfc';path.write_bytes(self.rom.data)
            rom=Rom(path);model=ChapterMap(rom,0)
            originals=[ChapterMap(rom,i).map[:] for i in range(12)]
            original_size=len(rom.data)
            model.paint(5,5,(model.map[5*64+5]+1)&1023)
            model.move(0,2,3)
            details=model.write();rom.save_original('Paint map',details)
            loaded=ChapterMap(Rom(path),0)
            self.assertEqual(loaded.map,model.map)
            self.assertEqual(loaded.positions[0],(2,3))
            self.assertEqual(len(path.read_bytes()),original_size)
            self.assertTrue(rom.last_backup.exists())
            for i in range(1,12):self.assertEqual(ChapterMap(rom,i).map,originals[i])
            rom.undo();self.assertEqual(ChapterMap(rom,0).map,originals[0])
            rom.redo();self.assertEqual(ChapterMap(rom,0).map,model.map)
            # Repeat saves reuse the same private slot rather than consuming space.
            updated=ChapterMap(rom,0);updated.paint(6,5,123);updated.write()
            self.assertEqual(ChapterMap(rom,0).map,updated.map)
            from portraits import pc_address
            h=updated.header+rom.header
            self.assertEqual(pc_address(int.from_bytes(rom.data[h:h+3],'little')),slot(0))

    def test_all_chapters_use_separate_slots_and_copier_headers_work(self):
        for chapter in range(12):
            model=ChapterMap(self.rom,chapter)
            model.paint(5,5,(model.map[5*64+5]+1)&1023)
            model.write()
            self.assertEqual(ChapterMap(self.rom,chapter).map,model.map)
        self.assertEqual(len({slot(i) for i in range(12)}),12)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'headered.smc'
            path.write_bytes(bytes(512)+self.rom.data)
            rom=Rom(path);self.assertEqual(rom.header,512)
            model=ChapterMap(rom,0);model.paint(4,4,987);model.write()
            self.assertEqual(ChapterMap(rom,0).map[4*64+4]&1023,987)
            self.assertEqual(rom.data[:512],bytes(512))

    def test_occupied_storage_and_stale_layout_fail_without_mutations(self):
        model=ChapterMap(self.rom,0);model.paint(0,0,123);model.move(0,3,4)
        self.rom.data[ARENA+self.rom.header]=42
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write()
        self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[ARENA+self.rom.header]=0
        self.rom.data[model.header+self.rom.header:model.header+self.rom.header+3]=self.rom.data[ChapterMap(self.rom,1).header+self.rom.header:ChapterMap(self.rom,1).header+self.rom.header+3]
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write()
        self.assertEqual(bytes(self.rom.data),before)

    def test_right_click_samples_staged_tiles_and_drag_only_pans(self):
        from FE4Builder import App
        from map_window import MapEditorWindow
        app=App();app.withdraw();app.rom=self.rom
        try:
            window=MapEditorWindow(app,0)
            window.canvas.xview_moveto(0);window.canvas.yview_moveto(0)
            window.model.paint(5,5,987)
            window.draw()
            source=SimpleNamespace(x=5.5*window.scale-window.canvas.canvasx(0),y=5.5*window.scale-window.canvas.canvasy(0))
            before=window.model.map[:]
            window.right_press(source);window.right_release(source)
            self.assertEqual(window.brush,987)
            self.assertEqual(window.model.map,before)
            target=SimpleNamespace(x=6.5*window.scale-window.canvas.canvasx(0),y=5.5*window.scale-window.canvas.canvasy(0))
            old=window.model.map[5*64+6]
            window.press(target);window.release(target)
            self.assertEqual(window.model.map[5*64+6],(old&0xfc00)|987)
            window.set_brush(123)
            window.right_press(source)
            dragged=SimpleNamespace(x=source.x+20,y=source.y)
            with patch.object(window.canvas,'scan_dragto') as pan:
                window.right_motion(dragged);window.right_release(dragged)
                self.assertTrue(pan.called)
            self.assertEqual(window.brush,123)
            window.destroy()
        finally:app.destroy()

    def test_separate_editors_and_picker_window_stacking(self):
        from FE4Builder import App
        from map_window import MapEditorWindow,ArmyMapWindow
        app=App();app.withdraw();app.rom=self.rom
        try:
            tiles=MapEditorWindow(app,0)
            self.assertTrue(tiles.edit_tiles)
            self.assertNotIn(str(tiles.deployment_panel),tuple(map(str,tiles.deployment_panel.master.panes())))
            self.assertFalse(tiles.items)
            self.assertEqual(tiles.save_button.cget('text'),'Write tiles to ROM')
            tiles.choose_tile();picker=tiles.tile_picker
            self.assertEqual(str(picker.transient()),'')
            with patch.object(tiles,'lift') as raise_map:
                tiles.raise_on_click(SimpleNamespace(widget=tiles.canvas))
                raise_map.assert_called_once()
            with patch.object(picker,'lift') as raise_picker:
                picker.raise_on_click(SimpleNamespace(widget=picker.canvas))
                raise_picker.assert_called_once()
            tiles.destroy()
            army=ArmyMapWindow(app,0)
            self.assertFalse(army.edit_tiles)
            self.assertIn(str(army.deployment_panel),tuple(map(str,army.deployment_panel.master.panes())))
            self.assertTrue(army.items)
            self.assertEqual(army.save_button.cget('text'),'Write positions to ROM')
            army.choose_tile();self.assertIsNone(army.tile_picker)
            old=army.model.map[:];army.set_brush(123)
            self.assertEqual(army.model.map,old)
            army.destroy()
        finally:app.destroy()

    def test_ui_pick_paint_and_save(self):
        from FE4Builder import App
        from map_window import MapEditorWindow
        from tileset_window import TilesetWindow
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'ui.sfc';path.write_bytes(self.rom.data)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                window=MapEditorWindow(app,0);app.update_idletasks()
                window.choose_tile()
                picker=window.tile_picker
                picker.select(SimpleNamespace(x=1.5*picker.cell,y=1.5*picker.cell))
                self.assertTrue(picker.winfo_exists())
                window.choose_tile()
                self.assertIs(window.tile_picker,picker)
                self.assertEqual(window.brush,33)
                self.assertTrue(window.edit_tiles)
                window.canvas.xview_moveto(0);window.canvas.yview_moveto(0)
                cell=SimpleNamespace(x=5.5*window.scale-window.canvas.canvasx(0),y=5.5*window.scale-window.canvas.canvasy(0))
                old=window.model.map[5*64+5]
                window.press(cell);window.release(cell)
                self.assertEqual(window.model.map[5*64+5],(old&0xfc00)|33)
                self.assertFalse(window.model.positions!=window.model.original_positions)
                self.assertEqual(str(window.save_button.cget('state')),'normal')
                self.assertTrue(window.save())
                self.assertEqual(ChapterMap(Rom(path),0).map[5*64+5]&1023,33)
                window.history_step(False)
                self.assertEqual(window.model.map[5*64+5],old)
                self.assertTrue(picker.winfo_exists())
                window.chapter.current(2);window.change_chapter()
                self.assertEqual(picker.model.chapter,2)
                picker.select(SimpleNamespace(x=2.5*picker.cell,y=.5*picker.cell))
                self.assertEqual(window.brush,2)
                self.assertTrue(picker.winfo_exists())
                window.destroy()
            finally:app.destroy()

if __name__=='__main__':unittest.main()
