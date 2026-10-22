"""Shared structural checks for edits made by the linked event editors."""
import hashlib,json
from functools import lru_cache
from rom import DATA_DIR

@lru_cache(maxsize=1)
def profiles():
    data=json.loads((DATA_DIR/'conversations.json').read_text(encoding='utf-8'))
    result={(p['start'],p['length']):p for p in data['profiles']}
    objectives=json.loads((DATA_DIR/'objectives.json').read_text(encoding='utf-8'))
    result.update({(p['start'],p['length']):p for p in objectives['profiles']})
    commands=json.loads((DATA_DIR/'event_commands.json').read_text(encoding='utf-8'))
    result.update({(p['start'],p['length']):p for p in commands['profiles']})
    return result

def checked(rom,profile):
    profile=profiles().get((profile['start'],profile['length']),profile)
    start=profile['start']+rom.header;end=start+profile['length']
    if start<rom.header or end>len(rom.data):raise ValueError('Event data is outside this ROM.')
    raw=bytes(rom.data[start:end]);masked=bytearray(raw)
    for address in profile.get('objectives',[]):
        if raw[address-profile['start']] not in (2,0x0f):raise ValueError('An objective command has an unsupported opcode.')
    for switch in profile.get('switches',[]):
        at=switch['address']-profile['start'];command=raw[at:at+5]
        if command not in (bytes.fromhex(switch['original']),b'\xfd'*5):
            raise ValueError('A recruitment command was changed by another tool. Its layout is unsupported.')
    for at,size in profile['masks']:masked[at:at+size]=bytes(size)
    if hashlib.sha256(masked).hexdigest()!=profile['hash']:
        raise ValueError('This event layout differs from the supported reference. Editing is disabled to preserve custom code.')
    return raw
