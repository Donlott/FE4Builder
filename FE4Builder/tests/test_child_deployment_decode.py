"""Native child-deployment payloads must never appear as separate commands."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from copy import copy
from rom import Rom,ROOT
from event_commands import catalogue,EventCommands,audio_options
from item_slot_events import COMMAND_SIZES,CONDITION_SIZES

BUILDER=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('event_catalogue_builder',BUILDER/'scripts/build_event_catalogue.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class ChildDeploymentDecodeTests(unittest.TestCase):
    def test_payload_is_one_command_and_truncation_fails_for_both_wrappers(self):
        for wrapper in (0x4a,0x4d):
            raw=bytes([wrapper,0x4f,0x24,0x21,0x2e,0,0x3d,0,0x12,0xe2,0,0xff,0xff])
            main={wrapper:('RUN_EVENT_CONDITION',1),0x12:('PLAY_SFX_WORD',3)}
            conditions={0x4f:('DEPLOY_UNIT_GROUP_CHILD',7)}
            event={'start':0,'length':len(raw)}
            nodes=builder.decode_commands(raw,event,main,conditions)
            self.assertEqual([(c['offset'],c['size']) for c in nodes],[(0,8),(8,3),(11,2)])
            self.assertEqual(nodes[1]['opcode'],0x12)
            self.assertFalse(builder.cached_commands_match(raw,event,{'commands':[dict(nodes[0],size=3)]},main,conditions))
            with self.assertRaises(ValueError):builder.decode_commands(raw[:7],{'start':0,'length':7},main,conditions)

    def test_all_catalogued_sizes_match_independent_decoder(self):
        for e in catalogue()['entries']:
            for c in e['commands']:
                op=c['opcode'];child=c.get('condition')
                if op>255 or (op in (0x4a,0x4d) and child in (0x2c,0x2d,0x3a)):continue
                size=1+CONDITION_SIZES[child] if op in (0x4a,0x4d) else COMMAND_SIZES[op]
                self.assertEqual(c['size'],size,(e['label'],c['offset'],c['name']))
        for event_id in (253,296,301):
            e=next(e for e in catalogue()['entries'] if e['id']==event_id)
            self.assertNotIn('unsupported',e)
            self.assertTrue(any(c.get('condition')==0x4f and c['size']==8 for c in e['commands']))
        e=next(e for e in catalogue()['entries'] if e['id']==253)
        self.assertFalse(any(c['offset']==428 for c in e['commands']))
        self.assertEqual(next(c['opcode'] for c in e['commands'] if c['offset']==433),0x12)

    def test_restored_sound_edit_changes_only_its_operand_with_both_headers(self):
        rom=Rom(next(ROOT.glob('*.sfc')));original=bytes(rom.data)
        i=next(i for i,e in enumerate(catalogue()['entries']) if e['id']==253)
        for header in (0,512):
            r=copy(rom);r.header=header;r.data=bytearray(header)+original
            m=EventCommands(r,i);n=next(n for n,c in enumerate(m.commands) if c['offset']==433)
            value=next(v for v in audio_options(m.commands[n]) if v!=m.values(n)[0]);before=bytes(r.data)
            m.write({n:[value]});at=m.profile['start']+434+header
            self.assertEqual(r.data[:at],before[:at]);self.assertEqual(r.data[at+2:],before[at+2:])
            self.assertEqual(r.data[at:at+2],value.to_bytes(2,'little'))
            self.assertEqual(EventCommands(r,i).values(n),[value])

    def test_regeneration_replaces_bad_cache_and_preserves_indices(self):
        source=next((BUILDER/'research/fe4-source').glob('FireEmblem4-*'))
        rom=Rom(next(ROOT.glob('*.sfc')))
        with tempfile.TemporaryDirectory(dir=BUILDER/'research') as folder:
            root=Path(folder);(root/'data').mkdir()
            for filename in ('event_commands','events','conversations','objectives'):
                (root/f'data/{filename}.json').write_bytes((BUILDER/f'data/{filename}.json').read_bytes())
            path=root/'data/event_commands.json';data=json.loads(path.read_text(encoding='utf-8'))
            ids=[e['id'] for e in data['entries']]
            row=next(e for e in data['entries'] if e['id']==253)
            child=next(c for c in row['commands'] if c.get('condition')==0x4f);child['size']=3
            sound=next(c for c in row['commands'] if c['offset']==433)
            sound.update(offset=428,size=8,opcode=0x21,name='CREATE_SPRITE',condition=None,editable=False)
            path.write_text(json.dumps(data),encoding='utf-8')
            with patch.object(builder,'B',root):builder.build(bytes(rom.data),source)
            rebuilt=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual([e['id'] for e in rebuilt['entries']],ids)
            row=next(e for e in rebuilt['entries'] if e['id']==253)
            self.assertFalse(any(c['offset']==428 for c in row['commands']))
            self.assertEqual(next(c['size'] for c in row['commands'] if c.get('condition')==0x4f),8)
            self.assertEqual(len(rebuilt['skipped']),1)
