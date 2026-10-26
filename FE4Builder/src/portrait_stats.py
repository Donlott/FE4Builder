"""Persistent, per-ROM portrait graphics baselines and shared-byte accounting."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from portrait_document import COUNT
from rom import DATA_DIR


@dataclass(frozen=True)
class GraphicsSizes:
    per_portrait: tuple
    total: int

    def record(self):
        return {'per_portrait': list(self.per_portrait), 'total': self.total}

    @classmethod
    def from_record(cls, record):
        values, total = record['per_portrait'], record['total']
        if (not isinstance(values, list) or len(values) != COUNT
                or any(type(value) is not int or value <= 0 for value in values)
                or type(total) is not int or not max(values) <= total <= sum(values)):
            raise ValueError('Invalid portrait size baseline.')
        return cls(tuple(values), total)


def current_sizes(document):
    # Compressed lookback dependencies and aliases can overlap: count each byte
    # once across the entire ROM, while retaining each slot's complete read set.
    used = set()
    for portrait in document.portraits:
        used.update(portrait.touched)
    return GraphicsSizes(tuple(len(p.touched) for p in document.portraits), len(used))


def optimized_sizes(document):
    streams = {}
    sizes = []
    for portrait in document.portraits:
        raw = document.pending.get(portrait.id, (portrait.raw, portrait.palette))[0]
        if raw not in streams:
            streams[raw] = len(document.compressed_graphics(raw))
        sizes.append(streams[raw])
    return GraphicsSizes(tuple(sizes), sum(streams.values()))


class PortraitSizeHistory:
    """Never replace an existing baseline with a later optimized ROM's sizes."""
    def __init__(self, document, path=None):
        self.path = Path(path) if path is not None else DATA_DIR / 'portrait-sizes.json'
        identity = str(document.path.resolve())
        self.identity = identity.casefold() if os.name == 'nt' else identity
        self.original = current_sizes(document)
        self.report_shown = False
        self.error = None
        try:
            config = self._read()
            record = config['roms'].get(self.identity)
            if record is not None:
                self.original = GraphicsSizes.from_record(record['original'])
                if type(record['optimization_report_shown']) is not bool:
                    raise ValueError('Invalid portrait optimization report setting.')
                self.report_shown = record['optimization_report_shown']
            else:
                config['roms'][self.identity] = self._record()
                self._write(config)
        except (OSError, ValueError, KeyError, TypeError) as error:
            # The UI warns instead of blocking ROM editing or silently replacing
            # a damaged/unreadable config with a new, misleading baseline.
            self.error = str(error)

    def _record(self):
        return {'original': self.original.record(), 'optimization_report_shown': self.report_shown}

    def _read(self):
        try:
            config = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'version': 1, 'roms': {}}
        if (not isinstance(config, dict) or config.get('version') != 1
                or not isinstance(config.get('roms'), dict)):
            raise ValueError('Unsupported portrait size config; existing data was preserved.')
        return config

    def _write(self, config):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix='portrait-sizes-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(config, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()

    def mark_report_shown(self):
        self.report_shown = True
        if self.error is not None:
            return
        try:
            config = self._read()
            # Keep an existing original even if another editor wrote the file.
            record = config['roms'].setdefault(self.identity, self._record())
            record['optimization_report_shown'] = True
            self._write(config)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.error = str(error)
