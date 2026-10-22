"""Project Naga integration tests; pass the supplied ROM as the first argument."""
import sys,tempfile,unittest,copy
from pathlib import Path
from core import ROM
from textcore import TextModel,TextError
from nagacore import NagaModel,encode_run,parse
ROM_PATH=sys.argv.pop(1)
class NagaTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rom=ROM(ROM_PATH);cls.model=TextModel(cls.rom);cls.rom.text=cls.model
  assert isinstance(cls.model,NagaModel)
  cls.intro=next(b for b in cls.model.blocks if b.label=='dialogueIntro1')
 def setUp(self):
  self.model.name_changes.clear();self.model.run_changes.clear();self.model.image_changes.clear();self.rom.pending.clear()
 def test_actual_english_and_live_pointer(self):
  self.assertEqual(self.intro.start,int.from_bytes(self.rom.data[0x31809c:0x31809f],'little'))
  self.assertEqual(self.intro.runs[0].text,'Milady, the castle is completely surrounded!')
  self.assertEqual(self.model.name(0),'Sigurd');self.assertEqual(self.model.name(1),'Noish')
  self.assertFalse(self.model.invalid);self.assertFalse(any(b.error for b in self.model.blocks))
  r=ROM(ROM_PATH);target=0x6f0000
  r.data[target:target+3]=b'\x09\x10\x01';r.data[0x31809c:0x31809f]=target.to_bytes(3,'little')
  m=TextModel(r);b=next(b for b in m.blocks if b.label=='dialogueIntro1')
  self.assertEqual(b.start,target);self.assertEqual(b.runs[0].text,'A')
  self.assertEqual(r.data[0x39a59:0x3adf5],self.rom.data[0x39a59:0x3adf5])
 def test_noop_and_every_indexed_passage(self):
  self.assertEqual(self.rom.build()[0],self.rom.original)
  for r in self.model.runs.values():self.assertEqual(encode_run(r,r.text)[0],r.raw)
  self.model.stage_image(0,self.model.menu_image(0));self.assertFalse(self.model.dirty)
  self.assertEqual(self.rom.build()[0],self.rom.original)
 def test_combined_save_preserves_other_data(self):
  run=self.intro.runs[0];self.model.stage_run(run,'Raddy, the castle is surrounded!');self.model.stage_name(0,'Raddy')
  im=self.model.render_name(0,'Raddy');self.model.stage_image(0,im);expected=self.model.image_changes[0]
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'edited.smc';self.rom.save(path);r=ROM(path);m=TextModel(r)
   self.assertEqual(m.name(0),'Raddy');self.assertEqual(m.name(1),'Noish')
   self.assertEqual(m.runs[run.start].text,'Raddy, the castle is surrounded!');self.assertEqual(m.runs[run.start].end,run.end)
   self.assertEqual(next(b for b in m.blocks if b.label=='dialogueIntro1').commands,self.intro.commands)
   p=self.model.menu[0]['pointer'];self.assertEqual(bytes(r.data[p:p+512]),expected)
   self.assertEqual(list(m.menu_image(0).getdata()),list(im.getdata()));self.assertEqual(r.header,self.rom.header)
   for at in (0xffde,0x40ffde):self.assertEqual(sum(r.data)&65535,int.from_bytes(r.data[at:at+2],'little'))
   allowed=set(range(0x505c00,0x505c10))|set(range(run.start,run.end))|set(range(p,p+512))|set(range(0xffdc,0xffe0))|set(range(0x40ffdc,0x40ffe0))
   self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(self.rom.data,r.data)) if a!=b))
   for a,b in zip(self.rom.portraits,r.portraits):self.assertEqual((a.raw,a.palette),(b.raw,b.palette))
  self.assertEqual(Path(ROM_PATH).read_bytes(),self.rom.original)
 def test_budget_controls_and_bitmap_guards(self):
  for text in ['x'*10000,'line\nbreak','😀']:
   with self.assertRaises(TextError):self.model.stage_run(self.intro.runs[0],text)
  with self.assertRaises(TextError):self.model.stage_name(0,'x'*15)
  with self.assertRaises(TextError):self.model.render_name(0,'VeryLongCharacterName')
  alias=next(i for i,e in enumerate(self.model.menu) if sum(x.get('pointer')==e.get('pointer') for x in self.model.menu)>1)
  im=self.model.menu_image(alias);im.putpixel((0,0),(im.getpixel((0,0))+1)%4)
  with self.assertRaises(TextError):self.model.stage_image(alias,im)
  self.assertTrue(parse(b'\x00\xff',0,'invalid','test').error)
 def test_projects_transaction_and_overlaps(self):
  self.model.stage_name(0,'Raddy');self.model.stage_run(self.intro.runs[0],'Hello, Raddy!');self.model.stage_image(0,self.model.render_name(0,'Raddy'))
  obj=self.model.export();m=NagaModel(self.rom);m.import_project(obj);self.assertEqual(obj,m.export())
  bad=copy.deepcopy(obj);bad['names']['0']='Marth';bad['images']['99999']='ff'
  with self.assertRaises(TextError):m.import_project(bad)
  self.assertEqual(m.export(),obj)
  m.stage_run(m.runs[m.names[0].runs[0].start],'Marth')
  with self.assertRaises(TextError):m.apply(bytearray(self.rom.data))
  data=bytearray(self.rom.data);data[self.intro.runs[0].start]^=1
  with self.assertRaises(TextError):self.model.apply(data)
 def test_headerless_and_font_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'base.sfc';path.write_bytes(self.rom.data);r=ROM(path);r.text=TextModel(r);r.text.stage_name(0,'Marth')
   out=Path(temp)/'out.sfc';r.save(out);self.assertEqual(len(out.read_bytes()),len(self.rom.data));self.assertEqual(TextModel(ROM(out)).name(0),'Marth')
  r=ROM(ROM_PATH);r.data[0x128000]^=1
  with self.assertRaises(TextError):TextModel(r)
if __name__=='__main__':unittest.main(verbosity=2)
