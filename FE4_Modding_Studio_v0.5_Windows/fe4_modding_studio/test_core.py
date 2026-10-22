"""Run: python3 test_core.py /path/to/FE4.smc (ROM never modified)."""
import sys,unittest,tempfile,random
from pathlib import Path
from PIL import Image
from core import *
from codec import *
ROM_PATH=sys.argv.pop(1) if len(sys.argv)>1 else None
class CodecTests(unittest.TestCase):
    def test_known_commands(self):
        vectors=[(b'\x02abc\xff',b'abc'),(b'\x51ab\xff',b'aabb'),(b'\x60Xab\xff',b'XaXb'),(b'\x70Xab\xff',b'aXbX'),(b'\xf0Z\xff',b'ZZZ'),(b'\xe0\x09Z\xff',b'Z'*12),(b'\x40\x03\x12\xff',b'12'),(b'\x40\x13\x12\xff',b'\x13\x23'),(b'\x40\x85\x12\xff',b'\x05\x01\x02'),(b'\x40\xa5\x12\xff',b'\x05\x01\x02'),(b'\x40\x95\x12\xff',b'\x50\x10\x20'),(b'\x40\xc5\x12\xff',b'\xf5\xf1\xf2'),(b'\x40\xd5\x12\xff',b'\x5f\x1f\x2f'),(b'\x02abc\x84\x03\xff',b'abcabc'),(b'\x02abc\xc0\x80\x03\xff',b'abcabc'),(b'\x01ab\xfc\x03\xff',b'abab'),(b'\x01ab\xf8\x00\x03\xff',b'abab')]
        for encoded,expected in vectors:self.assertEqual(decompress(encoded,0)[0],expected)
    def test_generated_streams(self):
        rng=random.Random(4)
        for raw in [b'\0'*2048,bytes(rng.randrange(16) for _ in range(2048)),bytes(range(256))*8,b'0123456789'*100]:self.assertEqual(decompress(compress(raw),0)[0],raw)
    def test_bank_boundary(self):
        r=bytearray(0x20010);r[0x7ffe:0x8000]=b'\x02a';r[0x10000:0x10003]=b'bc\xff'
        self.assertEqual(decompress(r,0x7ffe)[0],b'abc')
        r[0xfffe:0x10000]=b'\x02a';r[0x18000:0x18003]=b'bc\xff'
        self.assertEqual(decompress(r,0xfffe)[0],b'abc')
    def test_bad_streams(self):
        for b in [b'\x80\x01',b'\0',b'\xe7\xffx\xff']:
            with self.assertRaises(ValueError):decompress(b,0,2048)

@unittest.skipUnless(ROM_PATH,'Pass a ROM to run integration tests')
class ROMTests(unittest.TestCase):
    def setUp(self):self.r=ROM(ROM_PATH);self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_all_export_import_noop(self):
        for q in self.r.portraits:
            self.assertEqual(pack(unpack(q.raw)),q.raw)
            p=self.d/'p.png';q.image().save(p,transparency=0);self.r.import_png(q.id,p)
            self.assertEqual(self.r.pending[q.id],(q.raw,q.palette))
        data,log=self.r.build();self.assertEqual(data,self.r.original);self.assertEqual(log,[])
    def test_recompress_all(self):
        for raw in {q.raw for q in self.r.portraits}:self.assertEqual(decompress(compress(raw),0)[0],raw)
    def test_replace_save_and_shared_isolation(self):
        q=next(q for q in self.r.portraits if any(p.id!=q.id and p.gfx==q.gfx for p in self.r.portraits))
        im=q.image();im.putpixel((8,8),(im.getpixel((8,8))+1)%14);p=self.d/'p.png';im.save(p,transparency=0);self.r.import_png(q.id,p)
        with self.assertRaises(EditorError):self.r.build()
        self.r.reserve(0x690000,0x698000);output=self.d/'modified.smc';self.r.save(output);after=ROM(output)
        self.assertEqual(after.portraits[q.id].raw,self.r.pending[q.id][0])
        for other in self.r.portraits:
            if other.id!=q.id:self.assertEqual(after.portraits[other.id].raw,other.raw)
        self.assertEqual(after.header,self.r.header);self.assertEqual(len(after.original),len(self.r.original))
        self.assertEqual(int.from_bytes(after.data[0xffde:0xffe0],'little'),sum(after.data)&65535)
        self.assertEqual(Path(ROM_PATH).read_bytes(),self.r.original)
    def test_shared_palette_isolation(self):
        q=next(q for q in self.r.portraits if any(p.id!=q.id and p.pal==q.pal for p in self.r.portraits))
        pal=bytearray(q.palette);pal[2]^=1;self.r.pending[q.id]=(q.raw,bytes(pal));self.r.reserve(0x690000,0x698000)
        data,_=self.r.build();(self.d/'x.smc').write_bytes(data);after=ROM(self.d/'x.smc')
        self.assertEqual(after.portraits[q.id].palette,bytes(pal))
        for other in self.r.portraits:
            if other.id!=q.id:self.assertEqual(after.portraits[other.id].palette,other.palette)
    def test_headerless_and_protection(self):
        p=self.d/'x.sfc';p.write_bytes(self.r.data);r=ROM(p);self.assertEqual(r.portraits[0].raw,self.r.portraits[0].raw)
        with self.assertRaises(EditorError):self.r.save(ROM_PATH)
        with self.assertRaises(EditorError):self.r.reserve(0xab4f9,0xab7e1)
        im=Image.new('RGB',(48,64));im.save(self.d/'bad.png')
        with self.assertRaises(EditorError):self.r.import_png(0,self.d/'bad.png')
    def test_rgb_conversion(self):
        im=Image.new('RGBA',(64,64),(0,0,0,0));im.paste((255,0,0,255),(8,8,16,16));im.save(self.d/'rgb.png');self.r.import_png(0,self.d/'rgb.png')
        preview=self.r.image(0).convert('RGBA');self.assertEqual(preview.getpixel((8,8)),(255,0,0,255));self.assertEqual(preview.getpixel((0,0))[3],0)
if __name__=='__main__':unittest.main(verbosity=2)
