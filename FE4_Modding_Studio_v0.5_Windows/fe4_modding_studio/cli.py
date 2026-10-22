#!/usr/bin/env python3
"""Optional command-line interface; GUI is studio.py."""
import argparse
from core import ROM

def main():
    p=argparse.ArgumentParser(description='FE4 Portrait Studio CLI')
    p.add_argument('rom');s=p.add_subparsers(dest='command',required=True)
    s.add_parser('inspect')
    x=s.add_parser('export');x.add_argument('slot',type=lambda v:int(v,16));x.add_argument('png')
    x=s.add_parser('import');x.add_argument('slot',type=lambda v:int(v,16));x.add_argument('png');x.add_argument('output');x.add_argument('--quantize',action='store_true');x.add_argument('--reserve',help='Owned, unused headerless hex range, e.g. 690000-698000')
    a=p.parse_args();r=ROM(a.rom)
    if a.command=='inspect':
        print(f'{len(r.data)} ROM bytes; {len(r.header)} header bytes; ExHiROM={r.exhirom}; SHA256={r.sha256}')
        for q in r.portraits:print(f'{q.id:02X}: graphics {q.gfx:06X}, palette {q.pal:06X}, compressed source {len(q.touched)} bytes')
    elif a.command=='export':r.image(a.slot).save(a.png,transparency=0)
    else:
        if a.reserve:r.reserve(*[int(v,16) for v in a.reserve.split('-')])
        _,notice=r.import_png(a.slot,a.png,a.quantize);print(notice)
        for line in r.save(a.output):print(line)
if __name__=='__main__':main()
