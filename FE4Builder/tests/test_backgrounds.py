import tempfile,unittest
from pathlib import Path
from copy import copy
from unittest.mock import patch
from rom import ROOT,Rom
from backgrounds import Background,ARENA,SLOT_SIZE,TABLE
from intro_graphics import encode_tile

class BackgroundTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))
    def test_six_images_noop_roundtrip_and_single_background_storage(self):
        import tkinter as tk
        root=tk.Tk();root.withdraw();original=bytes(self.rom.data)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
                for index in range(6):
                    model=Background(self.rom,index);rows=model.screen()
                    self.assertEqual((len(rows[0]),len(rows)),(256,88))
                    path=Path(folder)/f'{index}.png';path.write_bytes(model.png());model.import_png(root,path)
                    self.assertFalse(model.dirty);self.assertEqual(model.apply(),[])
            model=Background(self.rom,3)
            model.raw=encode_tile([[1]*8 for _ in range(8)])+model.raw[32:]
            self.assertTrue(model.apply());self.assertEqual(Background(self.rom,3).raw,model.raw)
            self.assertEqual(len(self.rom.data),len(original))
            lo=ARENA+3*SLOT_SIZE;hi=lo+SLOT_SIZE;at=TABLE+9
            self.assertEqual(self.rom.data[:at],original[:at]);self.assertEqual(self.rom.data[at+3:lo],original[at+3:lo]);self.assertEqual(self.rom.data[hi:],original[hi:])
            for i in (0,1,2,4,5):
                other=Background(self.rom,i);self.assertFalse(other.dirty)
            headered=copy(self.rom);headered.header=512;headered.data=bytearray(512)+self.rom.data
            self.assertEqual(Background(headered,3).screen(),model.screen())
        finally:root.destroy()
    def test_occupied_stale_modified_storage_and_loader_rejected(self):
        original=bytes(self.rom.data)
        self.rom.data[ARENA+10]=17
        model=Background(self.rom,0);model.raw=encode_tile([[1]*8 for _ in range(8)])+model.raw[32:]
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.apply()
        self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[:]=original;model=Background(self.rom,0);model.raw=encode_tile([[1]*8 for _ in range(8)])+model.raw[32:]
        self.rom.data[model.descriptor_address+6]^=1
        with self.assertRaises(ValueError):model.apply()
        self.rom.data[:]=original;model=Background(self.rom,0);model.raw=encode_tile([[1]*8 for _ in range(8)])+model.raw[32:];model.apply()
        self.rom.data[ARENA+256]^=1
        with self.assertRaises(ValueError):Background(self.rom,0)
        self.rom.data[:]=original;self.rom.data[0xabb3e]^=1
        with self.assertRaises(ValueError):Background(self.rom,0)
    def test_png_import_draft_save_failure_backup_undo_and_event_link(self):
        from FE4Builder import App
        import tkinter as tk
        from event_commands import catalogue
        original=bytes(self.rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            folder=Path(folder);path=folder/'background.sfc';path.write_bytes(original)
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                self.assertTrue(any(t[1]=='Background Editor' for t in app.home_tools))
                w=app.edit_background(3);self.assertEqual(w.current,3)
                file=folder/'edit.png';file.write_bytes(w.model.png());image=tk.PhotoImage(master=w,file=str(file))
                old=image.get(128,44);cell=(44//8*32+128//8)*2;pal=(int.from_bytes(w.model.map[cell:cell+2],'little')>>10)&7
                rgb=next(c for c in w.model.palette[pal*16:pal*16+16] if c!=old)
                image.put('#%02x%02x%02x'%rgb,(128,44));image.write(str(file),format='png')
                w.model.import_png(w,file);self.assertTrue(w.pending());self.assertEqual(path.read_bytes(),original)
                with patch.object(app.rom,'save_original',side_effect=OSError('test failure')),patch('background_window.messagebox.showerror'):
                    self.assertFalse(w.save());self.assertEqual(bytes(app.rom.data),original);self.assertTrue(w.pending())
                self.assertTrue(w.save());self.assertFalse(w.pending());self.assertEqual(app.rom.last_backup.read_bytes(),original)
                changed=path.read_bytes();self.assertNotEqual(changed,original)
                w.history(False);self.assertEqual(path.read_bytes(),original)
                w.history(True);self.assertEqual(path.read_bytes(),changed);w.destroy()
                e=next(e for e in catalogue()['entries'] if any(c['opcode']==0x14 for c in e['commands']))
                event=app.edit_events(e['id']);command=next(i for i,c in enumerate(event.model.commands) if c['opcode']==0x14)
                event.commands.selection_set(str(command));event.select_command()
                with patch.object(app,'edit_background',return_value=None) as opened:
                    event.open_background();opened.assert_called_once_with(event.model.values(command)[1])
                event.destroy()
            finally:app.destroy()
