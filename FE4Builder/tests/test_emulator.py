import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
from rom import ROOT,Rom,character_modules
import emulator

class EmulatorTests(unittest.TestCase):
    def setUp(self):self.source=next(ROOT.glob('*.sfc'))

    def test_settings_roundtrip_and_argument_boundaries(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            folder=Path(folder);exe=folder/'emulator with spaces.exe';exe.write_bytes(b'fake')
            rom=folder/'edited ROM & [test].sfc';rom.write_bytes(b'test')
            config={'executable':str(exe),'arguments':['--example','{rom}']}
            settings=folder/'emulator.json'
            emulator.save_config(config,settings)
            loaded=emulator.load_config(settings)
            argv=emulator.command(loaded,rom)
            self.assertEqual(argv,[str(exe.resolve()),'--example',str(rom.resolve())])
            self.assertEqual(emulator.command({'executable':str(exe),'arguments':[]},rom)[-1],str(rom.resolve()))
            with patch('emulator.subprocess.Popen') as popen:
                emulator.launch(loaded,rom)
                popen.assert_called_once_with(argv,cwd=str(folder.resolve()),shell=False)
            settings.write_text('{bad json',encoding='utf-8')
            with self.assertRaises(ValueError):emulator.load_config(settings)

    def test_real_child_process_receives_literal_rom_path(self):
        # Test spawning with a harmless CLI stand-in, never a user's emulator.
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            folder=Path(folder).resolve();rom=folder/'edited ROM & [test].sfc';rom.write_bytes(b'freshly saved')
            capture=folder/'received.json';script=folder/'fake emulator.py'
            script.write_text('import sys,json,hashlib\nfrom pathlib import Path\nPath(sys.argv[2]).write_text(json.dumps({"rom":sys.argv[1],"hash":hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()}))\n',encoding='utf-8')
            process=emulator.launch({'executable':sys.executable,'arguments':[str(script),'{rom}',str(capture)]},rom)
            self.assertEqual(process.wait(timeout=10),0)
            result=json.loads(capture.read_text())
            self.assertEqual(result['rom'],str(rom))
            self.assertEqual(result['hash'],hashlib.sha256(b'freshly saved').hexdigest())

    def test_save_launch_uses_saved_bytes_and_creates_backup(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            folder=Path(folder);path=folder/'edited ROM.sfc';path.write_bytes(self.source.read_bytes())
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                app.show_editor('Character Editor')
                field=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Base HP')
                before=path.read_bytes();value=(app.rom.values(app.modules[0],0)[field]+1)%255
                app.editors[field][0].set(str(value))
                config={'executable':sys.executable,'arguments':['{rom}']}
                def launched(config,rom):
                    self.assertEqual(Rom(rom).values(character_modules()[0],0)[field],value)
                    return Mock()
                with patch('emulator.load_config',return_value=config),patch('emulator.launch',side_effect=launched) as launch:
                    self.assertTrue(app.save_and_launch());launch.assert_called_once()
                self.assertEqual(app.rom.last_backup.read_bytes(),before)
                self.assertTrue(app.rom.history.can_undo)
            finally:app.destroy()

    def test_invalid_fields_and_cancelled_settings_do_not_save_or_launch(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'edited.sfc';path.write_bytes(self.source.read_bytes())
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                app.show_editor('Character Editor');before=path.read_bytes()
                field=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Base HP')
                app.editors[field][0].set('256')
                with patch('emulator.load_config',return_value={'executable':sys.executable,'arguments':['{rom}']}),patch('emulator.launch') as launch,patch('FE4Builder.messagebox.showerror'):
                    self.assertFalse(app.save_and_launch());launch.assert_not_called()
                self.assertEqual(path.read_bytes(),before)
                with patch('emulator.load_config',return_value={'executable':'missing-emulator.exe','arguments':[]}),patch.object(app,'configure_emulator',return_value=None),patch('emulator.launch') as launch:
                    self.assertFalse(app.save_and_launch());launch.assert_not_called()
                self.assertEqual(path.read_bytes(),before)
            finally:app.destroy()

    def test_popup_save_failure_and_process_failure(self):
        from FE4Builder import App
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'edited.sfc';path.write_bytes(self.source.read_bytes())
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                app.show_editor('Character Editor')
                with patch('emulator.load_config',return_value={'executable':sys.executable,'arguments':[]}),patch('emulator.launch') as launch:
                    self.assertFalse(app.save_and_launch(save_callback=lambda:False));launch.assert_not_called()
                field=next(i for i,f in enumerate(app.modules[0].fields) if f.name=='Base HP')
                value=(app.rom.values(app.modules[0],0)[field]+1)%255;app.editors[field][0].set(str(value))
                with patch('emulator.load_config',return_value={'executable':sys.executable,'arguments':[]}),patch('emulator.launch',side_effect=OSError('test failure')),patch('FE4Builder.messagebox.showerror'):
                    self.assertFalse(app.save_and_launch())
                self.assertEqual(Rom(path).values(character_modules()[0],0)[field],value)
                self.assertIn('ROM saved',app.status.get())
            finally:app.destroy()

    def test_map_launch_saves_staged_tiles(self):
        from FE4Builder import App
        from map_window import MapEditorWindow
        from chapter_maps import ChapterMap
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'map.sfc';path.write_bytes(self.source.read_bytes())
            app=App();app.withdraw();app.rom=Rom(path)
            try:
                window=MapEditorWindow(app,0);window.model.paint(5,5,123)
                with patch('emulator.load_config',return_value={'executable':sys.executable,'arguments':[]}),patch('emulator.launch') as launch:
                    self.assertTrue(window.save_and_launch());launch.assert_called_once()
                self.assertEqual(ChapterMap(Rom(path),0).map[5*64+5]&1023,123)
                window.destroy()
            finally:app.destroy()

if __name__=='__main__':unittest.main()
