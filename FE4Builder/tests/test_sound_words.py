import ctypes as C,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom
from audio_preview import catalogue
from sound_words import WORD_INFO,describe_word

class SoundWordTests(unittest.TestCase):
    def test_all_words_named_and_uncertainty_explicit(self):
        entries=[e for e in catalogue()['entries'] if e['kind']=='word']
        self.assertEqual({e['value'] for e in entries},set(WORD_INFO))
        for e in entries:
            self.assertEqual(e['label'],WORD_INFO[e['value']]['label'])
            self.assertTrue(e['description']);self.assertTrue(e['evidence'])
        self.assertEqual([WORD_INFO[v]['ticks'] for v in range(0xe0,0xe8)],[31,63,95,127,159,191,223,255])
        self.assertEqual(WORD_INFO[0xf7]['target'],60);self.assertEqual(WORD_INFO[0x7ff7]['target'],127)
        self.assertIn('partly',describe_word(0xd0));self.assertIn('Unknown',describe_word(65535))
    def test_native_volume_targets_stop_and_signal_match_descriptions(self):
        from audio_core import AudioCore
        from audio_preview import CORE
        rom=Rom(next(ROOT.glob('*.sfc')));original=bytes(rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            h=AudioCore(CORE,original,folder)
            try:
                h.run(1200)
                for i,b in enumerate(bytes.fromhex('2254968060')):h.ram[0x1f00+i]=b
                h.word(0xd7,0x1f00);h.run(2);h.word(0x4ba,0x11);h.run(180)
                h.core.retro_serialize_size.restype=C.c_size_t
                h.core.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];h.core.retro_serialize.restype=C.c_bool
                h.core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];h.core.retro_unserialize.restype=C.c_bool
                def snapshot():
                    block=C.create_string_buffer(h.core.retro_serialize_size());self.assertTrue(h.core.retro_serialize(block,len(block)));return block.raw
                def spc():
                    state=snapshot();at=state.index(b'SND:066560:')+11;return state[at:at+65536]
                base=snapshot()
                for word in (0xe0,0xe7,0xf7,0x7ff7):
                    block=C.create_string_buffer(base);self.assertTrue(h.core.retro_unserialize(block,len(base)))
                    h.word(0x4d8,word);h.run(1);ram=spc()
                    self.assertEqual(ram[0x2c3],WORD_INFO[word]['target'])
                    self.assertIn(WORD_INFO[word]['ticks']-ram[0xc4],(1,2))
                    h.run(300);ram=spc();self.assertEqual(ram[0xc6],WORD_INFO[word]['target'])
                    self.assertEqual(ram[0x22]==0,word in (0xe0,0xe7))
                h.word(0x4d8,0xe8);h.run(60);self.assertEqual(spc()[0xc6],255)
                self.assertEqual(spc()[0x448],0);h.word(0x4d8,0xd0);h.run(2);self.assertEqual(spc()[0x448],1)
            finally:h.close()
        self.assertEqual(bytes(rom.data),original)
    def test_viewer_and_editor_show_selected_word_meaning_without_edits(self):
        from FE4Builder import App
        app=App();app.withdraw();app.rom=Rom(next(ROOT.glob('*.sfc')));original=bytes(app.rom.data)
        try:
            with patch('winsound.PlaySound'):
                viewer=app.open_audio('word',0x7ff7)
                self.assertIn('127/255',viewer.details.get());self.assertIn('high byte',viewer.details.get())
                viewer.target('word',0xd0);self.assertIn('partly',viewer.details.get())
                viewer.destroy()
                editor=app.edit_events(1);command=next(i for i,c in enumerate(editor.model.commands) if c['opcode']==0x12)
                editor.commands.selection_set(str(command));editor.select_command();self.assertIn('31 driver ticks',editor.help.get())
                editor.variables[0].set(next(label for label,value in editor.field_options[0].items() if value==0x7ff7))
                self.assertIn('high byte',editor.help.get());self.assertIn('127',editor.help.get())
                editor.destroy()
            self.assertEqual(bytes(app.rom.data),original);self.assertFalse(app.rom.dirty)
        finally:app.destroy()
