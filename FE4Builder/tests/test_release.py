"""Release integrity and clean-room startup checks; no ROM fixture required."""
import hashlib,importlib.util,json,subprocess,sys,tarfile,tempfile,unittest,zipfile
from pathlib import Path
B=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_builder',B/'scripts/build_release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ReleaseTests(unittest.TestCase):
    def test_allowlist_manifest_privacy_and_platform_launchers(self):
        for platform in ('Windows','Linux'):
            files=release.payload(platform);manifest=json.loads(files['RELEASE.json'])
            for name,expected in manifest['files'].items():self.assertEqual(hashlib.sha256(files[name]).hexdigest(),expected)
            self.assertEqual(set(manifest['files'])|{'RELEASE.json'},set(files))
            for name in files:
                self.assertFalse(any(part in name.lower() for part in ('research/','__pycache__','audio-cache','rom-selector.json','ui-state.json','emulator.json')))
                self.assertNotIn(Path(name).suffix.lower(),('.sfc','.smc','.gba','.state','.srm','.sav','.lnk'))
                self.assertFalse(name.startswith('/') or '..' in Path(name).parts)
            self.assertIn('Nightmare Modules/FE4 Nightmare modules/Character Editors/FE4 1st Gen Character Editor.nmm',files)
            if platform=='Windows':self.assertIn('FE4Builder/vendor/snes9x/snes9x_libretro.dll',files)
            else:
                self.assertFalse(any(name.endswith('.dll') for name in files));self.assertTrue(files['Launcher'].startswith(b'#!/bin/sh\n'));self.assertNotIn(b'\r',files['Launcher'])
    def test_archive_extraction_and_clean_source_startup(self):
        with tempfile.TemporaryDirectory(dir=B/'tests',prefix='release smoke ') as temporary:
            folder=Path(temporary);archives=release.build(folder/'out')
            for archive in archives:
                destination=folder/('Linux test' if archive.suffix=='.gz' else 'Windows test');destination.mkdir()
                if archive.suffix=='.zip':
                    with zipfile.ZipFile(archive) as handle:handle.extractall(destination)
                else:
                    with tarfile.open(archive) as handle:
                        self.assertEqual(next(member for member in handle.getmembers() if member.name.endswith('/Launcher')).mode,0o755)
                        handle.extractall(destination)
                root=next(destination.iterdir())
                code="""import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('FE4Builder/src').resolve()))
from rom import character_modules,class_modules,category_modules,EDITOR_CATEGORIES,MODULES,load_module
from FE4Builder import App
for p in MODULES.rglob('*.nmm'):load_module(p)
assert character_modules() and class_modules()
for category in EDITOR_CATEGORIES:category_modules(category)
app=App();app.withdraw();app.update_idletasks();assert app.rom is None;app.destroy()
print('Clean source startup OK')
"""
                result=subprocess.run([sys.executable,'-c',code],cwd=root,capture_output=True,text=True,timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('Clean source startup OK',result.stdout)
