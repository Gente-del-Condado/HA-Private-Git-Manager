import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import publish_mirror as publisher


class ExportTests(unittest.TestCase):
    def source(self, path, extra=None):
        files = {'private_git_manager/config.yaml': b'version: "0.17.3"\n',
                 'private_git_manager/Dockerfile': b'FROM scratch',
                 'private_git_manager/app/main.py': b'# fixture',
                 'manifest.toml': b'packaging_format=2',
                 'custom_components/pgm_forgejo_backup/manifest.json':
                     b'{"domain":"pgm_forgejo_backup","version":"0.2.0"}'}
        files.update(extra or {})
        with tarfile.open(path, 'w:gz') as archive:
            for name, data in files.items():
                item = tarfile.TarInfo('source/' + name)
                item.size, item.mode = len(data), 0o755 if name.endswith('.py') else 0o644
                archive.addfile(item, io.BytesIO(data))

    def test_export_excludes_private_root_and_workflows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.source(root / 'source.tar.gz', {'private-note.txt': b'private fixture', '.github/workflows/evil.yml': b'x'})
            files = publisher.export(root / 'source.tar.gz', root / 'out')
            self.assertNotIn('private-note.txt', files)
            self.assertNotIn('.github/workflows/evil.yml', files)
            self.assertEqual(files['private_git_manager/app/main.py']['mode'], 0o755)

    def test_unknown_distribution_file_requires_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.source(root / 'source.tar.gz', {'private_git_manager/new.py': b'new'})
            with self.assertRaisesRegex(ValueError, 'Archivo nuevo'):
                publisher.export(root / 'source.tar.gz', root / 'out')

    def test_tampered_transfer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.source(root / 'source.tar.gz')
            files = publisher.export(root / 'source.tar.gz', root / 'main')
            (root / 'receipt.json').write_text(json.dumps({'source_sha': 'a'*40, 'tag_sha': None, 'main_files': files}))
            publisher.verify(root)
            (root / 'main/manifest.toml').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'alterada'):
                publisher.verify(root)

    def test_unknown_file_in_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'secret.txt').write_text('fixture')
            with self.assertRaisesRegex(ValueError, 'ajeno'):
                publisher.inventory(root)

    def test_controller_paths_cannot_enter_allowlist(self):
        with patch.object(publisher, 'CONTROL') as control:
            (control / 'public-files.txt').read_text.return_value = '.github/workflows/other.yml\n'
            with self.assertRaisesRegex(ValueError, 'no autorizada'):
                publisher.allowed()


if __name__ == '__main__':
    unittest.main()
