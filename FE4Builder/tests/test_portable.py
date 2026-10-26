"""ROM-free desktop/platform checks for Windows and Ubuntu 22.04."""
import importlib,json,sys,tempfile,unittest,subprocess,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from rom import ROOT,BUILDER_DIR,MODULES,lines,load_module
from ui_common import wheel_steps,bind_canvas_wheel,ContextStore
import audio_platform as audio

class PortableTests(unittest.TestCase):
    def test_wheel_windows_linux_and_canvas_routing(self):
        for event,expected in ((SimpleNamespace(num=4,delta=0),-1),(SimpleNamespace(num=5,delta=0),1),(SimpleNamespace(delta=120),-1),(SimpleNamespace(delta=-240),2),(SimpleNamespace(delta=1),-1)):
            self.assertEqual(wheel_steps(event),expected)
        callbacks={};canvas=Mock();canvas.bind.side_effect=lambda name,fn:callbacks.__setitem__(name,fn)
        bind_canvas_wheel(canvas)
        self.assertIn('<Button-4>',callbacks);self.assertIn('<Shift-Button-5>',callbacks)
        self.assertEqual(callbacks['<Button-4>'](SimpleNamespace(num=4)),'break');canvas.yview_scroll.assert_called_once_with(-1,'units')
        callbacks['<Shift-Button-5>'](SimpleNamespace(num=5));canvas.xview_scroll.assert_called_once_with(1,'units')
    def test_clean_gui_imports_module_casing_and_data(self):
        for module in (BUILDER_DIR/'src').glob('*.py'):importlib.import_module(module.stem)
        for path in MODULES.rglob('*.nmm'):
            load_module(path);data=lines(path)
            references=[data[5]]+[data[i] for i in range(11,len(data),5)]
            names={p.name for p in path.parent.iterdir()}
            for reference in references:
                if reference!='NULL':self.assertIn(reference,names,f'{path.name}: filename case mismatch')
        for path in (BUILDER_DIR/'data').glob('*.json'):
            if path.name not in ('emulator.json','rom-selector.json','ui-state.json'):json.loads(path.read_text(encoding='utf-8'))
        from FE4Builder import App
        app=App();app.withdraw()
        try:
            app.update_idletasks();self.assertIsNone(app.rom)
            self.assertIn('<Button-4>',app.bind())
            self.assertTrue(any(tool[1]=='Background Editor' for tool in app.home_tools))
            from ui_common import scrollable_frame
            import tkinter as tk
            top=tk.Toplevel(app);content=scrollable_frame(top);self.assertTrue(top.bind('<Button-4>'));top.destroy()
        finally:app.destroy()
    def test_linux_audio_arguments_loop_stop_and_errors(self):
        process=Mock();process.poll.return_value=0
        fake_os=SimpleNamespace(name='posix',environ={})
        with patch.object(audio,'os',fake_os),patch.object(audio.shutil,'which',side_effect=lambda name:'/usr/bin/paplay' if name=='paplay' else None),patch.object(audio.subprocess,'Popen',return_value=process) as opened:
            player=audio.WavPlayer();path=Path('a folder/test & music.wav');player.play(path,True)
            self.assertEqual(opened.call_args.args[0],['/usr/bin/paplay',str(path)])
            self.assertFalse(opened.call_args.kwargs['shell'])
            self.assertTrue(player.poll());self.assertEqual(opened.call_count,2)
            process.poll.return_value=None;player.stop();process.terminate.assert_called_once();self.assertIsNone(player.process)
            process.poll.return_value=1;player.play(path)
            with self.assertRaises(ValueError):player.poll()
        with patch.object(audio.shutil,'which',return_value=None):
            with self.assertRaises(ValueError):audio.player_command('x.wav')
    def test_optional_core_selection_and_case_sensitive_state(self):
        from history import History
        import history,ui_common
        with tempfile.TemporaryDirectory(dir=BUILDER_DIR/'tests') as folder:
            root=Path(folder);core=root/'snes9x_libretro.so';core.write_bytes(b'fixture')
            fake=SimpleNamespace(name='posix',environ={'FE4BUILDER_AUDIO_CORE':str(core)})
            with patch.object(audio,'os',fake):self.assertEqual(audio.core_path(),core)
            with patch.object(ui_common,'os',SimpleNamespace(name='posix')):
                store=ContextStore(root/'state.json');a=SimpleNamespace(path=root/'A.sfc');b=SimpleNamespace(path=root/'a.sfc')
                store.put(a,'test',{'value':1});self.assertEqual(store.get(b,'test'),{})
            with patch.object(history,'os',SimpleNamespace(name='posix')):
                self.assertNotEqual(History(root/'A.sfc',b'').folder,History(root/'a.sfc',b'').folder)
    def test_launchers_lf_and_linux_headless_message(self):
        for path in (ROOT/'Launcher.sh',ROOT/'Setup Ubuntu.sh',ROOT/'FE4_Modding_Studio_v0.5_Windows/Setup Ubuntu.sh',ROOT/'FE4_Modding_Studio_v0.5_Windows/Start Studio.sh'):
            data=path.read_bytes();self.assertTrue(data.startswith(b'#!/bin/sh\n'));self.assertNotIn(b'\r',data)
        if sys.platform.startswith('linux'):
            environment=dict(os.environ,DISPLAY='')
            result=subprocess.run([sys.executable,str(BUILDER_DIR/'scripts/start.py')],env=environment,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(result.returncode,0);self.assertIn('graphical desktop',result.stderr)
