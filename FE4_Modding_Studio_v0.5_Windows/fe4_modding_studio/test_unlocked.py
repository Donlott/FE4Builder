import sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent.resolve()))
from core import ROM,rgb
from textcore import TextModel
from PIL import Image
source=Path(sys.argv[1]);r=ROM(source)
assert not r.shared_grey
with tempfile.TemporaryDirectory() as d:
 d=Path(d)
 for q in r.portraits:
  im=r.image(q.id);assert tuple(im.getpalette()[42:45])==rgb(int.from_bytes(q.palette[28:30],'little'))
  p=d/'roundtrip.png';im.save(p,transparency=0);r.import_png(q.id,p)
  assert r.pending[q.id]==(q.raw,q.palette),q.id
 assert r.build()[0]==r.original
 r.pending.clear()
 q=r.portraits[0];im=r.image(0);pal=im.getpalette();pal[42:45]=[255,0,0];im.putpalette(pal);im.save(d/'change.png',transparency=0)
 r.import_png(0,d/'change.png');assert r.pending[0][1][28:30]==b'\x1f\x00'
 r.reserve(0x690000,0x698000);r.save(d/'changed.smc');after=ROM(d/'changed.smc')
 assert not after.shared_grey and after.portraits[0].palette[28:30]==b'\x1f\x00'
 for i in range(1,248):assert after.portraits[i].palette==r.portraits[i].palette
 for a,n in [(0x9a183,1),(0xb8374,4),(0xbd780,3),(0x16cad5,3),(0x16cb04,3)]:assert after.data[a:a+n]==r.data[a:a+n]
 r.pending.clear()
 im=Image.new('RGBA',(64,64));im.putdata([(0,0,0,0) if i%16==0 else ((i%16)*16,0,0,255) for i in range(4096)]);im.save(d/'15.png');r.import_png(0,d/'15.png')
 assert len(set(r.image(0).getdata()))==16
 r.pending.clear();r.text=TextModel(r);r.text.stage_name(0,'MARTH');r.save(d/'name.smc');assert TextModel(ROM(d/'name.smc')).name(0)=='MARTH'
 assert source.read_bytes()==r.original
print('PASS: new ROM loads; all 248 portrait exports/reimports exact; index-14 colour edit saved/reopened; other palettes and unlock patch preserved; 15-colour RGBA import; text-name save/reopen; source unchanged.')
