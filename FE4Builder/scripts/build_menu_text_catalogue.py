"""Build the ROM-free Project Naga menu-text layout catalogue."""
from pathlib import Path
import json
import sys

B = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(B / 'src'))
from menu_text import SKILL_IDS


def build():
    entries = []

    def table(category, count, base, pool, variants, kind='name'):
        for i in range(count):
            entry = dict(key=len(entries), category=category, id=i, kind=kind,
                         table=base + i * 16, pool=pool, variants=variants)
            entries.append(entry)

    table('Item names', 138, 0x504000, [0x572000, 0x580000],
          [[0, 1, 'left'], [4, 5, 'right']])
    table('Item descriptions', 138, 0x507000, [0x5A0000, 0x5B0000], [[0, 1, 'left']], kind='description')
    # The first 25 description images are composed dynamically from item traits.
    for i in range(25):
        entries.append(dict(key=len(entries), category='Item effect descriptions', id=i,
                            kind='effect', graphics=0x5A0000 + i * 512))
    for slot, skill in enumerate(SKILL_IDS):
        entries.append(dict(key=len(entries), category='Skills', id=skill, kind='skill',
                            slot=slot, pointer=0x9AC5C + skill * 3, pool=[0x594000, 0x59D000]))
    table('Class names', 72, 0x502400, [0x568000, 0x571000], [[0, 1, 'left']])
    table('Terrain names', 26, 0x503000, [0x580000, 0x583400], [[0, 1, 'left']])
    table('Status names', 7, 0x503F00, [0x546000, 0x546E00], [[0, 1, 'left']])
    table('Skill types', 2, 0x502900, [0x547000, 0x547400], [[0, 1, 'left']])
    table('Locations — map', 46, 0x503200, [0x584000, 0x590000],
          [[0, 1, 'left'], [4, 5, 'center'], [8, 9, 'right']])
    table('Locations — menus', 55, 0x505000, [0x584000, 0x590000],
          [[0, 1, 'left'], [4, 5, 'center']])
    # These are dense, separate message-name IDs, NOT item/class record IDs.
    # For example item 1C (Iron lance) uses the message list's entry 1A.
    for category, count, base in (('Item names — messages', 110, 0x506700),
                                  ('Class names — messages', 71, 0x506200)):
        for i in range(count):
            entries.append(dict(key=len(entries), category=category, id=i,
                                kind='encoded', address=base + i * 16))
    result = dict(profile='Project Naga beta 7', source={
        'repository': 'https://github.com/Miacidae/Project-Naga-beta-v7',
        'commit': '8924fb4ff5330b347074083736ada17940b677a5',
        'files': ['MenuText/_MenuTextInstaller.asm', 'MenuText/Tilemaps/Items.asm',
                  'MenuText/Tilemaps/Classes.asm', 'MenuText/Tilemaps/Terrains.asm',
                  'MenuText/Tilemaps/Locations.asm', 'MenuText/Tilemaps/Statuses.asm',
                  'MenuText/Tilemaps/Skills_Menu.asm', 'Dialogue/Others/Item_Names.asm',
                  'Dialogue/Others/Class_Names.asm'],
        'note': 'Description and skill pointer tables also traced in the supplied ROM. Labels are read from ROM artwork, not the source translation.'},
        entries=entries)
    target = B / 'data' / 'menu_text.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{len(entries)} menu text entries in {target}')


if __name__ == '__main__':
    build()
