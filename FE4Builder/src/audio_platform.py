"""Native audio core discovery and cancellable WAV playback on Windows/Linux."""
import os,sys,shutil,subprocess
from pathlib import Path
from rom import BUILDER_DIR


def core_path():
    configured=os.environ.get('FE4BUILDER_AUDIO_CORE')
    if configured:return Path(configured).expanduser()
    if os.name=='nt':return BUILDER_DIR/'vendor/snes9x/snes9x_libretro.dll'
    candidates=[BUILDER_DIR/'vendor/snes9x/snes9x_libretro.so']
    candidates += [Path(root)/'libretro/snes9x_libretro.so' for root in ('/usr/lib/x86_64-linux-gnu','/usr/lib/aarch64-linux-gnu','/usr/lib')]
    candidates += [Path.home()/'.config/retroarch/cores/snes9x_libretro.so',Path.home()/'.var/app/org.libretro.RetroArch/config/retroarch/cores/snes9x_libretro.so']
    return next((p for p in candidates if p.is_file()),candidates[0])


def player_command(path):
    for name,args in (('paplay',[]),('aplay',['-q']),('ffplay',['-nodisp','-autoexit','-loglevel','error'])):
        executable=shutil.which(name)
        if executable:return [executable,*args,str(path)]
    raise ValueError('Install pulseaudio-utils (paplay), alsa-utils (aplay), or ffmpeg (ffplay) to play previews.')


def playback_problem():
    if sys.maxsize<=2**32:return 'Audio previews require 64-bit Python.'
    if os.name=='nt':return '' if core_path().is_file() else 'The Snes9x audio core is missing.'
    if not sys.platform.startswith('linux'):return 'Audio previews currently support Windows and Linux.'
    if not core_path().is_file():return 'Install the Snes9x libretro core, or set FE4BUILDER_AUDIO_CORE to snes9x_libretro.so. Audio browsing and editing still work.'
    try:player_command('preview.wav')
    except ValueError as error:return str(error)
    return ''

class WavPlayer:
    def __init__(self):self.process=None;self.path=None;self.loop=False
    def play(self,path,loop=False):
        self.stop();self.path=Path(path);self.loop=loop
        if os.name=='nt':
            import winsound
            flags=winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT
            if loop:flags|=winsound.SND_LOOP
            winsound.PlaySound(str(path),flags)
        else:self._start()
    def _start(self):
        self.process=subprocess.Popen(player_command(self.path),shell=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def poll(self):
        if self.process is None:return False
        code=self.process.poll()
        if code is None:return True
        self.process.wait();self.process=None
        if code:raise ValueError('Audio player failed. Check that your desktop audio session is running.')
        if self.loop:self._start();return True
        return False
    def stop(self):
        self.loop=False
        if self.process is not None:
            if self.process.poll() is None:self.process.terminate()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.process=None
        if os.name=='nt':
            import winsound
            winsound.PlaySound(None,0)
