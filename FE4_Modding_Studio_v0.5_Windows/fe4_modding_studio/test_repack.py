"""Run: python3 test_repack.py ROM.smc"""
import sys, unittest, tempfile, random
from pathlib import Path
from core import ROM, GFX_TABLE, PAL_TABLE, COUNT, EditorError
from codec import decompress
import repack
ROM_PATH=sys.argv.pop(1)
class PackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom=ROM(ROM_PATH)
        cls.initial=cls.rom.packing_plan()
    def setUp(self):
        self.r=self.rom;self.r.pending.clear();self.r.optimize_portraits=True;self.r.arena=None
    def test_repack_preserves_all_assets_and_unrelated_bytes(self):
        r=self.r;plan=r.packing_plan()
        self.assertGreater(plan.remaining,0)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'packed.smc';r.save(path);after=ROM(path)
            for old,new in zip(r.portraits,after.portraits):
                self.assertEqual((old.raw,old.palette),(new.raw,new.palette))
            allowed=plan.allowed|set(range(GFX_TABLE,PAL_TABLE+COUNT*3))|set(range(0xffdc,0xffe0))|set(range(0x40ffdc,0x40ffe0))
            self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(r.data,after.data)) if a!=b))
            self.assertEqual(after.header,r.header)
            self.assertEqual(sum(after.data)&65535,int.from_bytes(after.data[0xffde:0xffe0],'little'))
            # Reopen and plan again: orphaned tail bytes are not presumed free.
            after._compression_cache=r._compression_cache.copy()
            after.optimize_portraits=True;after.build()
        self.assertEqual(Path(ROM_PATH).read_bytes(),r.original)
    def test_smaller_funds_larger_and_alias_split(self):
        r=self.r
        large=max(r.portraits,key=lambda p:len(r._compression_cache[p.raw]))
        target=min((p for p in r.portraits if p.id not in (0,0xf6) and len(p.touched)>100),key=lambda p:len(p.touched))
        self.assertGreater(len(r._compression_cache[large.raw]),len(target.touched))
        larger=bytes([large.raw[0]^1])+large.raw[1:]
        r.pending[target.id]=(larger,target.palette)
        donor=next(p for p in r.portraits if p.id not in (target.id,0,0xf6))
        # Unique small sheet contributes space without needing adjacent storage.
        r.pending[donor.id]=(bytes(2048),donor.palette)
        r.pending[0]=(large.raw,r.portraits[0].palette)
        result,_=r.build();data=result[len(r.header):]
        for p in r.portraits:
            g=r.address(int.from_bytes(data[GFX_TABLE+p.id*3:GFX_TABLE+p.id*3+3],'little'))
            self.assertEqual(decompress(data,g,2048)[0],r.pending.get(p.id,(p.raw,p.palette))[0])
        # Different pixels no longer use the shared 00/F6 pointer.
        self.assertNotEqual(data[GFX_TABLE:GFX_TABLE+3],data[GFX_TABLE+0xf6*3:GFX_TABLE+0xf6*3+3])
    def test_unknown_holes_and_window_boundaries(self):
        plan=self.r.packing_plan()
        read=set().union(*(p.touched for p in self.r.portraits))
        for a,blob in plan.writes:
            self.assertEqual(a//0x8000,(a+len(blob)-1)//0x8000)
            self.assertTrue(set(range(a,a+len(blob)))<=read)
        for a,b in repack.PROFILE_WINDOWS:
            self.assertFalse((set(range(a,b))-read)&plan.allowed)
        # Direct trace excludes borrowed compressed instructions.
        # At 10: FC 08 copies three bytes from offset 2, then FF ends.
        d=bytearray(32);d[2:5]=bytes([0xf0,7,0xff]);d[10:13]=bytes([0xfc,8,0xff])
        direct=set();raw,touched=decompress(d,10,direct=direct)
        self.assertEqual(raw,bytes([7])*3)
        self.assertEqual(direct,{10,11});self.assertTrue({2,3,4}<=touched)
    def test_shared_palette_split(self):
        r=self.r;p=next(p for p in r.portraits if any(q.id!=p.id and q.pal==p.pal for q in r.portraits))
        pal=bytearray(p.palette);pal[2]^=1;r.pending[p.id]=(p.raw,bytes(pal))
        b,_=r.build();data=b[len(r.header):]
        for q in r.portraits:
            a=r.address(int.from_bytes(data[PAL_TABLE+q.id*3:PAL_TABLE+q.id*3+3],'little'))
            self.assertEqual(bytes(data[a:a+32]),r.pending.get(q.id,(q.raw,q.palette))[1])
    def test_exhaustion_leaves_output_and_input_untouched(self):
        windows=repack.PROFILE_WINDOWS
        try:
            repack.PROFILE_WINDOWS=[(0xa65b5,0xa65c5)]
            with tempfile.TemporaryDirectory() as d:
                out=Path(d)/'copy.smc';out.write_bytes(b'keep')
                with self.assertRaises(EditorError):self.r.save(out)
                self.assertEqual(out.read_bytes(),b'keep')
        finally:repack.PROFILE_WINDOWS=windows
        self.assertEqual(Path(ROM_PATH).read_bytes(),self.r.original)
if __name__=='__main__':unittest.main()
