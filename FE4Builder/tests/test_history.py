import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom,character_modules
from history import patches,apply_entry,digest
from names import NameEditor

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path=Path(self.directory.name)/'history-test.sfc'
        self.path.write_bytes(next(ROOT.glob('*.sfc')).read_bytes())
        self.rom=Rom(self.path)
        self.module=character_modules()[0]

    def tearDown(self):
        self.directory.cleanup()

    def edit(self,value):
        values=self.rom.values(self.module,0)
        values[1]=value
        self.rom.write(self.module,0,values)
        self.rom.save_original('Character HP',[f'HP: {value}'])

    def test_backups_undo_redo_and_reopen(self):
        baseline=self.path.read_bytes()
        self.edit(51)
        self.assertEqual(self.rom.last_backup.read_bytes(),baseline)
        first=self.path.read_bytes()
        self.edit(52)
        self.assertEqual(self.rom.last_backup.read_bytes(),first)
        self.rom=Rom(self.path)
        self.assertEqual(self.rom.history.state['cursor'],2)
        self.rom.undo()
        self.assertEqual(self.path.read_bytes(),first)
        self.rom.undo()
        self.assertEqual(self.path.read_bytes(),baseline)
        self.rom.redo()
        self.assertEqual(self.path.read_bytes(),first)
        self.assertEqual(len(self.rom.history.state['audit']),5)

    def test_new_edit_after_undo_keeps_audit_and_drops_redo(self):
        self.edit(51)
        self.edit(52)
        self.rom.undo()
        self.edit(53)
        self.assertFalse(self.rom.history.can_redo)
        self.assertEqual(len(self.rom.history.state['audit']),4)
        self.rom.undo()
        self.assertEqual(self.rom.values(self.module,0)[1],51)

    def test_backup_failure_and_write_failure_preserve_disk_and_history(self):
        baseline=self.path.read_bytes()
        with patch.object(self.rom.history,'backup',side_effect=OSError('backup unavailable')):
            with self.assertRaises(OSError):
                self.edit(51)
        self.assertEqual(self.path.read_bytes(),baseline)
        self.assertFalse(self.rom.history.can_undo)
        with patch.object(self.rom,'_save',side_effect=OSError('write unavailable')):
            with self.assertRaises(OSError):
                self.rom.save_original('Failed edit')
        self.assertEqual(self.path.read_bytes(),baseline)
        self.assertFalse(Rom(self.path).history.can_undo)

    def test_undo_failure_and_external_change_are_atomic(self):
        self.edit(51)
        before=self.path.read_bytes()
        with patch.object(self.rom,'_save',side_effect=OSError('write unavailable')):
            with self.assertRaises(OSError):
                self.rom.undo()
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(bytes(self.rom.data),before)
        self.assertEqual(self.rom.history.state['cursor'],1)
        external=bytearray(before)
        external[-1]^=1
        self.path.write_bytes(external)
        with self.assertRaises(ValueError):
            self.rom.undo()
        self.assertEqual(self.path.read_bytes(),external)

    def test_pending_journal_recovery(self):
        self.edit(51)
        state=self.rom.history.state
        history=self.rom.history
        history.pending.write_text(history.file.read_text(),encoding='utf-8')
        history.file.unlink()
        reopened=Rom(self.path)
        self.assertEqual(reopened.history.state,state)
        reopened.undo()

    def test_restoration_is_undoable_and_noop_has_no_backup(self):
        self.rom.save_original()
        self.assertFalse(self.rom.history.folder.exists())
        baseline=self.path.read_bytes()
        self.edit(51)
        backup=self.rom.last_backup
        edited=self.path.read_bytes()
        self.rom.restore_backup(backup)
        self.assertEqual(self.path.read_bytes(),baseline)
        self.rom.undo()
        self.assertEqual(self.path.read_bytes(),edited)

    def test_names_are_one_undoable_action(self):
        before=self.path.read_bytes()
        model=NameEditor(self.rom,0)
        model.write('Lex',allow_expand=True)
        self.rom.save_original('Rename character')
        after=self.path.read_bytes()
        self.assertNotEqual(before,after)
        self.rom.undo()
        self.assertEqual(self.path.read_bytes(),before)
        self.rom.redo()
        self.assertEqual(self.path.read_bytes(),after)

    def test_sparse_patches_cover_file_size_changes(self):
        for before,after in [(b'abcd',b'aXcdmore'),(b'abcdmore',b'aXcd')]:
            entry={'before_hash':digest(before),'after_hash':digest(after),
                   'before_size':len(before),'after_size':len(after),'patches':patches(before,after)}
            self.assertEqual(apply_entry(before,entry,True),after)
            self.assertEqual(apply_entry(after,entry,False),before)

    def test_invalid_history_does_not_prevent_opening(self):
        self.edit(51)
        self.rom.history.file.write_text('[1,2,3]',encoding='utf-8')
        reopened=Rom(self.path)
        self.assertFalse(reopened.history.can_undo)
        self.assertTrue(reopened.history.notice)
        self.assertTrue(self.rom.last_backup.exists())

    def test_modified_backup_is_not_restored(self):
        self.edit(51)
        before=self.path.read_bytes()
        backup=self.rom.last_backup
        tampered=bytearray(backup.read_bytes())
        tampered[-1]^=1
        backup.write_bytes(tampered)
        with self.assertRaises(ValueError):
            self.rom.restore_backup(backup)
        self.assertEqual(self.path.read_bytes(),before)

    def test_overwritten_export_is_backed_up(self):
        target=self.path.parent/'export.sfc'
        target.write_bytes(b'previous export')
        self.rom.save_copy(target)
        self.assertEqual(self.rom.last_backup.read_bytes(),b'previous export')
        self.assertEqual(target.read_bytes(),self.rom.data)

    def test_editor_buttons_and_history_screen(self):
        from FE4Builder import App
        from test_name_ui import descendants
        app=App()
        app.withdraw()
        try:
            app.rom=self.rom
            app.show_editor('Character Editor')
            original=self.rom.values(self.module,0)[1]
            app.editors[1][0].set('51')
            self.assertTrue(app.write_original())
            self.assertTrue(self.rom.history.can_undo)
            self.assertIn('Base HP',self.rom.history.state['entries'][0]['details'][0])
            app.history_step(False)
            self.assertEqual(self.rom.values(self.module,0)[1],original)
            app.history_step(True)
            self.assertEqual(self.rom.values(self.module,0)[1],51)
            app.show_history()
            dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
            app.update_idletasks()
            tree=next(w for w in descendants(dialog) if w.winfo_class()=='Treeview')
            self.assertEqual(len(tree.get_children()),3)
            restore=next(w for w in descendants(dialog) if w.winfo_class()=='TButton' and w.cget('text')=='Restore selected backup')
            with patch('history_window.messagebox.askyesno',return_value=True):
                restore.invoke()
            self.assertEqual(self.rom.values(self.module,0)[1],original)
            app.history_step(False)
            self.assertEqual(self.rom.values(self.module,0)[1],51)
            dialog.destroy()
        finally:
            app.destroy()

if __name__=='__main__':
    unittest.main()
