import importlib.util
from pathlib import Path

import pytest

PROVIDER = (
    Path(__file__).resolve().parents[1]
    / "custom_components/pgm_forgejo_backup/providers/forgejo.py"
)
spec = importlib.util.spec_from_file_location("pgm_forgejo_provider", PROVIDER)
forgejo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(forgejo)


@pytest.fixture
def backup_remote(tmp_path, monkeypatch):
    # Ejecuta los comandos Git reales, con un repositorio bare local como destino aislado.
    original_run = forgejo._run
    provider = forgejo.Forgejo("ssh://git@example.test/team/backups.git", "", "")
    remote = tmp_path / "remote.git"
    original_run(["git", "init", "--bare", "--initial-branch=main", str(remote)])

    def local_run(args, **kwargs):
        args = [str(remote) if value == provider.url else value for value in args]
        if "env" in kwargs:
            kwargs["env"] = {**kwargs["env"], "GIT_ALLOW_PROTOCOL": "file"}
        return original_run(args, **kwargs)

    monkeypatch.setattr(forgejo, "_run", local_run)

    def git(*args):
        return original_run(["git", "--git-dir", str(remote), *args]).decode().strip()

    source = tmp_path / "backup.tar"
    source.write_bytes(b"fixture for Git transport")
    metadata = {"backup_id": "fixture", "protected": True, "size": source.stat().st_size}
    return provider, source, metadata, git


def test_first_backup_creates_browsable_main_and_repairs_tag_only_remote(backup_remote):
    provider, source, metadata, git = backup_remote
    provider.upload(source, metadata)
    assert "Copias de seguridad de Home Assistant" in git("show", "main:README.md")
    tags = git("show-ref", "--tags")
    assert provider.list() == [metadata]

    git("update-ref", "-d", "refs/heads/main")
    provider.upload(source, metadata)
    assert "pgm-data-" in git("show", "main:README.md")
    assert git("show-ref", "--tags") == tags
    assert provider.list() == [metadata]


def test_backup_preserves_existing_repository_branch(backup_remote):
    provider, source, metadata, git = backup_remote
    provider.upload(source, metadata)
    original = git("rev-parse", "refs/heads/main")
    git("update-ref", "refs/heads/manual", original)
    git("update-ref", "-d", "refs/heads/main")
    newer = {**metadata, "backup_id": "second"}
    provider.upload(source, newer)
    assert git("for-each-ref", "--format=%(refname)", "refs/heads") == "refs/heads/manual"
    assert git("rev-parse", "refs/heads/manual") == original
    assert provider.get("second") == newer
