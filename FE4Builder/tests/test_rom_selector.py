import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT
import rom_selector
from FE4Builder import App


class RomSelectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.folder=Path(self.temp.name)
        self.settings=self.folder/'rom-selector.json'
        self.mock=patch.object(rom_selector,'SETTINGS',self.settings);self.mock.start()

    def tearDown(self):self.mock.stop();self.temp.cleanup()

    def test_startup_success_relaunch_and_remembered_browse_location(self):
        path=next(ROOT.glob('*.sfc'));before=path.read_bytes()
        app=App();app.withdraw();app.update_idletasks()
        try:
            self.assertEqual(app.rom_selector.winfo_manager(),'pack')
            self.assertFalse(app.home.winfo_manager())
            self.assertIsNone(app.rom)
            with patch('FE4Builder.filedialog.askopenfilename',return_value=str(path)):
                self.assertTrue(app.open_rom())
            self.assertFalse(app.rom_selector.winfo_manager())
            self.assertEqual(app.home.winfo_manager(),'pack')
            self.assertEqual(rom_selector.last_rom(),str(path.resolve()))
        finally:app.destroy()
        app=App();app.withdraw();app.update_idletasks()
        try:
            self.assertIsNone(app.rom)
            self.assertEqual(app.last_rom_path,str(path.resolve()))
            self.assertEqual(app.rom_selector.winfo_manager(),'pack')
            with patch('FE4Builder.filedialog.askopenfilename',return_value='') as browse:
                app.open_rom()
            self.assertEqual(Path(browse.call_args.kwargs['initialdir']),path.parent)
            self.assertIsNone(app.rom)
            self.assertTrue(app.rom_selector.winfo_manager())
            self.assertEqual(rom_selector.last_rom(),str(path.resolve()))
        finally:app.destroy()
        self.assertEqual(path.read_bytes(),before)

    def test_missing_last_file_failed_open_and_corrupt_settings(self):
        missing=self.folder/'missing.sfc';rom_selector.remember(missing)
        app=App();app.withdraw();app.update_idletasks()
        try:
            with patch('FE4Builder.messagebox.showerror') as error:
                app.open_rom(app.last_rom_path)
            error.assert_called_once()
            self.assertIsNone(app.rom)
            self.assertTrue(app.rom_selector.winfo_manager())
            self.assertEqual(rom_selector.initial_directory(str(missing)),self.folder)
        finally:app.destroy()
        for invalid in ('not json','[]','{"last_rom":7}','{"last_rom":"\\u0000"}'):
            self.settings.write_text(invalid)
            self.assertEqual(rom_selector.last_rom(),'')

    def test_preferences_write_failure_does_not_block_open(self):
        app=App();app.withdraw();app.update_idletasks()
        try:
            with patch('rom_selector.remember',side_effect=OSError('Read only')):
                self.assertTrue(app.open_rom(str(next(ROOT.glob('*.sfc')))))
            self.assertIn('could not be remembered',app.status.get())
            self.assertEqual(app.home.winfo_manager(),'pack')
        finally:app.destroy()
