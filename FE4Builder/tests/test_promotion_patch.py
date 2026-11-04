"""ROM-free patch transactions, compatibility guards and desktop integration."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import unittest

from rom import Rom
from patch_window import save_patch
import promotion_patch as pp


def fixture(path, header=False, fill=0):
    data = bytearray(0x800000)
    data[0xFFC0:0xFFD5] = b'FIREEMBLEM4'.ljust(21, b' ')
    # Native reference instruction sequences; class records themselves remain
    # arbitrary editable data and are deliberately absent from the profile.
    addresses = (0x49B57, 0x49BB2, 0x49C0D, 0x49C68, 0x49CD4, 0x49D40)
    for index, at in enumerate(addresses, 1):
        data[at - 12:at] = bytes.fromhex('22 84 A0 84 22 ED 98 84 22') + (0x87A4F9 + index * 0x18).to_bytes(3, 'little')
        data[at:at + 15] = bytes([0x18, 0x7D, index, 0, 0x29, 0xFF, 0, 0xC9, 0x1F, 0, 0x90, 3, 0xA9, 0x1E, 0])
    data[0x1E95CE:0x1E95D7] = bytes.fromhex('BF 4C 96 9E A8 B7 24 F0 46')
    data[0x1E961D:0x1E962D] = bytes.fromhex('A9 00 00 8F CE 45 7F AF D3 45 7F 1A 8F D3 45 7F')
    data[pp.ARENA:pp.ARENA + pp.SIZE] = bytes([fill]) * pp.SIZE
    path.write_bytes((bytes(512) if header else b'') + data)
    return path


class PromotionPatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = fixture(Path(self.directory.name) / 'promotion.sfc')
        self.rom = Rom(self.path)
        self.before = bytes(self.rom.data)
        self.app = SimpleNamespace(rom=self.rom, refresh_after_history=lambda: None)

    def tearDown(self):
        self.directory.cleanup()

    def test_install_remove_only_changes_reserved_code_and_hooks(self):
        pp.install(self.rom)
        self.assertTrue(pp.installed(self.rom))
        self.assertEqual(len(self.rom.data), len(self.before))
        allowed = set(range(pp.ARENA, pp.ARENA + pp.SIZE))
        for at, (_, new) in pp.program()[1].items():
            allowed.update(range(at, at + len(new)))
        changed = {i for i, (old, new) in enumerate(zip(self.before, self.rom.data)) if old != new}
        self.assertLessEqual(changed, allowed)
        pp.uninstall(self.rom)
        self.assertEqual(bytes(self.rom.data), self.before)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_native_code_and_storage_conflicts_fail_before_mutation(self):
        addresses = list(pp.program()[1]) + [pp.HOOKS[0] - 12, 0x1E95CE, 0x1E961D, pp.ARENA + 100]
        for address in addresses:
            self.rom.data[:] = self.before
            self.rom.data[address] ^= 1
            before = bytes(self.rom.data)
            with self.assertRaises(ValueError, msg=hex(address)):
                pp.install(self.rom)
            self.assertEqual(bytes(self.rom.data), before)

    def test_duplicate_install_and_tampered_removal_are_atomic(self):
        pp.install(self.rom)
        baseline = bytes(self.rom.data)
        with self.assertRaises(ValueError):
            pp.install(self.rom)
        self.assertEqual(bytes(self.rom.data), baseline)
        for at in (pp.ARENA + pp.CODE_OFFSET, pp.HOOKS[1], pp.FLASH_HOOK):
            self.rom.data[:] = baseline
            self.rom.data[at] ^= 1
            before = bytes(self.rom.data)
            with self.assertRaises(ValueError):
                pp.uninstall(self.rom)
            self.assertEqual(bytes(self.rom.data), before)

    def test_headered_ff_storage_restores_exactly(self):
        path = fixture(Path(self.directory.name) / 'headered.smc', header=True, fill=255)
        rom = Rom(path)
        before = bytes(rom.data)
        pp.install(rom)
        self.assertEqual(rom.data[:512], bytes(512))
        pp.uninstall(rom)
        self.assertEqual(bytes(rom.data), before)
        self.rom.data[:] = self.rom.data[:0x400000]
        before = bytes(self.rom.data)
        with self.assertRaises(ValueError):
            pp.install(self.rom)
        self.assertEqual(bytes(self.rom.data), before)

    def test_save_backup_undo_redo_and_removal(self):
        save_patch(self.app, patch_name='promotion')
        installed = self.path.read_bytes()
        self.assertTrue(pp.installed(Rom(self.path)))
        self.assertEqual(self.rom.last_backup.read_bytes(), self.before)
        self.assertEqual(len(self.rom.history.state['entries']), 1)
        self.rom.undo()
        self.assertEqual(self.path.read_bytes(), self.before)
        self.rom.redo()
        self.assertEqual(self.path.read_bytes(), installed)
        save_patch(self.app, True, patch_name='promotion')
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_failed_disk_write_rolls_back_memory_and_preserves_file(self):
        with patch.object(self.rom, 'save_original', side_effect=OSError('write fixture')):
            with self.assertRaises(OSError):
                save_patch(self.app, patch_name='promotion')
        self.assertEqual(bytes(self.rom.data), self.before)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_patch_window_install_remove_and_save_failure(self):
        from FE4Builder import App
        from tkinter import ttk
        app = App()
        app.withdraw()
        app.rom = self.rom
        try:
            window = app.edit_patches()
            tabs = next(w for w in window.winfo_children() if isinstance(w, ttk.Notebook))
            self.assertEqual(tabs.tab(1, 'text'), 'Negative promotion stats')
            panel = window.nametowidget(tabs.tabs()[1])
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            buttons = {str(w['text']): w for w in descendants(panel) if isinstance(w, ttk.Button)}
            install, remove = buttons['Install: Negative promotion stats'], buttons['Remove patch']
            self.assertTrue(remove.instate(['disabled']))
            with (patch.object(self.rom, 'save_original', side_effect=OSError('write fixture')),
                  patch('patch_window.messagebox.showerror') as error):
                install.invoke()
                self.assertTrue(error.called)
            self.assertEqual(self.path.read_bytes(), self.before)
            self.assertEqual(bytes(self.rom.data), self.before)
            install.invoke()
            self.assertTrue(pp.installed(self.rom))
            self.assertTrue(install.instate(['disabled']))
            self.assertFalse(remove.instate(['disabled']))
            self.assertFalse(app.undo_button.instate(['disabled']))
            remove.invoke()
            self.assertEqual(self.path.read_bytes(), self.before)
            self.assertFalse(install.instate(['disabled']))
            window.destroy()
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()
