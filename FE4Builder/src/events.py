"""Read-only event inspection. Source annotations are never treated as a decoder."""
import hashlib,json
from functools import lru_cache
from rom import DATA_DIR
from portraits import pc_address

CHAPTERS=['Prologue']+[f'Chapter {i}' for i in range(1,11)]+['Final Chapter']

@lru_cache(maxsize=1)
def catalogue():
    return json.loads((DATA_DIR/'events.json').read_text(encoding='utf-8'))

def inspect(rom,entry,trigger=False):
    start=entry['start'];pointer=None
    if not trigger:
        at=0xfe8bf+entry['id']*3+rom.header
        if at+3>len(rom.data):raise ValueError('Event pointer table is outside this ROM.')
        pointer=int.from_bytes(rom.data[at:at+3],'little')
        start=pc_address(pointer)
    at=start+rom.header;size=entry['length']
    if at<rom.header or at+size>len(rom.data):raise ValueError('Event data is outside this ROM.')
    raw=bytes(rom.data[at:at+size])
    matches=start==entry['start'] and hashlib.sha256(raw).hexdigest()==entry['hash']
    return dict(start=start,pointer=pointer,raw=raw,matches=matches)

def hex_dump(raw,start):
    return '\n'.join(f'{start+i:06X}  '+raw[i:i+16].hex(' ').upper() for i in range(0,len(raw),16))
