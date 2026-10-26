"""ROM-free integration checks for the merged Studio/FE4Builder portrait editor.

Synthetic banks contain generated tiles, never game data. Only the game's code
fingerprint check is bypassed for these fixtures; codecs, pointers, storage,
image import, history and GUI callbacks run normally.
"""
import random
import struct
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from rom import Rom
from portraits import (COUNT, decode_tiles, encode_tiles, encode_palette, decode_palette,
    editable_sheet, native_sheet_from_editable, studio_sheet, native_sheet_from_studio,
    face_from_sheet, export_png, png_bytes)
from portrait_codec import compress, decompress
from portrait_document import PortraitDocument, GFX_TABLE, PAL_TABLE
from portrait_window import load_png, open_portrait_window


def fixture(path,header=False):
    data=bytearray(0x800000)
    data[0xffc0:0xffcb]=b'FIREEMBLEM4';data[0xffd5]=0x25
    rng=random.Random(37)
    sheet=[[rng.randrange(16) for _ in range(128)] for _ in range(32)]
    raw=encode_tiles(sheet);blob=compress(raw);address=0xa65b5
    data[address:address+len(blob)]=blob
    palette=encode_palette([(i*16,i*8,i*4) for i in range(16)])
    data[0xca800:0xca820]=palette
    for idx in range(COUNT):
        data[GFX_TABLE+3*idx:GFX_TABLE+3*idx+3]=(address|0xc00000).to_bytes(3,'little')
        data[PAL_TABLE+3*idx:PAL_TABLE+3*idx+3]=(0xcca800).to_bytes(3,'little')
    path.write_bytes((b'H'*512 if header else b'')+data)
    return raw,palette


class LayoutTests(unittest.TestCase):
    def test_both_artist_layouts_preserve_every_native_pixel_and_talking_frame(self):
        sheet=[[((x*5)^(y*7)^(x//8))%16 for x in range(128)] for y in range(32)]
        self.assertEqual(native_sheet_from_studio(studio_sheet(sheet)),sheet)
        self.assertEqual(native_sheet_from_editable(editable_sheet(sheet)),sheet)
        for frame in (1,2):
            face=face_from_sheet(sheet,frame)
            for y in range(16):self.assertEqual(face[32+y][:32],sheet[(frame-1)*16+y][96:128])
        with self.assertRaises(ValueError):native_sheet_from_studio([[0]*64]*80)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.path=self.root/'fixture.sfc';self.raw,self.palette=fixture(self.path)
        self.profile=patch.object(PortraitDocument,'validate_profile',return_value=False);self.profile.start()
        self.rom=Rom(self.path)
        self.tk=tk.Tk();self.tk.withdraw()

    def tearDown(self):
        self.tk.destroy();self.profile.stop();self.folder.cleanup()

    def doc(self):return PortraitDocument(self.rom)

    def png(self,rows,colors=None,name='test.png'):
        path=self.root/name
        path.write_bytes(export_png(rows,colors or decode_palette(self.palette)))
        return path

    def test_png_roundtrip_both_layouts_native_and_legacy_face(self):
        sheet=decode_tiles(self.raw);colors=decode_palette(self.palette)
        for rows in (studio_sheet(sheet),editable_sheet(sheet),sheet):
            result,actual,static,reduced=load_png(self.tk,self.png(rows),False)
            self.assertEqual(encode_tiles(result),self.raw)
            self.assertEqual(encode_palette(actual),self.palette)
            self.assertFalse(static);self.assertFalse(reduced)
        _,_,static,_=load_png(self.tk,self.png(face_from_sheet(sheet)),False)
        self.assertTrue(static)

    def test_duplicate_indexed_palette_entries_are_retained(self):
        palette=[(0,0,0)]*16;palette[3]=palette[7]=(255,0,0)
        sheet=[[7 if x%2 else 3 for x in range(128)] for y in range(32)]
        result,colors,_,_=load_png(self.tk,self.png(studio_sheet(sheet),palette),False)
        self.assertEqual(result,sheet);self.assertEqual(colors[3],colors[7])

    def test_builder_unused_padding_does_not_consume_colors(self):
        rows=editable_sheet(decode_tiles(self.raw));colors=decode_palette(self.palette)
        pixels=[[colors[v] for v in row] for row in rows]
        for y in range(64):
            for x in range(48,64):pixels[y][x]=(x*3,y*3,x*y%256)
        palette=[];indices=[]
        for row in pixels:
            result=[]
            for c in row:
                if c not in palette:palette.append(c)
                result.append(palette.index(c))
            indices.append(result)
        path=self.root/'padding.png';path.write_bytes(png_bytes(indices,palette))
        _,_,_,reduced=load_png(self.tk,path,False)
        self.assertFalse(reduced)

    def test_excess_colors_require_opt_in_and_invalid_dimensions_reject(self):
        path=self.root/'many.png';rows=[[x+y*64 for x in range(64)] for y in range(64)]
        colors=[((i*19)%256,(i*31)%256,(i*7)%256) for i in range(4096)]
        path.write_bytes(png_bytes(rows,colors))
        with self.assertRaisesRegex(ValueError,'Enable color reduction'):load_png(self.tk,path,False)
        sheet,colors,_,reduced=load_png(self.tk,path,True)
        self.assertTrue(reduced);self.assertLessEqual(max(max(row) for row in sheet),15)
        with self.assertRaises(ValueError):load_png(self.tk,self.png([[0]*20]*20),False)

    def test_partial_alpha_rejected(self):
        import zlib
        def chunk(kind,body):return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
        path=self.root/'alpha.png'
        path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',64,64,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([255,0,0,128])*64)*64))+chunk(b'IEND',b''))
        with self.assertRaisesRegex(ValueError,'partial transparency'):load_png(self.tk,path,False)

    def test_shared_grey_is_fixed_and_palette_word_preserved(self):
        doc=self.doc();doc.shared_grey=True
        colors=decode_palette(self.palette);colors[14]=(106,106,106)
        rows=[[14]*128 for _ in range(32)]
        path=self.png(studio_sheet(rows),colors)
        result,actual,_,_=load_png(self.tk,path,False,True)
        self.assertEqual(result,rows)
        doc.stage(0,result,actual)
        self.assertEqual(doc.pending[0][1][28:30],self.palette[28:30])
        colors[14]=(255,0,0)
        with self.assertRaisesRegex(ValueError,'shared grey'):load_png(self.tk,self.png(studio_sheet(rows),colors),False,True)

    def test_staged_write_isolates_shared_assets_and_history_header_roundtrip(self):
        for header in (False,True):
            fixture(self.path,header);rom=Rom(self.path);doc=PortraitDocument(rom)
            sheet=decode_tiles(self.raw);sheet[0][0]^=1
            colors=decode_palette(self.palette);colors[1]=(255,0,0)
            before=self.path.read_bytes();doc.stage(0,sheet,colors)
            self.assertEqual(self.path.read_bytes(),before)
            doc.reserve(0x7c0000,0x7c8000);doc.commit(rom)
            after=self.path.read_bytes();check=PortraitDocument(rom)
            self.assertNotEqual(after,before);self.assertEqual(len(after),len(before))
            if header:self.assertEqual(after[:512],b'H'*512)
            self.assertEqual(check.portraits[0].raw,encode_tiles(sheet))
            self.assertEqual(check.portraits[1].raw,self.raw);self.assertEqual(check.portraits[1].palette,self.palette)
            self.assertEqual(rom.last_backup.read_bytes(),before)
            rom.undo();self.assertEqual(self.path.read_bytes(),before)
            rom.redo();self.assertEqual(self.path.read_bytes(),after)
            # History is per-path; reset it before testing another header format.
            if not header:self.path=self.root/'headered.smc'

    def test_optimization_verifies_all_slots_and_preserves_unrelated_bytes(self):
        doc=self.doc();doc.optimize_portraits=True;before=bytes(self.rom.data)
        plan=doc.packing_plan();doc.commit(self.rom);after=bytes(self.rom.data)
        allowed=plan.allowed|set(range(GFX_TABLE,PAL_TABLE+COUNT*3))|set(range(0xffdc,0xffe0))|set(range(0x40ffdc,0x40ffe0))
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,after)) if a!=b))
        self.assertTrue(all(p.raw==self.raw for p in self.doc().portraits))

    def test_failed_write_stale_snapshot_and_occupied_space_are_atomic(self):
        doc=self.doc();doc.stage(0,[[0]*128 for _ in range(32)],decode_palette(self.palette));before=bytes(self.rom.data)
        with self.assertRaisesRegex(ValueError,'Reserve space'):doc.commit(self.rom)
        self.assertEqual(bytes(self.rom.data),before);self.assertEqual(self.path.read_bytes(),before)
        with self.assertRaises(ValueError):doc.reserve(0xa6500,0xa8000)
        doc.reserve(0x7c0000,0x7c8000)
        with patch.object(self.rom,'save_original',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):doc.commit(self.rom)
        self.assertEqual(bytes(self.rom.data),before);self.assertTrue(doc.pending)
        self.rom.data[0x200]^=1
        with self.assertRaisesRegex(ValueError,'changed while'):doc.commit(self.rom)
        self.assertEqual(self.path.read_bytes(),before)

    def test_external_file_change_is_not_overwritten(self):
        doc=self.doc();doc.stage(0,[[0]*128 for _ in range(32)],decode_palette(self.palette));doc.reserve(0x7c0000,0x7c8000)
        altered=bytearray(self.path.read_bytes());altered[0x200]^=1;self.path.write_bytes(altered)
        with self.assertRaisesRegex(ValueError,'outside'):doc.commit(self.rom)
        self.assertEqual(self.path.read_bytes(),altered);self.assertEqual(bytes(self.rom.data),doc.snapshot)

    def test_integrated_gui_stage_preview_both_exports_write_f5_and_close(self):
        from FE4Builder import App
        app=App();app.rom=self.rom;app.update()
        try:
            # Slot labels normally come from game character records, absent in generated banks.
            with patch('portrait_window.PortraitWindow.slot_names',return_value={0:'Synthetic'}):
                dialog=app.edit_portrait(0)
            self.assertIsNotNone(dialog);dialog.update()
            def descendants(w):
                for child in w.winfo_children():yield child;yield from descendants(child)
            labels=[w.cget('text') for w in descendants(dialog) if w.winfo_class()=='TButton']
            for text in ('Write Portrait to ROM','Save & Launch (F5)','Import PNG…','Undo slot','Preview packing…','Reserve space…'):self.assertIn(text,labels)
            for text in ('Animations…','Names & story…','Open ROM…'):self.assertNotIn(text,labels)
            self.assertEqual(len(dialog.talking),3);self.assertIsNotNone(dialog.animation_job)
            before=self.path.read_bytes();path=self.png(studio_sheet([[0]*128 for _ in range(32)]))
            with patch('portrait_window.filedialog.askopenfilename',return_value=str(path)):dialog.import_png()
            self.assertTrue(dialog.pending());self.assertEqual(self.path.read_bytes(),before)
            self.assertFalse(dialog.write.instate(['disabled']))
            for index,size in ((0,(64,64)),(1,(64,80))):
                dialog.layout.current(index);output=self.root/f'export-{index}.png'
                with patch('portrait_window.filedialog.asksaveasfilename',return_value=str(output)):dialog.export()
                self.assertEqual(struct.unpack('>II',output.read_bytes()[16:24]),size)
            dialog.undo();self.assertFalse(dialog.pending())
            with patch('portrait_window.filedialog.askopenfilename',return_value=str(path)):dialog.import_png()
            with patch('portrait_window.ask_unsaved',return_value=None):dialog.close()
            self.assertTrue(dialog.winfo_exists());self.assertTrue(dialog.pending())
            dialog.document.reserve(0x7c0000,0x7c8000)
            self.assertTrue(dialog.save());self.assertFalse(dialog.pending());self.assertNotEqual(self.path.read_bytes(),before)
            with patch.object(app,'save_and_launch',return_value=True) as launched:
                dialog.focus_force();dialog.update();dialog.event_generate('<F5>');dialog.update()
                launched.assert_called_once()
                # Direct command as well as binding routes to the host workflow.
                dialog.launch();self.assertEqual(launched.call_args.kwargs['save_callback'],dialog.save)
            job=dialog.animation_job;dialog.close();self.assertNotIn(job,app.tk.call('after','info'))
        finally:app.destroy()

    def test_save_and_launch_writes_staged_portraits_before_emulator_start(self):
        import sys
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        try:
            with patch('portrait_window.PortraitWindow.slot_names',return_value={}):dialog=app.edit_portrait(0)
            dialog.document.stage(0,[[0]*128 for _ in range(32)],decode_palette(self.palette))
            dialog.document.reserve(0x7c0000,0x7c8000)
            before=self.path.read_bytes()
            def check(config,path):
                self.assertNotEqual(Path(path).read_bytes(),before)
                self.assertEqual(PortraitDocument(Rom(path)).portraits[0].raw,bytes(2048))
                return Mock()
            config={'executable':sys.executable,'arguments':['{rom}']}
            with patch('emulator.load_config',return_value=config),patch('emulator.launch',side_effect=check) as launched:
                self.assertTrue(dialog.launch());launched.assert_called_once()
            self.assertFalse(dialog.pending());self.assertTrue(self.rom.history.can_undo)
            dialog.close()
        finally:app.destroy()

    def test_packing_preview_is_background_only_and_does_not_enable_optimization(self):
        import time
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        try:
            with patch('portrait_window.PortraitWindow.slot_names',return_value={}):dialog=app.edit_portrait(0)
            before=self.path.read_bytes()
            with patch('portrait_window.messagebox.showinfo') as notice:
                dialog.preview_packing()
                self.assertTrue(dialog.busy)
                self.assertFalse(dialog.save())
                deadline=time.monotonic()+10
                while dialog.busy and time.monotonic()<deadline:
                    app.update();time.sleep(.01)
                self.assertFalse(dialog.busy);notice.assert_called_once()
            self.assertFalse(dialog.optimize.get());self.assertFalse(dialog.pending())
            self.assertEqual(self.path.read_bytes(),before)
            dialog.close()
        finally:app.destroy()

    def test_unknown_loader_rejected_before_any_write(self):
        self.profile.stop()
        before=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'loader differs'):PortraitDocument(self.rom)
        self.assertEqual(self.path.read_bytes(),before)
        self.profile.start()


if __name__=='__main__':unittest.main()
