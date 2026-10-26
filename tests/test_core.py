import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from core import Store, target_kind, open_target


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.store = Store(self.path / 'data.db')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def item(self):
        return self.store.save(dict(title='Монгол ажил', target='https://example.com/report.pdf', note='3-р багана шалга', project='Rainy', position='12'))

    def test_save_reopen_edit_and_complete(self):
        item = self.item()
        self.store.close()
        self.store = Store(self.path / 'data.db')
        self.assertEqual(self.store.all()[0]['note'], '3-р багана шалга')
        self.store.flag(item['id'], 'done', True)
        self.store.flag(item['id'], 'pinned', True)
        saved = self.store.all()[0]
        edited = self.store.save({**saved, 'note': 'Шинэ алхам'}, saved)
        self.assertEqual(edited['created'], item['created'])
        self.assertEqual(edited['done'], 1)
        self.store.flag(item['id'], 'done', False)
        self.store.delete(item['id'])
        self.assertEqual(len(self.store.all()), 1)

    def test_backup_merges_without_overwriting_and_validates_atomically(self):
        item = self.item()
        backup = self.path / 'backup.json'
        self.store.export(backup)
        self.assertEqual(self.store.import_backup(backup), 0)
        self.store.flag(item['id'], 'done', True)
        self.store.delete(item['id'])
        self.assertEqual(self.store.import_backup(backup), 1)
        data = json.loads(backup.read_text('utf-8'))
        valid = {**data['items'][0], 'id': 'second'}
        data['items'] = [valid, {**valid, 'id': 'third', 'target': 'javascript:evil()'}]
        backup.write_text(json.dumps(data), 'utf-8')
        with self.assertRaises(ValueError):
            self.store.import_backup(backup)
        self.assertEqual(len(self.store.all()), 1)

    def test_reject_protocol_execution_and_relative_paths(self):
        for value in ['javascript:alert(1)', 'data:text/html,hi', 'shell:AppsFolder', 'https://', 'report.pdf', '']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                target_kind(value)
        self.assertEqual(target_kind('C:\\Work\\report.xlsx'), 'file')
        self.assertEqual(target_kind('https://example.com'), 'url')
        script = self.path / 'unsafe.cmd'
        script.write_text('echo never execute')
        with self.assertRaises(ValueError):
            open_target(str(script))

    def test_pdf_page(self):
        with patch('core.webbrowser.open') as opener:
            open_target('https://example.com/report.pdf#old', '12')
            opener.assert_called_once_with('https://example.com/report.pdf#page=12')

    def test_all_languages_complete(self):
        data = json.loads((Path(__file__).resolve().parents[1] / 'desktop/locales.json').read_text('utf-8'))
        self.assertEqual(len(data['rows']), 12)
        for code, row in data['rows'].items():
            self.assertEqual(len(row), len(data['keys']), code)
            self.assertTrue(all(isinstance(s, str) and s.strip() for s in row))


if __name__ == '__main__':
    unittest.main()
