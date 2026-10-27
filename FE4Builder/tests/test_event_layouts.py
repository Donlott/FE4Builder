"""ROM-free checks for dialogue relocations inside protected event layouts."""
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from dialogue import encode
from event_layouts import checked,profiles


class EventLayoutTests(unittest.TestCase):
    def setUp(self):
        self.start=0x108000;self.address=self.start+2
        self.original=(0x600000).to_bytes(3,'little')
        # Generated quote command, participant word and an unrelated pointer.
        self.raw=b'\x31\xff'+self.original+b'\x01\x11\x00'+self.original+b'\xff\xff'
        self.profile={'start':self.start,'length':len(self.raw),'masks':[[6,2]],
                      'dialogues':[[self.address,self.original.hex()]]}
        canonical=bytearray(self.raw);canonical[6:8]=bytes(2)
        self.profile['hash']=hashlib.sha256(canonical).hexdigest()
        self.profile_patch=patch('event_layouts.profiles',return_value={})
        self.profile_patch.start();self.addCleanup(self.profile_patch.stop)
        # Synthetic ROMs have no game engine; the real engine check is covered
        # separately below. Pointer mapping, bounds and dialogue decoding run.
        self.engine=patch('dialogue.check_profile');self.engine.start()
        self.addCleanup(self.engine.stop)

    def rom(self,header=0):
        data=bytearray(0x800000+header)
        data[self.start+header:self.start+header+len(self.raw)]=self.raw
        for at,text in ((0x600000,'Original[End]'),(0x7d2400,'Edited[End]')):
            payload=encode(text);data[at+header:at+header+len(payload)]=payload
        return SimpleNamespace(data=data,header=header)

    def move(self,rom,address=None,pointer=0x7d2400):
        at=(self.address if address is None else address)+rom.header
        rom.data[at:at+3]=pointer.to_bytes(3,'little')

    def test_original_and_relocated_dialogue_with_both_header_formats(self):
        for header in (0,512):
            with self.subTest(header=header):
                rom=self.rom(header);before=bytes(rom.data)
                self.assertEqual(checked(rom,self.profile),self.raw)
                self.assertEqual(bytes(rom.data),before)
                self.move(rom);before=bytes(rom.data)
                snapshot=checked(rom,self.profile)
                self.assertEqual(snapshot[2:5],(0x7d2400).to_bytes(3,'little'))
                self.assertEqual(bytes(rom.data),before)

    def test_invalid_unmapped_non_dialogue_and_unterminated_targets_rejected(self):
        for pointer in (0,0x7e0000,0xc08000,0x601000,0x7dfffe):
            with self.subTest(pointer=f'{pointer:06X}'):
                rom=self.rom();self.move(rom,pointer=pointer);before=bytes(rom.data)
                with self.assertRaisesRegex(ValueError,'Dialogue pointer.*unsupported'):
                    checked(rom,self.profile)
                self.assertEqual(bytes(rom.data),before)

    def test_changed_pointer_requires_supported_dialogue_engine(self):
        self.engine.stop();rom=self.rom();self.move(rom)
        with self.assertRaisesRegex(ValueError,'dialogue engine does not match'):
            checked(rom,self.profile)

    def test_readable_bytes_without_a_dialogue_end_are_rejected(self):
        rom=self.rom();self.move(rom,pointer=0x601000)
        rom.data[0x601000:0x605000]=encode('A[End]')[:1]*16384
        with self.assertRaisesRegex(ValueError,'No dialogue end found'):
            checked(rom,self.profile)

    def test_event_opcodes_flags_destinations_and_unknown_pointers_stay_protected(self):
        for offset in (0,1,5,8,9,10,11,12):
            with self.subTest(offset=offset):
                rom=self.rom();self.move(rom);rom.data[self.start+offset]^=1
                with self.assertRaisesRegex(ValueError,'event layout differs'):
                    checked(rom,self.profile)
        rom=self.rom();self.move(rom,address=self.start+8)
        with self.assertRaisesRegex(ValueError,'event layout differs'):
            checked(rom,self.profile)

    def test_existing_editable_operands_and_actual_snapshots_are_preserved(self):
        rom=self.rom();self.move(rom)
        previous=checked(rom,self.profile)
        rom.data[self.start+6:self.start+8]=b'\x03\x00'
        current=checked(rom,self.profile)
        self.assertNotEqual(previous,current)
        self.assertEqual(current[6:8],b'\x03\x00')
        self.move(rom,pointer=0x600000)
        self.assertNotEqual(checked(rom,self.profile),current)

    def test_profiles_without_dialogue_metadata_keep_original_behavior(self):
        self.profile.pop('dialogues');rom=self.rom()
        self.assertEqual(checked(rom,self.profile),self.raw)
        self.move(rom)
        with self.assertRaisesRegex(ValueError,'event layout differs'):
            checked(rom,self.profile)

    def test_recruitment_and_objective_opcode_guards_remain_enforced(self):
        rom=self.rom();self.move(rom)
        self.profile['switches']=[{'address':self.start,'original':self.raw[:5].hex()}]
        with self.assertRaisesRegex(ValueError,'recruitment command was changed'):
            checked(rom,self.profile)
        self.profile.pop('switches');self.profile['objectives']=[self.start]
        with self.assertRaisesRegex(ValueError,'objective command has an unsupported opcode'):
            checked(rom,self.profile)

    def test_prologue_metadata_survives_shared_profile_selection(self):
        self.profile_patch.stop()
        from dialogue import catalogue
        profile=profiles()[(0x108000,416)]
        self.assertEqual(profile['hash'],'581c35b3370408fa43b14c82b3a9ef29b17888ff50b1d3ad4754b7fccac58a80')
        self.assertEqual([at for at,_ in profile['dialogues']],
                         [0x108116,0x108127,0x108137,0x108143])
        known={e['address'] for e in catalogue()['entries']}
        for address,reference in profile['dialogues']:
            self.assertIn(address,known)
            self.assertEqual(len(bytes.fromhex(reference)),3)
            self.assertTrue(profile['start']<=address<address+3<=profile['start']+profile['length'])
            for at,size in profile['masks']:
                self.assertFalse(set(range(at,at+size)) & set(range(address-profile['start'],address-profile['start']+3)))
