import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom
from chapter_maps import ChapterMap,MAP_HEADERS
from portraits import pointer_for


class MapResizeTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_resize_roundtrip_preserves_terrain_units_other_chapters_and_rom_size(self):
        before=bytes(self.rom.data)
        model=ChapterMap(self.rom,1)
        model.resize(32,24,8,10)
        self.assertTrue(model.dirty)
        self.assertTrue(model.outside_deployments())
        self.assertEqual(bytes(self.rom.data),before)
        details=model.write()
        loaded=ChapterMap(self.rom,1)
        self.assertEqual(loaded.bounds,(8,10,40,34))
        self.assertEqual(loaded.map,model.original_map)
        self.assertEqual(loaded.positions,model.original_positions)
        self.assertEqual(len(self.rom.data),len(before))
        expected=bytearray(before)
        expected[model.header+16:model.header+24]=bytes.fromhex('8000 a000 8002 2002')
        self.assertEqual(self.rom.data,expected)
        self.assertIn('camera bounds',details[-1])
        loaded.resize(64,64);loaded.write()
        self.assertEqual(bytes(self.rom.data),before)

    def test_invalid_sizes_and_origins_leave_staged_bounds_unchanged(self):
        model=ChapterMap(self.rom,0)
        for args in ((15,32,0,0),(32,13,0,0),(65,32,0,0),(32,32,33,0),
                     (32,32,0,-1),(16,14,49,50),(32.0,32,0,0)):
            with self.assertRaises(ValueError):model.resize(*args)
            self.assertEqual(model.bounds,model.original_bounds)
        model.resize(16,14,48,50)
        self.assertEqual(model.bounds,(48,50,64,64))

    def test_stale_or_shared_headers_and_paint_failures_are_atomic(self):
        model=ChapterMap(self.rom,0);model.resize(32,24)
        self.rom.data[model.header+16]^=16
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write()
        self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[model.header+16]^=16
        model.paint(0,0,987)
        before=bytes(self.rom.data)
        with patch('map_layout.plan_layout',side_effect=ValueError('No storage')):
            with self.assertRaises(ValueError):model.write()
        self.assertEqual(bytes(self.rom.data),before)
        at=MAP_HEADERS+3
        self.rom.data[at:at+3]=pointer_for(model.header).to_bytes(3,'little')
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write()
        self.assertEqual(bytes(self.rom.data),before)

    def test_headered_save_paint_backup_undo_redo(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'resize.smc';path.write_bytes(bytes(512)+self.rom.data)
            rom=Rom(path);before=path.read_bytes();model=ChapterMap(rom,0)
            model.resize(40,24,4,3);model.paint(6,8,987)
            rom.save_original('Resize and paint',model.write())
            self.assertEqual(rom.last_backup.read_bytes(),before)
            loaded=ChapterMap(Rom(path),0)
            self.assertEqual(loaded.bounds,(4,3,44,27))
            self.assertEqual(loaded.map[8*64+6]&1023,987)
            rom.undo();self.assertEqual(path.read_bytes(),before)
            rom.redo();self.assertEqual(ChapterMap(rom,0).bounds,(4,3,44,27))

    def test_editor_staging_cancel_discard_and_save_failure(self):
        from FE4Builder import App
        from map_window import MapEditorWindow
        app=App();app.withdraw();app.rom=self.rom
        try:
            window=MapEditorWindow(app,0)
            dialog=window.resize_map();dialog.destroy();window.grab_set()
            self.assertFalse(window.model.dirty)
            window.stage_resize(32,24,4,3)
            self.assertEqual(window.model.bounds,(4,3,36,27))
            self.assertEqual(str(window.save_button.cget('state')),'normal')
            self.assertTrue(window.canvas.find_withtag('crop-mask'))
            with patch('map_window.ask_unsaved',return_value=None):
                self.assertFalse(window.settle())
            self.assertTrue(window.model.dirty)
            before=bytes(self.rom.data)
            with patch.object(self.rom,'save_original',side_effect=OSError('Read only')),patch('map_window.messagebox.showerror'):
                self.assertFalse(window.save())
            self.assertEqual(bytes(self.rom.data),before)
            with patch('map_window.ask_unsaved',return_value=False):
                self.assertTrue(window.settle())
            self.assertFalse(window.model.dirty)
            self.assertEqual(window.model.bounds,(0,0,64,32))
            window.destroy()
        finally:app.destroy()
