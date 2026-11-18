import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from check_mirror import inspect_archive
from github_mirror import Mirror, ArchiveRedirect
from urllib.request import Request


class ArchiveTests(unittest.TestCase):
    def archive(self, changes=None, link=None):
        files = {'root/private_git_manager/config.yaml': b'version: "0.17.3"\n',
                 'root/private_git_manager/Dockerfile': b'FROM scratch\n',
                 'root/private_git_manager/app/main.py': b'print("fixture")\n',
                 'root/manifest.toml': b'packaging_format = 2\n',
                 'root/custom_components/pgm_forgejo_backup/manifest.json':
                     json.dumps({'domain': 'pgm_forgejo_backup', 'version': '0.17.3'}).encode()}
        files.update(changes or {})
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode='w:gz') as archive:
            for name, value in files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(value)
                archive.addfile(entry, io.BytesIO(value))
            if link:
                entry = tarfile.TarInfo(link)
                entry.type, entry.linkname = tarfile.SYMTYPE, '/etc/passwd'
                archive.addfile(entry)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'archive.tar.gz'
            path.write_bytes(raw.getvalue())
            return inspect_archive(path)

    def test_valid_distribution(self):
        value = self.archive()
        self.assertEqual(value['app_version'], '0.17.3')
        self.assertEqual(value['app_files'], 3)
        self.assertEqual(value['component_files'], 1)

    def test_traversal_and_multiple_roots(self):
        for name in ('root/../outside', '/absolute', 'another/file', 'root/.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.archive({name: b'x'})

    def test_links_are_rejected(self):
        with self.assertRaises(ValueError):
            self.archive(link='root/private_git_manager/link')

    def test_wrong_component(self):
        with self.assertRaises(ValueError):
            self.archive({'root/custom_components/pgm_forgejo_backup/manifest.json': b'{"domain":"other"}'})

    def test_bad_version(self):
        with self.assertRaises(ValueError):
            self.archive({'root/private_git_manager/config.yaml': b'version: latest'})

    def test_secrets_and_runtime_data_are_rejected(self):
        for path, value in [('keys/key', b'x'), ('data/state.json', b'{}'),
                            ('key', b'-----BEGIN OPENSSH PRIVATE KEY-----')]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.archive({'root/private_git_manager/' + path: value})


class ReaderTests(unittest.TestCase):
    @patch.dict('os.environ', {'MIRROR_READ_TOKEN': 'fixture'})
    def test_other_repository_rejected(self):
        with self.assertRaises(ValueError):
            Mirror('jacksignal')

    @patch.dict('os.environ', {'MIRROR_READ_TOKEN': 'fixture'})
    def test_identity_and_privacy_required(self):
        for update in ({'private': False}, {'id': 1}, {'full_name': 'other/repo'}):
            metadata = {'id': 1463365361, 'full_name': 'Gente-del-Condado/HA-Private-Git-Manager-private', 'private': True}
            metadata.update(update)
            with self.subTest(update=update), patch.object(Mirror, 'request', return_value=metadata), self.assertRaises(ValueError):
                Mirror('HA-Private-Git-Manager-private').verify()

    def test_redirect_drops_authorization(self):
        request = Request('https://api.github.com/repos/a/b/tarball/x', headers={'Authorization': 'Bearer fixture'})
        new = ArchiveRedirect().redirect_request(request, None, 302, 'Found', {}, 'https://codeload.github.com/a/b/legacy.tar.gz/x')
        self.assertIsNone(new.get_header('Authorization'))

    def test_untrusted_redirect_rejected(self):
        with self.assertRaises(ValueError):
            ArchiveRedirect().redirect_request(Request('https://api.github.com/a'), None, 302, 'Found', {}, 'https://other.invalid/a')


if __name__ == '__main__':
    unittest.main()
