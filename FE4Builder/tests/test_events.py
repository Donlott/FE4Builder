import unittest
from types import SimpleNamespace
from rom import Rom,ROOT
from events import catalogue,inspect

class EventTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))

    def test_catalogue_and_read_only_inspection(self):
        before=bytes(self.rom.data);data=catalogue()
        self.assertEqual(len(data['events']),557)
        self.assertEqual({e['chapter'] for e in data['chapters']},set(range(12)))
        for e in data['events']:self.assertTrue(inspect(self.rom,e)['matches'],e['label'])
        for e in data['chapters']:self.assertTrue(inspect(self.rom,e,True)['matches'])
        self.assertEqual(bytes(self.rom.data),before)

    def test_changed_relocated_and_invalid_data(self):
        e=catalogue()['events'][0]
        self.rom.data[e['start']]^=1
        self.assertFalse(inspect(self.rom,e)['matches'])
        at=0xfe8bf+e['id']*3
        self.rom.data[at:at+3]=(0x2f8020).to_bytes(3,'little')
        self.assertEqual(inspect(self.rom,e)['start'],0x6f8020)
        self.assertFalse(inspect(self.rom,e)['matches'])
        self.rom.data[at:at+3]=bytes(3)
        with self.assertRaises(ValueError):inspect(self.rom,e)

    def test_copier_header(self):
        headered=SimpleNamespace(data=bytearray(512)+self.rom.data,header=512)
        for e in catalogue()['events']:
            self.assertEqual(inspect(headered,e),inspect(self.rom,e))

    def test_viewer_navigation_and_search(self):
        from FE4Builder import App
        app=App();app.withdraw()
        try:
            app.rom=self.rom;window=app.view_events();app.update()
            self.assertEqual(len(window.visible),1+sum(e['chapter']==0 for e in catalogue()['events']))
            window.search.set('QuanGroupSpawn');app.update()
            self.assertGreater(len(window.visible),1)
            window.list.selection_clear(0,'end');window.list.selection_set(1);window.select()
            self.assertIn('Reference bytes match',window.status.get())
            self.assertTrue(window.scene_entries)
            window.chapter.current(11);window.populate();app.update()
            self.assertEqual(window.visible[0][1]['chapter'],11)
            window.destroy()
        finally:app.destroy()
