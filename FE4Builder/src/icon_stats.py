"""First-open icon baselines and persistent optimization preferences per ROM."""
import json
import os
from pathlib import Path
import tempfile
from rom import DATA_DIR


def valid_sizes(value):
    return (isinstance(value, dict) and set(value) == {'items', 'skills', 'loaded'} and
            all(type(v) is int for v in value.values()) and 0 <= value['items'] <= 120 and
            0 <= value['skills'] <= 32 and value['loaded'] in (19456, 20480))


class IconSizeHistory:
    def __init__(self, document, path=None):
        self.path = Path(path) if path is not None else DATA_DIR / 'icon-sizes.json'
        identity = str(document.rom.path.resolve())
        self.identity = identity.casefold() if os.name == 'nt' else identity
        self.original = document.baseline or document.sizes_original()
        self.optimize = False
        self.report_shown = False
        self.error = None
        try:
            config = self.read()
            entry = config['roms'].get(self.identity)
            if entry is not None:
                if (not isinstance(entry, dict) or not valid_sizes(entry.get('original')) or
                        type(entry.get('optimize')) is not bool or type(entry.get('report_shown')) is not bool):
                    raise ValueError('Invalid original icon size record; existing configuration was preserved.')
                self.original = entry['original']
                self.optimize = entry['optimize']
                self.report_shown = entry['report_shown']
            else:self.save()
        except (OSError, ValueError, TypeError) as exc:self.error = str(exc)

    def read(self):
        try:config = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:return {'version': 1, 'roms': {}}
        if not isinstance(config, dict) or config.get('version') != 1 or not isinstance(config.get('roms'), dict):
            raise ValueError('Unsupported icon size configuration; existing contents were preserved.')
        return config

    def save(self):
        if self.error:return
        config = self.read()
        config['roms'][self.identity] = dict(original=self.original, optimize=self.optimize, report_shown=self.report_shown)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix='icon-sizes-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if Path(temporary).exists():Path(temporary).unlink()

    def update(self, optimize, report_shown=None):
        self.optimize = optimize
        if report_shown is not None:self.report_shown = report_shown
        try:self.save()
        except (OSError, ValueError) as exc:self.error = str(exc)


def artwork_bytes(sizes):
    return (sizes['items'] + sizes['skills']) * 128


def report(original, current, projected):
    return (f'Original icon artwork: {artwork_bytes(original):,} bytes\n'
            f'Current icon artwork: {artwork_bytes(current):,} bytes\n'
            f'New icon artwork: {artwork_bytes(projected):,} bytes\n'
            f'Total artwork saved since original: {artwork_bytes(original) - artwork_bytes(projected):+,} bytes\n'
            f'This optimization frees: {artwork_bytes(current) - artwork_bytes(projected):,} bytes of icon slots\n'
            f'Loaded graphics sheets: {projected["loaded"]:,} bytes\n\n'
            'Each icon uses 128 bytes. Identical whole icons can share one slot.\n'
            'Unused artwork is retained unless it is an exact duplicate. Fixed DMA\n'
            'sheets and the ROM file do not shrink. An expanded skill sheet can\n'
            'return to its original size when the packed artwork fits 24 slots.')
