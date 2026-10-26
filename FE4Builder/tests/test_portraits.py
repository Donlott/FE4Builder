import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom
from portraits import *
from fe4_codec import decompress,compress

class PortraitTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_all_portraits_decode_and_tile_palette_round_trip(self):
        for i in range(COUNT):
            portrait=Portrait(self.rom,i)
            self.assertEqual(encode_tiles(portrait.sheet),portrait.raw)
            self.assertEqual(native_sheet_from_editable(editable_sheet(portrait.sheet)),portrait.sheet)
            self.assertEqual(decode_palette(encode_palette(portrait.colors)),portrait.colors)
        self.assertEqual(character_portrait_id(self.rom,1),0)
        self.assertEqual(character_portrait_id(self.rom,2),1)

    def test_compressor_round_trips_and_bank_boundaries(self):
        for i in (0,4,27,52,76,135,157,182,247):
            portrait=Portrait(self.rom,i)
            self.assertEqual(decompress(compress(portrait.raw),0)[0],portrait.raw)

    def test_in_place_import_preserves_other_portraits(self):
        model=Portrait(self.rom,0)
        other=Portrait(self.rom,1)
        # Original streams can be referenced by later portraits. First create
        # a private allocation, then verify it can be reused for a smaller image.
        busy=[[((x*13+y*7)^(x*y))&15 for x in range(128)] for y in range(32)]
        model.import_sheet(busy,model.colors)
        model=Portrait(self.rom,0)
        before=bytes(self.rom.data)
        sheet=[[0]*128 for _ in range(32)]
        description=model.import_sheet(sheet,model.colors)
        self.assertIn('existing',description)
        self.assertEqual(Portrait(self.rom,0).raw,bytes(2048))
        self.assertEqual(Portrait(self.rom,1).raw,other.raw)
        self.assertEqual(len(self.rom.data),len(before))

    def test_relocation_undo_redo_and_shared_palette(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'portraits.sfc'
            path.write_bytes(self.rom.data)
            rom=Rom(path)
            # Exercise a shared palette without touching the user's ROM.
            rom.data[PALETTE_TABLE+3:PALETTE_TABLE+6]=rom.data[PALETTE_TABLE:PALETTE_TABLE+3]
            path.write_bytes(rom.data)
            rom=Rom(path)
            model=Portrait(rom,0)
            other=Portrait(rom,1)
            # High-entropy indices force a new allocation.
            state=17
            sheet=[]
            for y in range(32):
                row=[]
                for x in range(128):
                    state=(state*1103515245+12345)&0x7fffffff
                    row.append((state>>16)&15)
                sheet.append(row)
            colors=model.colors[:]
            colors[1]=(255,0,0)
            before=path.read_bytes()
            description=model.import_sheet(sheet,colors)
            self.assertIn('Relocates',description)
            self.assertIn('private palette',description)
            self.assertEqual(Portrait(rom,1).colors,other.colors)
            self.assertEqual(Portrait(rom,1).raw,other.raw)
            rom.save_original('Portrait import')
            after=path.read_bytes()
            self.assertEqual(len(after),len(before))
            self.assertEqual(Portrait(Rom(path),0).raw,encode_tiles(sheet))
            rom.undo()
            self.assertEqual(path.read_bytes(),before)
            rom.redo()
            self.assertEqual(path.read_bytes(),after)

    def test_occupied_space_and_invalid_image_are_atomic(self):
        model=Portrait(self.rom,0)
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):
            model.import_sheet([[0]*64 for _ in range(64)],model.colors)
        self.assertEqual(self.rom.data,before)
        self.rom.data[ARENA]=1
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):
            allocate(self.rom,[2000])
        self.assertEqual(self.rom.data,before)

    def test_png_export_import_and_static_mouth(self):
        import tkinter as tk
        from portrait_window import load_png,quantize
        app=tk.Tk()
        app.withdraw()
        try:
            model=Portrait(self.rom,0)
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                path=Path(directory)/'portrait.png'
                path.write_bytes(export_png(editable_sheet(model.sheet),model.colors))
                sheet,colors,static,reduced=load_png(app,path)
                self.assertFalse(static)
                self.assertFalse(reduced)
                self.assertFalse(model.plan_import(sheet,colors)[0])
                # Continue to accept the old native layout as an import format.
                path.write_bytes(export_png(model.sheet,model.colors))
                sheet,colors,static,reduced=load_png(app,path)
                self.assertFalse(static)
                self.assertFalse(reduced)
                edits,_=model.plan_import(sheet,colors)
                self.assertFalse(edits)
                path.write_bytes(export_png(model.rows,model.colors))
                sheet,colors,static,reduced=load_png(app,path)
                self.assertTrue(static)
                self.assertEqual(face_from_sheet(sheet,1),face_from_sheet(sheet,2))
            pixels=[[(x*5,y*8,(x*y)%256) for x in range(48)] for y in range(64)]
            _,palette,reduced=quantize(pixels,[[False]*48 for _ in range(64)],pixels[0][0])
            self.assertTrue(reduced)
            self.assertEqual(len(palette),16)
        finally:
            app.destroy()

    def test_editable_sheet_mouth_frames_and_unused_padding(self):
        import tkinter as tk
        from portrait_window import load_png
        model=Portrait(self.rom,0)
        rows=editable_sheet(model.sheet)
        self.assertEqual((len(rows[0]),len(rows)),(64,80))
        self.assertEqual([row[:48] for row in rows[:64]],model.rows)
        self.assertEqual([row[:32] for row in rows[64:80]],[row[96:128] for row in model.sheet[:16]])
        self.assertEqual([row[32:] for row in rows[64:80]],[row[96:128] for row in model.sheet[16:32]])
        rows[64][0]=7;rows[64][32]=8
        packed=native_sheet_from_editable(rows)
        self.assertEqual(packed[0][96],7)
        self.assertEqual(packed[16][96],8)
        self.assertEqual(face_from_sheet(packed),model.rows)
        app=tk.Tk();app.withdraw()
        try:
            # Arbitrary artwork in the unused top-right must not consume colors.
            pixels=[[model.colors[v] for v in row] for row in editable_sheet(model.sheet)]
            for y in range(64):
                for x in range(48,64):pixels[y][x]=(x*4,y*4,(x*y)%256)
            # Encode as RGB so unused padding contains more than 15 colors.
            palette=[];indices=[]
            for row in pixels:
                encoded=[]
                for pixel in row:
                    if pixel not in palette:palette.append(pixel)
                    encoded.append(palette.index(pixel))
                indices.append(encoded)
            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
                path=Path(folder)/'padding.png'
                path.write_bytes(png_bytes(indices,palette))
                _,_,static,reduced=load_png(app,path)
                self.assertFalse(static)
                self.assertFalse(reduced)
        finally:app.destroy()

    def test_import_buttons_preview_write_and_undo(self):
        from FE4Builder import App
        from test_name_ui import descendants
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'portrait-test.sfc'
            path.write_bytes(self.rom.data)
            png=Path(directory)/'new-face.png'
            rows=[[0]*48 for _ in range(64)]
            for y in range(12,52):
                for x in range(8,40):
                    rows[y][x]=1
            colors=[(0,0,0),(255,0,0)]+[(0,0,0)]*14
            png.write_bytes(export_png(rows,colors))
            app=App()
            app.withdraw()
            try:
                app.rom=Rom(path)
                app.show_editor('Character Editor')
                self.assertEqual(app.current_portrait,0)
                before=path.read_bytes()
                app.edit_portrait(0)
                dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
                exported=next(w for w in descendants(dialog) if w.winfo_class()=='TButton' and w.cget('text')=='Export sheet…')
                dialog.layout.current(1) # FE4Builder's below-mouth template
                export_path=Path(directory)/'full-sheet.png'
                with patch('portrait_window.filedialog.asksaveasfilename',return_value=str(export_path)):
                    exported.invoke()
                import struct
                self.assertEqual(struct.unpack('>II',export_path.read_bytes()[16:24]),(64,80))
                imported=next(w for w in descendants(dialog) if w.winfo_class()=='TButton' and w.cget('text')=='Import PNG…')
                write=next(w for w in descendants(dialog) if w.winfo_class()=='TButton' and w.cget('text')=='Write Portrait to ROM')
                with patch('portrait_window.filedialog.askopenfilename',return_value=str(png)):
                    imported.invoke()
                self.assertFalse(write.instate(['disabled']))
                self.assertEqual(path.read_bytes(),before)
                dialog.document.reserve(0x7c0000,0x7c8000)
                write.invoke()
                self.assertTrue(app.rom.history.can_undo)
                self.assertNotEqual(path.read_bytes(),before)
                self.assertEqual(app.rom.last_backup.read_bytes(),before)
                dialog.destroy()
                app.history_step(False)
                self.assertEqual(path.read_bytes(),before)
            finally:
                app.destroy()

if __name__=='__main__':
    unittest.main()
