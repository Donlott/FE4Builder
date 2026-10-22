from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from rom import ROOT,Rom
from intro_graphics import IntroAsset,assets,ARENA,ARENA_SIZE,pc_address
from portraits import png_bytes


class IntroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=next(ROOT.glob('*.sfc'))
        cls.original=cls.source.read_bytes()
        cls.root=tk.Tk();cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):cls.root.destroy()

    def model(self,rom,key):return IntroAsset(rom,next(e for e in assets() if e['key']==key))

    def test_every_resource_export_reimport_is_lossless(self):
        rom=Rom(self.source)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'sheet.png'
            for entry in assets():
                with self.subTest(resource=entry['key']):
                    model=IntroAsset(rom,entry);index=entry.get('default_palette',0)
                    path.write_bytes(model.png(index));model.import_png(self.root,path,index)
                    self.assertFalse(model.dirty)
            self.assertEqual(bytes(rom.data),self.original)

    def test_caption_save_reopen_backup_undo_redo_and_reuse(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'intro.sfc';path.write_bytes(self.original);rom=Rom(path)
            model=self.model(rom,'caption1');model.text('A new story begins...')
            expected=model.raw;details=model.apply();rom.save_original('Caption test',details)
            saved=path.read_bytes();reloaded=self.model(Rom(path),'caption1')
            self.assertEqual(reloaded.raw,expected)
            self.assertTrue(ARENA<=pc_address(reloaded.pointer)<ARENA+ARENA_SIZE)
            self.assertEqual(len(saved),len(self.original))
            self.assertEqual(rom.last_backup.read_bytes(),self.original)
            self.assertEqual(saved[0x7a0000:],self.original[0x7a0000:])
            rom.undo();self.assertEqual(path.read_bytes(),self.original)
            rom.redo();self.assertEqual(path.read_bytes(),saved)
            model=self.model(rom,'caption1');oldpointer=model.pointer
            model.text('');model.apply()
            self.assertEqual(self.model(rom,'caption1').pointer,oldpointer)
            self.assertEqual(self.source.read_bytes(),self.original)

    def test_caption_rejects_overlong_or_unsupported_text_without_changes(self):
        model=self.model(Rom(self.source),'caption2')
        for text in ('W'*100,'\u2603'):
            with self.assertRaises(ValueError):model.text(text)
            self.assertFalse(model.dirty)

    def test_screen_rebuild_preserves_image_and_title_clouds(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'replace.png'
            for key in ('nintendo','title','art1','art3','art12'):
                with self.subTest(resource=key):
                    rom=Rom(self.source);model=self.model(rom,key)
                    rows,colors=model.rows();rows=[row[:] for row in rows]
                    if key=='nintendo':rows=[[0]*256 for _ in rows]
                    # Add a single tile-sized block in the first cell's existing palette.
                    old=rows[0][0];value=(old//16)*16+1
                    for y in range(8):
                        for x in range(8):rows[y][x]=value
                    path.write_bytes(png_bytes(rows,colors))
                    model.import_png(self.root,path);self.assertTrue(model.dirty)
                    if key=='title':self.assertEqual(model.raw[16384:],model.original[16384:])
                    visual=model.screen();model.apply()
                    self.assertEqual(self.model(rom,key).screen(),visual)
                    # Retiling preserves every other visible pixel, including flips/palettes.
                    actual=model.screen()
                    for y in range(8,len(rows)):self.assertEqual([colors[v] for v in actual[y]],[colors[v] for v in rows[y]])

    def test_occupied_storage_and_stale_source_roll_back(self):
        rom=Rom(self.source);rom.data[ARENA]=7
        model=self.model(rom,'caption1');model.text('Changed caption');before=bytes(rom.data)
        with self.assertRaisesRegex(ValueError,'occupied'):model.apply()
        self.assertEqual(bytes(rom.data),before)
        rom=Rom(self.source);first=self.model(rom,'caption1');second=self.model(rom,'caption1')
        first.text('First');first.apply();before=bytes(rom.data);second.text('Second')
        with self.assertRaisesRegex(ValueError,'changed'):second.apply()
        self.assertEqual(bytes(rom.data),before)

    def test_copier_header_and_invalid_loader(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'headered.smc';header=bytes([37])*512;path.write_bytes(header+self.original)
            rom=Rom(path);model=self.model(rom,'caption1');model.text('Header test');model.apply()
            self.assertEqual(bytes(rom.data[:512]),header)
            self.assertEqual(self.model(rom,'caption1').raw,model.raw)
            e=next(e for e in assets() if e['key']=='nintendo');rom.data[e['refs'][0]['low']+rom.header-1]=0
            with self.assertRaisesRegex(ValueError,'instructions'):IntroAsset(rom,e)

    def test_logo_aliases_and_palette_import(self):
        rom=Rom(self.source);model=self.model(rom,'title_english')
        model.raw=bytes([model.raw[0]^1])+model.raw[1:];model.apply()
        self.assertEqual(self.model(rom,'title_english').raw,model.raw)
        # Both the immediate loader and scene-table reference must be repointed.
        from intro_graphics import pointer
        values=[pointer(rom,[ref]) for ref in model.entry['refs']]
        self.assertEqual(len(set(values)),1)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            for key in ('title_palette','nintendo_palette'):
                palette=self.model(rom,key);rows,colors=palette.rows()
                target=1 if key=='nintendo_palette' else 0
                colors[target]=(255,0,255)
                path=Path(folder)/'palette.png';path.write_bytes(png_bytes(rows,colors))
                palette.import_png(self.root,path);self.assertTrue(palette.dirty)
                self.assertEqual(palette.raw[2:],palette.original[2:])
                palette.apply();self.assertEqual(self.model(rom,key).raw,palette.raw)

    def test_readable_logo_pixel_edits_restore_correct_native_tiles(self):
        from logo_layout import projection
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'logo.png'
            for key in ('title_english','title_logo'):
                model=self.model(Rom(self.source),key);original=model.raw
                projected,owners,_,_=projection(original,key,model.rom)
                rows,colors=model.rows()
                x,y=next((x,y) for (x,y),owner in owners.items() if projected[y][x])
                tile,dx,dy,pal=owners[x,y]
                value=next(pal*16+i for i in range(1,16) if colors[pal*16+i]!=colors[rows[y][x]])
                rows[y][x]=value
                from portraits import export_png
                path.write_bytes(export_png(rows,colors));model.import_png(self.root,path)
                start=tile*32;self.assertNotEqual(model.raw[start:start+32],original[start:start+32])
                self.assertEqual(model.raw[:start],original[:start]);self.assertEqual(model.raw[start+32:],original[start+32:])
                model.apply();self.assertEqual(self.model(model.rom,key).raw,model.raw)
                # Raw exports remain available and lossless too.
                fresh=self.model(model.rom,key);path.write_bytes(fresh.png(3,False));fresh.import_png(self.root,path,3,False)
                self.assertFalse(fresh.dirty)

    def test_logo_gap_paint_is_rejected_atomically(self):
        model=self.model(Rom(self.source),'title_logo');rows,colors=model.rows()
        rows[0][0]=163
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'bad.png';path.write_bytes(png_bytes(rows,colors))
            with self.assertRaisesRegex(ValueError,'gap'):model.import_png(self.root,path)
            self.assertFalse(model.dirty)

    def test_rgba_logo_erasure_with_unchanged_rgb_is_applied(self):
        import struct,zlib
        model=self.model(Rom(self.source),'title_english');rows,colors=model.rows()
        x,y=next((x,y) for y,line in enumerate(rows) for x,value in enumerate(line) if value)
        def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        body=b''.join(b'\0'+b''.join(bytes(colors[value])+bytes([0 if (sx,sy)==(x,y) or value==0 else 255]) for sx,value in enumerate(line)) for sy,line in enumerate(rows))
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',len(rows[0]),len(rows),8,6,0,0,0))+chunk(b'IDAT',zlib.compress(body))+chunk(b'IEND',b'')
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'erase.png';path.write_bytes(png);model.import_png(self.root,path)
        self.assertTrue(model.dirty)
        self.assertEqual(model.rows()[0][y][x],0)

    def test_shared_native_logo_pixels_propagate_and_conflicts_abort(self):
        from logo_layout import projection
        from collections import defaultdict
        from portraits import export_png
        model=self.model(Rom(self.source),'title_english');rows,colors=model.rows()
        _,owners,_,_=projection(model.raw,model.key,model.rom);copies=defaultdict(list)
        for at,(tile,dx,dy,pal) in owners.items():
            x,y=at
            if rows[y][x]:copies[tile,dx,dy,pal].append(at)
        identity,positions=next((key,value) for key,value in copies.items() if len(value)>1)
        pal=identity[3];x,y=positions[0];old=rows[y][x]
        values=[];seen={colors[old]}
        for i in range(1,16):
            value=pal*16+i
            if colors[value] not in seen:values.append(value);seen.add(colors[value])
        self.assertGreaterEqual(len(values),2)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'shared.png';rows[y][x]=values[0];path.write_bytes(export_png(rows,colors));model.import_png(self.root,path)
            changed=model.rows()[0]
            for sx,sy in positions:self.assertEqual(changed[sy][sx]%16,values[0]%16)
            model=self.model(Rom(self.source),'title_english');rows,colors=model.rows()
            for (sx,sy),value in zip(positions[:2],values[:2]):rows[sy][sx]=value
            path.write_bytes(export_png(rows,colors))
            with self.assertRaisesRegex(ValueError,'disagree'):model.import_png(self.root,path)
            self.assertFalse(model.dirty)

    def test_erasing_overlapped_sprite_pixels_does_not_reveal_old_art(self):
        from logo_layout import projection
        from intro_graphics import decode_tiles
        from portraits import export_png
        model=self.model(Rom(self.source),'title_logo');rows,colors=model.rows();sheet=decode_tiles(model.raw)
        _,_,layers,_=projection(model.raw,model.key,model.rom)
        at=next(at for at,items in layers.items() if sum(bool(sheet[t//16*8+dy][t%16*8+dx]) for t,dx,dy,p in items)>1)
        x,y=at;rows[y][x]=0
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'erase.png';path.write_bytes(export_png(rows,colors));model.import_png(self.root,path)
        self.assertEqual(model.rows()[0][y][x],0)

    def test_window_caption_write_and_launch(self):
        from FE4Builder import App
        from intro_window import IntroWindow
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'gui.sfc';path.write_bytes(self.original)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                window=IntroWindow(app);window.withdraw()
                i=next(i for i,e in enumerate(window.entries) if e['key']=='caption1')
                window.list.selection_clear(0,'end');window.list.selection_set(i);window.select()
                window.text.set('GUI caption');window.caption_text();self.assertTrue(window.model.dirty)
                self.assertTrue(window.save());self.assertFalse(window.model.dirty)
                self.assertEqual(self.model(Rom(path),'caption1').raw,window.model.raw)
                with patch.object(app,'save_and_launch',return_value=True) as launch:
                    self.assertTrue(window.launch());self.assertEqual(launch.call_args.kwargs['parent'],window)
                for key in ('title_english','title_logo'):
                    i=next(i for i,e in enumerate(window.entries) if e['key']==key)
                    window.list.selection_clear(0,'end');window.list.selection_set(i);window.select()
                    self.assertEqual(window.layout.current(),0)
                    self.assertTrue(window.palette.instate(['disabled']))
                    self.assertEqual(window.photo.width(),512)
                    window.layout.current(1);window.display()
                    self.assertEqual(window.photo.width(),256)
                    self.assertTrue(window.palette.instate(['readonly']))
                    self.assertFalse(window.model.dirty)
                window.destroy()
            finally:app.destroy()
