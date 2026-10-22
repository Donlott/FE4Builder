"""Read-only music/effect preview rendering and cancellable worker jobs."""
import hashlib,json,os,subprocess,sys,tempfile,time,wave
from functools import lru_cache
from pathlib import Path
from rom import BUILDER_DIR,DATA_DIR

CORE=BUILDER_DIR/'vendor/snes9x/snes9x_libretro.dll'
CACHE=DATA_DIR/'audio-cache'
VERSION=2
@lru_cache(maxsize=1)
def catalogue():return json.loads((DATA_DIR/'audio.json').read_text(encoding='utf-8'))
def playback_available():return os.name=='nt' and sys.maxsize>2**32

def clean_rom(data):
    raw=bytes(data);header=len(raw)%0x8000
    if header not in (0,512) or len(raw)<0x400000:raise ValueError('Expected a FE4 ROM.')
    raw=raw[header:]
    if not raw[0xffc0:0xffd5].startswith(b'FIREEMBLEM4'):raise ValueError('This is not a supported FE4 ROM.')
    for guard in catalogue()['guards']:
        if hashlib.sha256(raw[guard['start']:guard['start']+guard['length']]).hexdigest()!=guard['hash']:
            raise ValueError('Audio preview needs the native FE4 sound driver. This ROM changes its playback routines.')
    return raw

def validate(kind,value,seconds,context):
    if not any(e['kind']==kind and e['value']==value for e in catalogue()['entries']):raise ValueError('This sound ID is not in the verified preview catalogue.')
    if type(seconds) is not int or not 1<=seconds<=120:raise ValueError('Preview length must be 1–120 seconds.')
    if context and not any(e['kind']=='music' and e['value']==context for e in catalogue()['entries']):raise ValueError('Choose a known background track.')

def render(data,kind,value,seconds,context,output,core_path=CORE):
    from audio_core import AudioCore
    validate(kind,value,seconds,context);raw=clean_rom(data)
    if os.name!='nt' or sys.maxsize<=2**32:raise ValueError('Audio playback currently requires 64-bit Windows Python.')
    if not Path(core_path).is_file():raise ValueError('The bundled Snes9x audio core is missing.')
    host=AudioCore(core_path,raw,Path(output).parent)
    try:
        host.run(1200)
        # The game stays untouched. Redirect only this private emulator's main task to
        # a WRAM thunk; normal VBlank/APU transport continues without intro events.
        for i,b in enumerate(bytes.fromhex('2254968060')):host.ram[0x1f00+i]=b
        host.word(0xd7,0x1f00);host.run(2)
        if kind=='music':
            host.word(0x4ba,value)
        else:
            # Load the normal chapter sound bank before isolated event effects.
            host.word(0x4ba,context or 0x11);host.run(180)
            if kind=='byte' or not context:
                host.word(0x4d8,0xe0);host.run(180)
            if kind=='word' and value==0xe8 and context:
                # Native village pattern: duck first, then audition the restoration.
                host.word(0x4d8,0xf7);host.run(90)
            host.word(0x4e2 if kind=='byte' else 0x4d8,value)
        host.capture=True;host.run(round(host.fps*seconds));host.capture=False
        pcm=b''.join(host.samples)
        if not pcm:raise ValueError('The audio core returned no samples.')
        with wave.open(str(output),'wb') as out:
            out.setparams((2,2,host.rate,0,'NONE','not compressed'));out.writeframes(pcm)
        return len(pcm)//4/host.rate
    finally:host.close()

class PreviewJob:
    def __init__(self,data,kind,value,seconds,context=0,cache=CACHE):
        if not playback_available():raise ValueError('Built-in audio playback is available on 64-bit Windows only. Audio browsing and event editing remain available on Linux.')
        validate(kind,value,seconds,context);raw=clean_rom(data)
        if not CORE.is_file():raise ValueError('The bundled Snes9x audio core is missing.')
        self.cache=Path(cache);self.cache.mkdir(parents=True,exist_ok=True)
        key=hashlib.sha256(raw+f'{VERSION}:{kind}:{value}:{seconds}:{context}'.encode()+hashlib.sha256(CORE.read_bytes()).digest()).hexdigest()
        self.output=self.cache/(key+'.wav');self.process=None;self.temp=None;self.started=time.monotonic();self.error=None
        if self.output.exists():self.output.touch();return
        self.temp=tempfile.TemporaryDirectory(prefix='job-',dir=self.cache)
        folder=Path(self.temp.name);snapshot=folder/'snapshot.sfc';snapshot.write_bytes(raw)
        self.pending_output=folder/'preview.wav'
        args=[sys.executable,str(Path(__file__).resolve()),str(snapshot),kind,str(value),str(seconds),str(context),str(self.pending_output)]
        try:self.process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception:self.temp.cleanup();self.temp=None;raise
    def poll(self):
        if self.error:raise ValueError(self.error)
        if self.process is None:return self.output
        if time.monotonic()-self.started>90:
            self.cancel();self.error='Audio preview timed out. This sound may need an unsupported driver/context.';raise ValueError(self.error)
        if self.process.poll() is None:return None
        code=self.process.returncode;stdout,stderr=self.process.communicate();self.process=None
        try:
            if code or not self.pending_output.is_file():
                self.error=(stderr.decode('utf-8',errors='replace').strip().splitlines() or ['The audio worker could not render this sound.'])[-1]
                raise ValueError(self.error)
            with wave.open(str(self.pending_output),'rb') as sound:
                if sound.getnchannels()!=2 or sound.getsampwidth()!=2 or sound.getnframes()==0:raise ValueError('Invalid audio preview output.')
            os.replace(self.pending_output,self.output)
            # Keep the cache bounded. Leave the current playback file in place.
            files=sorted(self.cache.glob('*.wav'),key=lambda p:p.stat().st_mtime,reverse=True)
            total=0
            for file in files:
                total+=file.stat().st_size
                if total>128*1024*1024 and file!=self.output:
                    try:file.unlink()
                    except OSError:pass
            return self.output
        finally:
            if self.temp:self.temp.cleanup();self.temp=None
    def cancel(self):
        if self.process is not None:
            if self.process.poll() is None:self.process.terminate()
            try:self.process.communicate(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.communicate()
            self.process=None
        if self.temp:self.temp.cleanup();self.temp=None

if __name__=='__main__':
    try:render(Path(sys.argv[1]).read_bytes(),sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),Path(sys.argv[6]))
    except Exception as error:print(str(error),file=sys.stderr);raise SystemExit(1)
