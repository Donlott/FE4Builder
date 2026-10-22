"""Small headless libretro host used only by an isolated audio-preview worker."""
import ctypes as C
from pathlib import Path
ENV=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
VIDEO=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
AUDIO=C.CFUNCTYPE(None,C.c_int16,C.c_int16)
BATCH=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t)
POLL=C.CFUNCTYPE(None)
INPUT=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
class Variable(C.Structure):_fields_=[('key',C.c_char_p),('value',C.c_char_p)]
class Game(C.Structure):_fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class Geometry(C.Structure):_fields_=[('base_width',C.c_uint),('base_height',C.c_uint),('max_width',C.c_uint),('max_height',C.c_uint),('aspect_ratio',C.c_float)]
class Timing(C.Structure):_fields_=[('fps',C.c_double),('sample_rate',C.c_double)]
class AV(C.Structure):_fields_=[('geometry',Geometry),('timing',Timing)]

class AudioCore:
    def __init__(self,path,rom,directory):
        self.core=C.CDLL(str(Path(path).resolve()));self.settings={};self.directory=str(Path(directory).resolve()).encode();self.capture=False;self.samples=[]
        def env(command,data):
            if command==10:return True
            if command in (9,30,31):C.cast(data,C.POINTER(C.c_char_p))[0]=self.directory;return True
            if command==3:C.cast(data,C.POINTER(C.c_bool))[0]=True;return True
            if command==16:
                values=C.cast(data,C.POINTER(Variable));i=0
                while values[i].key:
                    self.settings[values[i].key]=values[i].value.split(b';',1)[-1].strip().split(b'|')[0];i+=1
                return True
            if command==15:
                var=C.cast(data,C.POINTER(Variable)).contents;var.value=self.settings.get(var.key);return var.value is not None
            if command==17:C.cast(data,C.POINTER(C.c_bool))[0]=False;return True
            if command==52:C.cast(data,C.POINTER(C.c_uint))[0]=0;return True
            return command in (1,11,18)
        def batch(data,count):
            if self.capture:self.samples.append(C.string_at(data,count*4))
            return count
        def sample(left,right):
            if self.capture:self.samples.append(bytes(C.c_int16(left))+bytes(C.c_int16(right)))
        self.callbacks=[ENV(env),VIDEO(lambda *_:None),AUDIO(sample),BATCH(batch),POLL(lambda:None),INPUT(lambda *_:0)]
        for name,callback in zip(('environment','video_refresh','audio_sample','audio_sample_batch','input_poll','input_state'),self.callbacks):getattr(self.core,'retro_set_'+name)(callback)
        self.core.retro_init();self.blob=C.create_string_buffer(rom)
        game=Game(b'audio-preview.sfc',C.cast(self.blob,C.c_void_p),len(rom),None)
        self.core.retro_load_game.argtypes=[C.POINTER(Game)];self.core.retro_load_game.restype=C.c_bool
        if not self.core.retro_load_game(C.byref(game)):raise ValueError('Audio core could not load this ROM.')
        self.core.retro_get_memory_data.argtypes=[C.c_uint];self.core.retro_get_memory_data.restype=C.c_void_p
        self.core.retro_get_memory_size.argtypes=[C.c_uint];self.core.retro_get_memory_size.restype=C.c_size_t
        pointer=self.core.retro_get_memory_data(2);size=self.core.retro_get_memory_size(2)
        if not pointer or size!=131072:raise ValueError('Audio core did not expose SNES work RAM.')
        self.ram=(C.c_ubyte*size).from_address(pointer)
        info=AV();self.core.retro_get_system_av_info.argtypes=[C.POINTER(AV)];self.core.retro_get_system_av_info(C.byref(info))
        self.fps=info.timing.fps;self.rate=round(info.timing.sample_rate)
    def run(self,count=1):
        for _ in range(count):self.core.retro_run()
    def word(self,address,value):self.ram[address]=value&255;self.ram[address+1]=value>>8&255
    def close(self):self.core.retro_unload_game();self.core.retro_deinit()
