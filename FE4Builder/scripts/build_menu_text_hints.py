"""Optional research tool: attach text hints only to identical public artwork.

Requires a local Project Naga source checkout and a reference ROM for its font
and pointer tables. No font/ROM bytes are included in the output. I and lowercase
l have identical artwork in this font; hash-bound reference hints resolve them.
New edits retain their exact spelling in the private ROM text directory.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B / 'src'))
from rom import Rom
from menu_text import MenuFont, MenuText, catalogue, reference_hints
import menu_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True, type=Path)
    parser.add_argument('--reference', required=True, type=Path)
    args = parser.parse_args()
    rom = Rom(args.rom)
    font = MenuFont(rom)
    # Never let a previous generated hint affect the research decoder.
    reference_hints.cache_clear()
    menu_text.reference_hints = lambda: {}
    mirrors = {}
    for name in ('Item_Names.asm', 'Class_Names.asm'):
        source = (args.reference / 'Dialogue' / 'Others' / name).read_text(encoding='utf-8-sig')
        for address, text in re.findall(r'\*\s*=\s*\$([0-9A-Fa-f]+).*?\.text\s+"([^"]*)"', source, re.S):
            mirrors[int(address, 16)] = text
    assets = [(0x546000, 'Statuses.2bpp'), (0x547000, 'Skill_Types.2bpp'),
              (0x568000, 'Classes.2bpp'), (0x572000, 'Items.2bpp'),
              (0x580000, 'Terrain.2bpp'), (0x584000, 'Locations.2bpp'),
              (0x594000, 'Skills.2bpp'), (0x5A0000, 'Item_Desc.2bpp')]
    assets = [(at, (args.reference / 'MenuText' / name).read_bytes()) for at, name in assets]
    hints = {}
    def body(rows):
        columns = [sum((rows[y][x] == 2) << y for y in range(16)) for x in range(len(rows[0]))]
        while columns and not columns[-1]: columns.pop()
        return columns
    for entry in catalogue()['entries']:
        if entry['kind'] == 'encoded':
            continue
        model = MenuText(rom, entry, font)
        art = model.artwork[0]
        if not any(at <= art.pointer and art.pointer + len(art.raw) <= at + len(raw)
                   and raw[art.pointer - at:art.pointer - at + len(art.raw)] == art.raw for at, raw in assets):
            continue
        if model.text is None:
            continue
        text = model.text.replace('I', 'l')
        if entry['category'] in ('Item names', 'Class names'):
            low, high = (0x506700, 0x506DE0) if entry['category'] == 'Item names' else (0x506200, 0x506670)
            candidates = [text for at, text in mirrors.items() if low <= at < high]
            target = body(model.original_rows)
            for candidate in candidates:
                try: rendered = font.render_line(candidate)
                except ValueError: continue
                if body(rendered) == target:
                    text = candidate
                    break
        text = re.sub(r'\blf\b', 'If', text)
        text = re.sub(r'\blnhibits\b', 'Inhibits', text)
        text = re.sub(r'\blsaach\b', 'Isaach', text)
        if entry['category'] == 'Status names':
            text = ['Healthy', 'Cured', 'Freelance', 'Captive', 'Silence', 'Sleep', 'Berserk'][entry['id']]
        if entry['category'] == 'Skill types':
            text = ['Personal skill', 'Class skill'][entry['id']]
        hints[str(entry['key'])] = dict(sha256=hashlib.sha256(art.raw).hexdigest(), text=text)
    (B / 'data' / 'menu_text_hints.json').write_text(json.dumps(hints, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(hints)} hash-bound hints; unrecognized/custom artwork uses ROM-font recognition.')


if __name__ == '__main__':
    main()
