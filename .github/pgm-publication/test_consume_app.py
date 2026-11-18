import hashlib
import io
import json
import tarfile
import unittest

from consume_app import COMPONENT, validate


class ConsumerTests(unittest.TestCase):
    def archive(self, tamper=False, extra=False, traversal=False, bad_mode=False):
        files = {COMPONENT + '/config.yaml': b'slug: private_git_manager\nversion: 0.17.3\narch: [amd64, aarch64]\n',
                 COMPONENT + '/Dockerfile': b'FROM scratch',
                 COMPONENT + '/requirements.txt': b'fixture',
                 COMPONENT + '/__init__.py': b'# fixture'}
        receipt = {'source_sha': 'a'*40, 'main_files': {p: {'sha256': hashlib.sha256(data).hexdigest(),
                    'mode': 0o4755 if bad_mode else 0o644} for p, data in files.items()}}
        if tamper:
            files[COMPONENT + '/__init__.py'] = b'changed'
        if extra:
            files[COMPONENT + '/extra.py'] = b'not in receipt'
        if traversal:
            files[COMPONENT + '/../other/file'] = b'escape'
        files['.publication/pgm.json'] = json.dumps(receipt).encode()
        files['custom_components/other/file.py'] = b'not imported or copied'
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w:gz') as archive:
            for name, data in files.items():
                entry = tarfile.TarInfo('root/' + name)
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
        return raw.getvalue()

    def test_only_component_and_verified_origin(self):
        record, files, version = validate(self.archive())
        self.assertEqual(version, '0.17.3')
        self.assertEqual(record['source_sha'], 'a'*40)
        self.assertEqual(len(files), 4)
        self.assertTrue(all(x.startswith(COMPONENT + '/') for x in files))

    def test_altered_bytes_and_unlisted_files_rejected(self):
        for case in ('tamper', 'extra', 'traversal', 'bad_mode'):
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate(self.archive(**{case: True}))


if __name__ == '__main__':
    unittest.main()
