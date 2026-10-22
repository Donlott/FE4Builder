import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from rom import ROOT,Rom
import growth_patch as gp
from patch_window import save_patch


class GrowthPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path=Path(self.temp.name)/'growth-test.sfc'
        self.baseline=next(ROOT.glob('*.sfc')).read_bytes()
        self.path.write_bytes(self.baseline)
        self.rom=Rom(self.path)
        self.app=SimpleNamespace(rom=self.rom,refresh_after_history=lambda:None)

    def tearDown(self):self.temp.cleanup()

    def test_install_save_backup_history_remove(self):
        save_patch(self.app)
        self.assertTrue(gp.installed(Rom(self.path)))
        self.assertEqual(len(self.rom.data),len(self.baseline))
        self.assertEqual(self.rom.last_backup.read_bytes(),self.baseline)
        installed=self.path.read_bytes()
        self.rom.undo();self.assertEqual(self.path.read_bytes(),self.baseline)
        self.rom.redo();self.assertEqual(self.path.read_bytes(),installed)
        save_patch(self.app,True)
        self.assertEqual(self.path.read_bytes(),self.baseline)

    def test_conflicts_are_atomic(self):
        for address in (0x98111,0x99510,gp.ARENA+100):
            self.rom.data[:]=self.baseline
            self.rom.data[address]^=1
            before=bytes(self.rom.data)
            with self.assertRaises(ValueError):gp.install(self.rom)
            self.assertEqual(bytes(self.rom.data),before)
        self.assertEqual(self.path.read_bytes(),self.baseline)

    def test_double_install_and_tampered_removal(self):
        gp.install(self.rom)
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):gp.install(self.rom)
        self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[gp.ARENA+0x110]^=1
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):gp.uninstall(self.rom)
        self.assertEqual(bytes(self.rom.data),before)

    def test_save_failure_rolls_back_memory_and_disk(self):
        with patch.object(self.rom,'save_original',side_effect=OSError('Cannot save')):
            with self.assertRaises(OSError):save_patch(self.app)
        self.assertEqual(bytes(self.rom.data),self.baseline)
        self.assertEqual(self.path.read_bytes(),self.baseline)

    def test_copier_header_and_ff_storage_restore(self):
        data=bytearray(self.baseline)
        data[gp.ARENA:gp.ARENA+gp.SIZE]=b'\xff'*gp.SIZE
        baseline=b'\x00'*512+data
        self.path.write_bytes(baseline)
        rom=Rom(self.path)
        self.assertEqual(rom.header,512)
        gp.install(rom);gp.uninstall(rom)
        self.assertEqual(bytes(rom.data),baseline)

    def legacy_patch(self):
        block=(Path(__file__).parent/'fixtures'/'growth-v1.bin').read_bytes()
        self.rom.data[gp.ARENA:gp.ARENA+gp.SIZE]=block
        for address,(_,hook) in gp.program()[1].items():
            self.rom.data[address:address+len(hook)]=hook
        self.assertEqual(gp.version(self.rom),1)

    def test_upgrade_is_one_undoable_edit_and_remains_removable(self):
        self.legacy_patch()
        self.rom.save_original('Install legacy patch')
        legacy=self.path.read_bytes()
        save_patch(self.app)
        self.assertEqual(gp.version(Rom(self.path)),2)
        self.assertEqual(self.rom.last_backup.read_bytes(),legacy)
        self.rom.undo();self.assertEqual(self.path.read_bytes(),legacy)
        self.rom.redo();self.assertEqual(gp.version(self.rom),2)
        save_patch(self.app,True);self.assertEqual(self.path.read_bytes(),self.baseline)

    def test_failed_upgrade_preserves_legacy_patch(self):
        self.legacy_patch()
        self.rom.data[0x99510]^=1
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):gp.install(self.rom)
        self.assertEqual(bytes(self.rom.data),before)
        self.rom.data[0x99510]^=1
        before=bytes(self.rom.data)
        with patch.object(self.rom,'save_original',side_effect=OSError('Cannot save')):
            with self.assertRaises(OSError):save_patch(self.app)
        self.assertEqual(bytes(self.rom.data),before)

    def test_legacy_removal_and_corrupt_upgrade(self):
        self.legacy_patch();gp.uninstall(self.rom)
        self.assertEqual(bytes(self.rom.data),self.baseline)
        self.legacy_patch();self.rom.data[gp.ARENA+0x300]^=1
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):gp.install(self.rom)
        self.assertEqual(bytes(self.rom.data),before)

    def test_window_controls(self):
        from FE4Builder import App
        app=App();app.withdraw();app.rom=self.rom
        try:
            app.update_idletasks()
            window=app.edit_patches()
            labels=[]
            def visit(widget):
                for child in widget.winfo_children():
                    if child.winfo_class()=='TButton':labels.append(child.cget('text'))
                    visit(child)
            visit(window)
            self.assertIn('Install: Display growth rates',labels)
            self.assertIn('Remove patch',labels)
            window.destroy()
            self.legacy_patch()
            window=app.edit_patches();labels.clear();visit(window)
            self.assertIn('Update: Display growth rates',labels)
            window.destroy()
        finally:app.destroy()
