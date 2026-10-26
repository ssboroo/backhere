"""Local data and safe target handling. No network or third-party packages."""
import json
import os
import sqlite3
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit


def target_kind(target):
    target = target.strip()
    if not target or '\x00' in target:
        raise ValueError('Empty or invalid target')
    parsed = urlsplit(target)
    if parsed.scheme.lower() in ('https', 'http'):
        if not parsed.hostname:
            raise ValueError('URL requires a hostname')
        return 'url'
    if parsed.scheme and not (len(parsed.scheme) == 1 and target[1:3] in (':\\', ':/')):
        raise ValueError('Use HTTPS/HTTP or an absolute file path')
    if not (os.path.isabs(target) or (len(target) > 2 and target[1:3] in (':\\', ':/')) or target.startswith('\\\\')):
        raise ValueError('Use an absolute file path')
    return 'file'


def open_target(target, position=''):
    if target_kind(target) == 'url':
        if position.isdecimal():
            target = target.split('#')[0] + '#page=' + position
        webbrowser.open(target)
    else:
        # Deliberately never run a shell command or execute executable/script files.
        if not Path(target).exists():
            raise FileNotFoundError(target)
        if Path(target).suffix.lower() in {'.exe', '.com', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.msi', '.scr', '.lnk', '.url', '.hta', '.wsf', '.reg'}:
            raise ValueError('Executable files are not supported as bookmarks')
        os.startfile(target)


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS spots (id TEXT PRIMARY KEY, title TEXT NOT NULL, target TEXT NOT NULL, note TEXT NOT NULL, project TEXT NOT NULL, position TEXT NOT NULL, created REAL NOT NULL, done INTEGER NOT NULL, pinned INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.db.commit()

    def setting(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, value))

    def all(self):
        self.db.row_factory = sqlite3.Row
        return [dict(row) for row in self.db.execute('SELECT * FROM spots ORDER BY created DESC')]

    @staticmethod
    def validate(item):
        for key, maximum in [('title', 160), ('target', 2048), ('note', 4000), ('project', 80), ('position', 160)]:
            if not isinstance(item.get(key), str) or len(item[key]) > maximum:
                raise ValueError('Invalid field: ' + key)
        if not item['title'].strip() or not item['note'].strip():
            raise ValueError('Title and note are required')
        target_kind(item['target'])
        if not isinstance(item.get('id'), str) or not item['id'] or len(item['id']) > 100:
            raise ValueError('Invalid ID')
        if not isinstance(item.get('created'), (float, int)) or not 0 <= item['created'] <= 8640000000000:
            raise ValueError('Invalid timestamp')
        if item.get('done') not in (0, 1, False, True) or item.get('pinned') not in (0, 1, False, True):
            raise ValueError('Invalid flags')

    def save(self, fields, existing=None):
        item = dict(fields)
        item.update(id=existing['id'] if existing else str(uuid.uuid4()), created=existing['created'] if existing else time.time(), done=existing['done'] if existing else 0, pinned=existing['pinned'] if existing else 0)
        self.validate(item)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO spots VALUES (:id,:title,:target,:note,:project,:position,:created,:done,:pinned)', item)
        return item

    def flag(self, item_id, field, value):
        if field not in ('done', 'pinned'):
            raise ValueError('Invalid field')
        with self.db:
            self.db.execute('UPDATE spots SET '+field+'=? WHERE id=?', (int(bool(value)), item_id))

    def delete(self, item_id):
        with self.db:
            self.db.execute('DELETE FROM spots WHERE id=? AND done=1', (item_id,))

    def export(self, path):
        # Atomic output avoids leaving a partial backup after interruption.
        output = Path(path)
        temporary = output.with_suffix(output.suffix + '.tmp')
        temporary.write_text(json.dumps({'version': 1, 'items': self.all()}, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(output)

    def import_backup(self, path):
        if Path(path).stat().st_size > 10_000_000:
            raise ValueError('Backup too large')
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('items'), list) or len(data['items']) > 10000:
            raise ValueError('Invalid backup')
        for item in data['items']:
            if not isinstance(item, dict):
                raise ValueError('Invalid item')
            self.validate(item)
        before = self.db.total_changes
        with self.db:
            for item in data['items']:
                self.db.execute('INSERT OR IGNORE INTO spots VALUES (:id,:title,:target,:note,:project,:position,:created,:done,:pinned)', item)
        return self.db.total_changes - before

    def close(self):
        self.db.close()
