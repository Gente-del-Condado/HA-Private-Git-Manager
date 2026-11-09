# Importa el paquete de proveedores sin iniciar Home Assistant.
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components/pgm_forgejo_backup")
)
from providers import forgejo  # noqa: E402


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


def test_readme_index_updates_on_upload_and_delete(backup_remote):
    provider, source, metadata, git = backup_remote
    old = {**metadata, "name": "Vieja", "date": "2026-11-08T18:00:00+01:00"}
    new = {**metadata, "backup_id": "second", "name": "Nueva | [1]", "date": "2026-11-09T09:00:00Z"}
    provider.upload(source, old)
    provider.upload(source, new)
    readme = git("show", "main:README.md")
    assert readme.index("Nueva") < readme.index("Vieja")
    assert "Nueva &#124; &#91;1&#93;" in readme
    assert "2026-11-08 17:00:00" in readme
    assert "(../../../src/tag/pgm-meta-second/metadata.json)" in readme
    assert "(../../../archive/pgm-data-second.zip)" in readme

    provider.delete("second")
    readme = git("show", "main:README.md")
    assert "pgm-data-second.zip" not in readme
    assert "Vieja" in readme
    provider.delete("fixture")
    assert "Todavía no hay copias guardadas" in git("show", "main:README.md")


def test_failed_direct_upload_keeps_recoverable_git_copy(backup_remote):
    provider, source, metadata, git = backup_remote

    class UnavailableReleases:
        def upload(self, *args):
            raise forgejo.ReleaseError("Forgejo rechazó el adjunto.")

        def available(self, *args):
            return False

    provider.releases = UnavailableReleases()
    provider.upload(source, metadata)
    assert provider.get("fixture") == metadata
    target = source.with_name("restored.tar")
    provider.download("fixture", target)
    assert target.read_bytes() == source.read_bytes()
    readme = git("show", "main:README.md")
    assert "Descargar backup.tar" not in readme
    assert "Descargar ZIP" in readme


def test_readme_uses_home_assistant_zone_and_orders_the_repeated_hour(backup_remote):
    provider, source, metadata, git = backup_remote
    provider.time_zone = ZoneInfo("Europe/Madrid")
    summer = {**metadata, "name": "Verano", "date": "2026-10-25T00:45:00Z"}
    winter = {**metadata, "backup_id": "second", "name": "Invierno", "date": "2026-10-25T01:15:00Z"}
    provider.upload(source, summer)
    provider.upload(source, winter)

    readme = git("show", "main:README.md")
    assert "Fecha (Europe/Madrid)" in readme
    first = readme.index("2026-10-25 02:15:00+01:00 | Invierno")
    second = readme.index("2026-10-25 02:45:00+02:00 | Verano")
    assert first < second
