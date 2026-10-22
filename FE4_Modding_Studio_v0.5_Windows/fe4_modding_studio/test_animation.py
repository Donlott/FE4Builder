"""Integration tests: python3 test_animation.py WORKING_NOW.smc [Raddy.png]."""
import sys,tempfile,unittest,copy
from pathlib import Path
from core import ROM
from animationcore import AnimationModel,AnimationError,BATTLE,COUNT,MAP,FEMALE,STANDING,order_key
from textcore import TextModel
ROM_PATH=sys.argv.pop(1);PNG=sys.argv.pop(1) if len(sys.argv)>1 else None
def lookup(rows,cls,sex,unit,weapon):
 # Model the staged class/gender/unit scan at $95:A2D5; fallback is prior row.
 stage=0
 for i,row in enumerate(rows):
  if row[0]!=cls:
   if stage>=1:return rows[i-1][4:]
   continue
  stage=max(stage,1)
  if row[3]!=sex:
   if stage>=2:return rows[i-1][4:]
   continue
  stage=max(stage,2)
  if row[2] and row[2]!=unit:
   if stage>=3:return rows[i-1][4:]
   continue
  stage=max(stage,3)
  if weapon==9 or row[1]==weapon:return row[4:]
 return rows[0][4:]

class AnimationTests(unittest.TestCase):
 def setUp(self):self.r=ROM(ROM_PATH);self.m=AnimationModel(self.r);self.r.animations=self.m
 def entry(self,kind,key):return next(e for e in self.m.entries.values() if e.kind==kind and e.key==key)
 def test_noop(self):
  self.assertEqual(self.r.build()[0],self.r.original)
  for e in self.m.entries.values():self.m.stage(e.address,e.original)
  self.assertFalse(self.m.dirty);self.assertEqual(self.r.build()[0],self.r.original)
 def test_separate_axe_handaxe_and_grouping(self):
  target=self.entry('Battle',(0x19,6,0,0));donor=self.entry('Battle',(0x29,6,0,0));axe=self.entry('Battle',(0x19,2,0,0))
  self.m.copy_from(target.address,donor.address);self.assertEqual(self.m.value(axe.address),axe.original)
  if self.m.bad_order:
   with self.assertRaises(AnimationError):self.r.build()
  else:self.r.build()
  self.m.reorder=True;data,_=self.r.build();body=data[len(self.r.header):]
  rows=[body[BATTLE+i*8:BATTLE+(i+1)*8] for i in range(COUNT)]
  self.assertEqual(rows,sorted(rows,key=order_key))
  self.assertEqual(next(r[4:] for r in rows if r[:4]==bytes(target.key)),donor.original)
  self.assertEqual(next(r[4:] for r in rows if r[:4]==bytes(axe.key)),axe.original)
  self.assertEqual(lookup(rows,0x19,0,1,6),donor.original)
  self.assertEqual(lookup(rows,0x19,0,1,2),axe.original)
  # Once grouped, the engine's staged scan reaches every explicit row key.
  for row in rows:
   self.assertEqual(lookup(rows,row[0],row[3],row[2],row[1]),row[4:])
 def test_map_and_movement(self):
  target=self.entry('Map combat',(0x19,));donor=self.entry('Map combat',(0x29,));self.m.copy_from(target.address,donor.address)
  female=self.entry('Female map assignment',(0x19,));self.m.stage(female.address,bytes([0x19,0x51]))
  move=self.entry('Map movement',(0x19,0,0));donormove=self.entry('Map movement',(0x27,0,255));self.m.copy_from(move.address,donormove.address)
  data,_=self.r.build();b=data[len(self.r.header):]
  self.assertEqual(b[target.address:target.address+49],donor.original)
  self.assertEqual(b[MAP+49*0x51:MAP+49*0x52],self.r.data[MAP+49*0x51:MAP+49*0x52])
  self.assertEqual(b[move.address:move.address+2],donormove.original)
 def test_project_and_validation(self):
  target=self.entry('Battle',(0x19,6,0,0));donor=self.entry('Battle',(0x29,6,0,0));self.m.copy_from(target.address,donor.address);self.m.reorder=True
  obj=self.m.export();m=AnimationModel(self.r);m.import_project(obj);self.assertEqual(m.export(),obj)
  bad=copy.deepcopy(obj);bad['changes']['FFFFFF']='00'
  with self.assertRaises(KeyError):m.import_project(bad)
  self.assertEqual(m.export(),obj)
  bad=copy.deepcopy(obj);bad['rom_sha256']='wrong'
  with self.assertRaises(AnimationError):m.import_project(bad)
  with self.assertRaises(AnimationError):m.stage(target.address,b'\xff\x00\x00\x00')
 def test_overlap_and_loader_guard(self):
  e=self.entry('Battle',(0x19,6,0,0));self.m.stage(e.address,b'\x37\x37\x26\x26');self.m.reorder=True
  b=bytearray(self.r.data);b[BATTLE]^=1
  with self.assertRaises(AnimationError):self.m.apply(b)
  self.r.data[0x15a2c8]^=1
  with self.assertRaises(AnimationError):AnimationModel(self.r)
 def test_combined_save_and_headerless(self):
  e=self.entry('Battle',(0x19,6,0,0));donor=self.entry('Battle',(0x29,6,0,0));self.m.copy_from(e.address,donor.address);self.m.reorder=True
  maprow=self.entry('Map combat',(0x19,));self.m.copy_from(maprow.address,self.entry('Map combat',(0x29,)).address)
  self.r.text=TextModel(self.r);self.r.text.stage_name(0,'RAD')
  if PNG:
   self.r.import_png(0,PNG);self.r.import_png(0xf6,PNG)
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'combined.smc';self.r.save(out);r=ROM(out);m=AnimationModel(r)
   self.assertFalse(m.bad_order);self.assertEqual(TextModel(r).name(0),'RAD')
   self.assertEqual(r.header,self.r.header);self.assertEqual(len(r.original),len(self.r.original))
   for q in r.portraits:
    expected=self.r.pending.get(q.id,(self.r.portraits[q.id].raw,self.r.portraits[q.id].palette));self.assertEqual((q.raw,q.palette),expected)
   self.assertEqual(int.from_bytes(r.data[0xffde:0xffe0],'little'),sum(r.data)&65535)
   h=Path(d)/'headerless.sfc';h.write_bytes(self.r.data);hr=ROM(h);hr.animations=AnimationModel(hr);hr.animations.copy_from(maprow.address,self.entry('Map combat',(0x29,)).address);hr.save(Path(d)/'headerless_out.sfc');self.assertEqual(ROM(Path(d)/'headerless_out.sfc').header,b'')
   # Binary diff is restricted to declared edits, portraits, name pool, checksums.
   allowed=set()
   for a,old,new in self.m.planned():allowed.update(range(a,a+len(old)))
   allowed.update(range(0x505c00,0x505c10) if getattr(self.r.text,'profile','')=='Project Naga' else range(0x39a59,0x3adf5));allowed.update(range(0xffdc,0xffe0));allowed.update(range(0x40ffdc,0x40ffe0))
   for i in self.r.pending:
    q=self.r.portraits[i];allowed.update(q.touched);allowed.update(range(q.pal,q.pal+32))
   self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(self.r.data,r.data)) if a!=b))
  self.assertEqual(Path(ROM_PATH).read_bytes(),self.r.original)
if __name__=='__main__':unittest.main(verbosity=2)
