import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from collections import defaultdict
from rom import ROOT,Rom
from dialogue import Dialogue,catalogue,encode,decode,preview
from dialogue_storage import REGIONS,pool


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        self.entries=catalogue()['entries']
        self.entry=next(e for e in self.entries if e['group']=='Prologue' and e['label']=='Intro1')

    def test_every_catalogued_scene_roundtrips_losslessly(self):
        self.assertEqual(len(self.entries),1624)
        self.assertEqual(len({e['address'] for e in self.entries}),1624)
        for entry in self.entries:
            model=Dialogue(self.rom,entry)
            self.assertEqual(encode(model.text),model.raw,entry['label'])
        original=bytes(self.rom.data)
        model=Dialogue(self.rom,self.entry)
        self.assertFalse(model.write(model.text))
        self.assertEqual(bytes(self.rom.data),original)

    def test_commands_arguments_end_and_invalid_input(self):
        text='[Start][Portrait 0001]Hello!\n[PauseText 01][SetSide 01][Wait][End]'
        raw=encode(text);self.assertEqual(decode(raw)[0],text)
        self.assertEqual(encode(text+'\n'),raw)
        for bad in ('Hello','[Portrait 01 00][End]','[PauseText ZZ][End]',
                    '[TextSpeed 00][End]','[End]After','[NoSuchTag][End]',
                    '[RunASM FFFFFF][End]after','[Font 00][End]'):
            with self.assertRaises(ValueError,msg=bad):encode(bad)
        with self.assertRaises(ValueError):decode(bytes.fromhex('00 ff 01'))

    def test_copy_on_write_longer_shorter_shared_and_stale(self):
        before=bytes(self.rom.data);model=Dialogue(self.rom,self.entry)
        text=model.text.replace('Milady','Dear lady',1)
        model.write(text)
        loaded=Dialogue(self.rom,self.entry)
        self.assertEqual(loaded.text,text)
        self.assertNotEqual(loaded.start,model.start)
        self.assertEqual(bytes(self.rom.data[model.start:model.start+model.length]),model.raw)
        for entry in self.entries:
            if entry!=self.entry:
                at=entry['address'];self.assertEqual(bytes(self.rom.data[at:at+3]),before[at:at+3])
        with self.assertRaises(ValueError):model.write(model.text.replace('Milady','Hello',1))
        loaded.write(text.replace('Dear lady','Lady',1))
        self.assertEqual(Dialogue(self.rom,self.entry).text,text.replace('Dear lady','Lady',1))
        starts=defaultdict(list)
        for entry in self.entries:
            model=Dialogue(self.rom,entry);starts[model.start].append(entry)
        pair=next(es for es in starts.values() if len(es)>1)
        first=Dialogue(self.rom,pair[0]);second=Dialogue(self.rom,pair[1]);raw=second.raw
        first.write(first.text.replace('[End]','Hello[End]'))
        self.assertEqual(Dialogue(self.rom,pair[1]).raw,raw)

    def test_storage_conflict_corruption_exhaustion_and_growth_patch_gap(self):
        from growth_patch import install,ARENA,SIZE
        install(self.rom);growth=bytes(self.rom.data[ARENA:ARENA+SIZE])
        model=Dialogue(self.rom,self.entry)
        model.write(model.text.replace('Milady','Hello',1))
        self.assertEqual(bytes(self.rom.data[ARENA:ARENA+SIZE]),growth)
        self.rom.data[REGIONS[0][0]+100]^=1
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):Dialogue(self.rom,self.entry).write(model.text.replace('Milady','Hi',1))
        self.assertEqual(bytes(self.rom.data),before)
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        self.rom.data[REGIONS[1][0]]=7;before=bytes(self.rom.data)
        with self.assertRaises(ValueError):Dialogue(self.rom,self.entry).write('[Start]Test[End]')
        self.assertEqual(bytes(self.rom.data),before)
        self.rom=Rom(next(ROOT.glob('*.sfc')))
        safe=[e for e in self.entries if not any(tag in Dialogue(self.rom,e).text for tag in ('[RunASM','[PrintDialogue'))][:6]
        for entry in safe[:5]:Dialogue(self.rom,entry).write('[Start]'+'A'*8190+'[End]')
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):Dialogue(self.rom,safe[5]).write('[Start]'+'B'*8190+'[End]')
        self.assertEqual(bytes(self.rom.data),before)

    def test_callbacks_are_preserved(self):
        model=next(Dialogue(self.rom,e) for e in self.entries if '[RunASM ' in Dialogue(self.rom,e).text)
        before=bytes(self.rom.data)
        with self.assertRaises(ValueError):model.write('[Start]Replacement[End]')
        self.assertEqual(bytes(self.rom.data),before)
        ordinary=Dialogue(self.rom,self.entry)
        with self.assertRaises(ValueError):ordinary.write(ordinary.text.replace('[End]','[PrintDialogue 6015DC][End]'))
        self.assertEqual(bytes(self.rom.data),before)

    def test_headered_save_backup_undo_redo_and_reopen(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path=Path(folder)/'dialogue.smc';path.write_bytes(bytes(512)+self.rom.data)
            rom=Rom(path);before=path.read_bytes();model=Dialogue(rom,self.entry)
            text=model.text.replace('Milady','Dear lady',1)
            rom.save_original('Dialogue edit',model.write(text))
            self.assertEqual(rom.last_backup.read_bytes(),before)
            self.assertEqual(Dialogue(Rom(path),self.entry).text,text)
            self.assertEqual(len(path.read_bytes()),len(before))
            self.assertEqual(rom.data[:512],bytes(512))
            rom.undo();self.assertEqual(path.read_bytes(),before)
            rom.redo();self.assertEqual(Dialogue(rom,self.entry).text,text)

    def test_window_search_staging_cancel_failed_save_and_preview(self):
        from FE4Builder import App
        app=App();app.withdraw();app.update_idletasks();app.rom=self.rom
        try:
            window=app.edit_dialogue()
            window.search.set('Milady, the castle')
            index=next(i for i in window.visible if self.entries[i]==self.entry)
            window.list.selection_clear(0,'end');window.list.selection_set(window.visible.index(index));window.select()
            self.assertEqual(window.model.entry,self.entry)
            text=window.contents().replace('Milady','Dear lady',1)
            window.text.delete('1.0','end');window.text.insert('1.0',text)
            self.assertTrue(window.pending());window.update_preview()
            rows,pages,overflow=preview(self.rom,text)
            self.assertEqual((len(rows),len(rows[0])),(64,256));self.assertGreater(pages,0)
            before=bytes(self.rom.data)
            with patch.object(self.rom,'save_original',side_effect=OSError('Read only')),patch('dialogue_window.messagebox.showerror'):
                self.assertFalse(window.save())
            self.assertEqual(bytes(self.rom.data),before);self.assertTrue(window.pending())
            with patch('dialogue_window.ask_unsaved',return_value=None):self.assertFalse(window.settle())
            with patch('dialogue_window.messagebox.askyesno',return_value=True):window.reload()
            self.assertFalse(window.pending());window.close()
        finally:app.destroy()
