import unittest
from copy import copy
from rom import ROOT,Rom
from ai_viewer import AIViewer

class AIViewerTests(unittest.TestCase):
    def setUp(self):self.rom=Rom(next(ROOT.glob('*.sfc')))
    def test_live_scripts_assignments_branches_and_headers(self):
        original=bytes(self.rom.data);model=AIViewer(self.rom)
        self.assertEqual(len(model.groups),72)
        self.assertEqual(sum(len(g['entries']) for g in model.groups),199)
        self.assertFalse(model.warnings)
        for g in model.groups:
            self.assertIsNone(g['error'])
            for e in g['entries']:
                nodes,warnings=model.decode(e['pointer'])
                self.assertTrue(nodes);self.assertFalse(warnings)
                self.assertFalse(any(n['name'].startswith('Unknown opcode') for n in nodes))
                self.assertTrue(model.shared(e['pointer']))
        arvis=model.groups[3];units=model.units(arvis,1)
        self.assertTrue(any(u['leader'] and u['character']==260 for u in units))
        evans=model.groups[2]['entries'][1];nodes,_=model.decode(evans['pointer'])
        self.assertTrue(any('Turn' in n['text'] for n in nodes))
        self.assertEqual(sum(n['name']=='Ai End' for n in nodes),2)
        target=model.groups[3]['entries'][0]['pointer'];nodes,_=model.decode(target)
        self.assertTrue(any('Sigurd' in n['text'] for n in nodes))
        at=model.address(target)+1;self.rom.data[at]=6
        self.assertIn('Unknown: 6',model.decode(target)[0][0]['text'])
        self.rom.data[:]=original
        headered=copy(self.rom);headered.header=512;headered.data=bytearray(512)+self.rom.data
        other=AIViewer(headered)
        self.assertEqual(other.groups,model.groups)
        self.assertEqual(other.decode(target),model.decode(target))
        self.assertEqual(bytes(self.rom.data),original)
    def test_corrupt_pointers_unknown_opcodes_and_cycles(self):
        model=AIViewer(self.rom);target=model.groups[3]['entries'][0]['pointer'];at=model.address(target)
        self.rom.data[at]=0xfe
        nodes,warnings=model.decode(target);self.assertEqual(len(nodes),1);self.assertIn('Unknown opcode',nodes[0]['name'])
        self.rom.data[at:at+3]=bytes([1,target&255,(target>>8)&255])
        nodes,warnings=model.decode(target);self.assertEqual(len(nodes),1)
        self.rom.data[0x6c784:0x6c787]=bytes(3)
        self.assertIsNotNone(AIViewer(self.rom).groups[0]['error'])
    def test_window_shared_links_target_and_readonly(self):
        from FE4Builder import App
        original=bytes(self.rom.data);app=App();app.withdraw();app.rom=self.rom
        try:
            window=app.view_ai(0,3,1);app.update()
            self.assertEqual(window.group['id'],3);self.assertEqual(window.number,1)
            self.assertTrue(window.commands.get_children())
            self.assertIn('Prologue Arvis Spawn',window.units_text.get('1.0','end'))
            self.assertEqual(str(window.detail['state']),'disabled')
            window.shared.selection_set(0);window.follow();self.assertEqual(window.group['id'],3)
            window.reload();self.assertEqual(bytes(self.rom.data),original)
            window.destroy()
            event=app.edit_events(1)
            command=next(i for i,c in enumerate(event.model.commands) if c['opcode']==0x24)
            event.commands.selection_set(str(command));event.select_command()
            self.assertEqual(str(event.ai_button['state']),'normal')
            from unittest.mock import patch
            with patch.object(app,'view_ai',return_value=None) as opened:
                event.inspect_ai();opened.assert_called_once_with(0,0,0)
            event.destroy()
        finally:app.destroy()
