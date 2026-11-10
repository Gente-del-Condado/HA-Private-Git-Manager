# Importa el paquete de proveedores sin iniciar Home Assistant.
import sys
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "custom_components/pgm_forgejo_backup")
)
from providers import forgejo, forgejo_releases, github  # noqa: E402


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


@pytest.mark.parametrize("suffix", ["", "/", ".git", ".git/"])
def test_web_url_accepts_clone_suffix_with_yunohost_subpath(suffix):
    url = "https://forgejo.example.test/forgejo/wolfbelmi88/CopiasHA"
    ssh = "ssh://forgejo@forgejo.example.test:2233/wolfbelmi88/CopiasHA.git"
    assert forgejo_releases.validate_web_url(url + suffix, ssh) == url
    with pytest.raises(forgejo_releases.ReleaseError):
        forgejo_releases.validate_web_url(url.replace("CopiasHA", "OtrasCopias"), ssh)


def test_release_check_reports_yunohost_sso_redirect(monkeypatch):
    releases = forgejo_releases.Releases(
        "https://forgejo.example.test/forgejo/user/backups", "test"
    )
    headers = Message()
    headers["Location"] = "https://forgejo.example.test/yunohost/sso/?r=test"

    def redirect(request, **kwargs):
        raise HTTPError(request.full_url, 302, "Found", headers, None)

    monkeypatch.setattr(releases.opener, "open", redirect)
    with pytest.raises(forgejo_releases.SSORequired):
        releases.check()


def test_github_backup_uses_github_readme_links_and_roundtrips(backup_remote, monkeypatch):
    local, source, metadata, git = backup_remote
    provider = github.GitHub("ssh://git@github.com/example/backups.git", "", "")
    monkeypatch.setattr(local, "url", provider.url)
    provider.upload(source, metadata)

    readme = git("show", "main:README.md")
    assert "https://github.com/example/backups/blob/pgm-meta-fixture/metadata.json" in readme
    assert "https://github.com/example/backups/archive/refs/tags/pgm-data-fixture.zip" in readme
    assert provider.list() == [metadata]
    destination = source.with_name("download.tar")
    provider.download("fixture", destination)
    assert destination.read_bytes() == source.read_bytes()
    provider.delete("fixture")
    assert provider.list() == []
    assert "pgm-data-fixture.zip" not in git("show", "main:README.md")


def test_github_release_sends_raw_file_to_official_upload_host(tmp_path, monkeypatch):
    releases = github.GitHubReleases("https://github.com/example/backups", "fixture")
    source = tmp_path / "backup.tar"
    source.write_bytes(b"tar-fixture")

    def request(method, path, *, base, body, headers):
        assert method == "POST"
        assert base == "https://uploads.github.com/repos/example/backups"
        assert path == "/releases/42/assets?name=backup.tar"
        assert headers == {"Content-Type": "application/octet-stream", "Content-Length": "11"}
        assert body.read() == b"tar-fixture"

    monkeypatch.setattr(releases, "_request", request)
    releases._upload_asset(42, source, 11)
    assert releases.repo == "https://api.github.com/repos/example/backups"
    assert releases._asset_path(42, 7) == "/releases/assets/7"


def test_github_urls_and_size_limit():
    ssh = github.normalize_ssh_url("git@github.com:example/backups.git")
    assert ssh == "ssh://git@github.com/example/backups.git"
    assert github.is_github(ssh)
    assert github.validate_github_web_url("https://github.com/example/backups.git", ssh) == (
        "https://github.com/example/backups"
    )
    with pytest.raises(forgejo_releases.ReleaseError):
        github.validate_github_web_url("https://other.example/example/backups", ssh)
    provider = github.GitHub(ssh, "", "")
    with pytest.raises(forgejo.ForgejoError, match="1900 MiB"):
        provider.upload(None, {"backup_id": "too_large", "size": 2 * 1024**3, "protected": True})
