import array,hashlib,sys,tempfile,time,unittest,wave
from pathlib import Path
from unittest.mock import patch
from rom import ROOT,Rom
from audio_preview import catalogue,clean_rom,validate,PreviewJob,render

class AudioPreviewTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))
    def test_catalogue_and_native_driver_guard(self):
        entries=catalogue()['entries']
        self.assertTrue(any(e['kind']=='music' and e['value']==0x22 for e in entries))
        self.assertTrue(any(e['kind']=='byte' and e['value']==0x6b for e in entries))
        self.assertTrue(any(e['kind']=='word' and e['value']==0x7ff7 for e in entries))
        raw=clean_rom(self.rom.data);self.assertEqual(clean_rom(bytes(512)+raw),raw)
        broken=bytearray(raw);broken[0x9654]^=1
        with self.assertRaises(ValueError):clean_rom(broken)
        for args in [('music',65535,3,0),('byte',0x6b,0,0),('word',0xe0,3,65535)]:
            with self.assertRaises(ValueError):validate(*args)
    def read(self,path):
        with wave.open(str(path),'rb') as sound:
            self.assertEqual((sound.getnchannels(),sound.getsampwidth(),sound.getframerate()),(2,2,32040))
            return array.array('h',sound.readframes(sound.getnframes()))
    def test_native_music_effect_and_control_rendering_readonly(self):
        original=bytes(self.rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            folder=Path(folder);tracks=[]
            for value in (0x11,0x22):
                path=folder/f'music-{value}.wav';render(original,'music',value,3,0,path);samples=self.read(path)
                self.assertGreater(max(map(abs,samples)),1000);tracks.append(hashlib.sha256(samples.tobytes()).digest())
            self.assertNotEqual(*tracks)
            path=folder/'effect.wav';render(original,'byte',0x6b,3,0,path);samples=self.read(path)
            self.assertGreater(max(map(abs,samples)),1000)
            path=folder/'fade.wav';render(original,'word',0xe0,4,0x11,path);samples=self.read(path)
            self.assertGreater(max(map(abs,samples[:32040*2])),100)
            self.assertLess(max(map(abs,samples[-32040*2:])),50)
        self.assertEqual(bytes(self.rom.data),original);self.assertEqual(self.rom.path.read_bytes(),original)
    def test_worker_cache_cancel_and_headered_key(self):
        original=bytes(self.rom.data)
        with tempfile.TemporaryDirectory(dir=ROOT/'FE4Builder/research') as folder:
            job=PreviewJob(original,'byte',0x6b,2,cache=folder);deadline=time.monotonic()+20;output=None
            while output is None and time.monotonic()<deadline:
                output=job.poll()
                if output is None:time.sleep(.05)
            self.assertIsNotNone(output);self.assertGreater(max(map(abs,self.read(output))),1000)
            cached=PreviewJob(bytes(512)+original,'byte',0x6b,2,cache=folder)
            self.assertIsNone(cached.process);self.assertEqual(cached.poll(),output)
            cancel=PreviewJob(original,'music',0x22,120,cache=folder);temporary=Path(cancel.temp.name);cancel.cancel()
            self.assertFalse(temporary.exists());self.assertIsNone(cancel.process)
        self.assertEqual(bytes(self.rom.data),original)
    def test_player_ui_readonly_and_event_preview_links(self):
        from FE4Builder import App
        from event_commands import catalogue as events
        app=App();app.withdraw();app.rom=self.rom;original=bytes(self.rom.data)
        try:
            with patch('winsound.PlaySound') as playback:
                window=app.open_audio('byte',0x6b)
                self.assertEqual(window.entries[window.current]['value'],0x6b)
                self.assertFalse(hasattr(window,'save'));self.assertFalse(playback.called)
                window.stop();self.assertTrue(playback.called);window.destroy()
                editor=app.edit_events(1)
                command=next(i for i,c in enumerate(editor.model.commands) if c['opcode']==0x12)
                editor.commands.selection_set(str(command));editor.select_command()
                self.assertEqual(str(editor.audio_button['state']),'normal')
                with patch.object(app,'open_audio') as opened:
                    editor.audio_button.invoke();opened.assert_called_once_with('word',0xe0,autoplay=True)
                editor.destroy()
            self.assertEqual(bytes(self.rom.data),original);self.assertFalse(self.rom.dirty)
        finally:app.destroy()
