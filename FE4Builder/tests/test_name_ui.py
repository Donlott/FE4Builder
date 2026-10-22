import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from FE4Builder import App
from rom import ROOT,Rom
from names import NameEditor
from test_names import prepare_name_fixture

def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

class NameWarningTest(unittest.TestCase):
    def test_decline_and_accept_wider_name(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'test.sfc'
            path.write_bytes(next(ROOT.glob('*.sfc')).read_bytes())
            fixture=Rom(path)
            prepare_name_fixture(fixture)
            path.write_bytes(fixture.data)
            app=App()
            app.withdraw()
            try:
                app.rom=Rom(path)
                app.edit_name(0)
                app.update_idletasks()
                dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
                entry=next(w for w in descendants(dialog) if w.winfo_class()=='TEntry')
                write=next(w for w in descendants(dialog) if w.winfo_class()=='TButton' and w.cget('text')=='Write to ROM')
                entry.delete(0,'end')
                entry.insert(0,'Beowulf')
                app.update_idletasks()
                self.assertFalse(write.instate(['disabled']))
                before=path.read_bytes()
                with patch('name_window.messagebox.askyesno',return_value=False) as warning:
                    write.invoke()
                    self.assertIn('Expand name space',warning.call_args.args[0])
                self.assertEqual(path.read_bytes(),before)
                with patch('name_window.messagebox.askyesno',return_value=True):
                    write.invoke()
                self.assertEqual(NameEditor(Rom(path),0).current,'Beowulf')
                self.assertEqual(len(path.read_bytes()),len(before))
                dialog.destroy()
            finally:
                app.destroy()

if __name__=='__main__':
    unittest.main()
