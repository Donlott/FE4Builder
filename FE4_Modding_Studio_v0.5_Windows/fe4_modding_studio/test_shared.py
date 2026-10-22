"""Run with the WORKING NOW ROM path and Raddy PNG path."""
import sys,tempfile
from pathlib import Path
from core import ROM,EditorError
rom_path,png_path=sys.argv[1:3]
r=ROM(rom_path)
r.import_png(0,png_path)
try:r.build();raise AssertionError('Single alias must remain protected')
except EditorError:pass
r.import_png(0xf6,png_path)
with tempfile.TemporaryDirectory() as d:
 out=Path(d)/'shared.smc';log=r.save(out);after=ROM(out)
 assert sum('graphics' in line for line in log)==1,log
 for i in [0,0xf6]:
  assert after.portraits[i].gfx==r.portraits[i].gfx
  assert (after.portraits[i].raw,after.portraits[i].palette)==r.pending[i]
 for i in range(248):
  if i not in [0,0xf6]:assert after.portraits[i]==r.portraits[i]
 assert Path(rom_path).read_bytes()==r.original
 assert after.header==r.header
 assert int.from_bytes(after.data[0xffde:0xffe0],'little')==sum(after.data)&65535
 print('PASS: both aliases saved without reservation; one graphics write; original pointers retained; both palettes correct; all other portraits and input unchanged.')
 raw,pal=r.pending[0xf6];r.pending[0xf6]=(bytes([raw[0]^1])+raw[1:],pal)
 try:r.build();raise AssertionError('Conflicting edits must remain protected')
 except EditorError:pass
 print('PASS: single-alias and conflicting-alias edits still require separate storage.')
 r.pending[0xf6]=r.pending[0]
 # A separate compressed stream using any affected byte must block reuse.
 other=r.portraits[1];other.touched=other.touched|{r.portraits[0].gfx}
 try:r.build();raise AssertionError('Indirect overlap must remain protected')
 except EditorError:pass
 print('PASS: indirect compressed-stream overlap blocks in-place replacement.')
