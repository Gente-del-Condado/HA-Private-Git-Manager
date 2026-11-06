import os
import subprocess

import pytest
import yaml
from app.core import Manager, Problem, endpoint, fingerprint, validate_ref


class FakeSupervisor:
    token = "test"

    def __init__(self):
        self.calls = []
        self.payloads = []
        self.installed = []
        self.fail = None
        self.addons = None

    def call(self, method, path, payload=None):
        self.calls.append((method, path))
        self.payloads.append((method, path, payload))
        if path == self.fail:
            raise Problem("Supervisor simulado no disponible.")
        if method == "POST" and "/local_" in path:
            slug = path.split("/")[3] if path.startswith("/store/") else path.split("/")[2]
            action = path.split("/")[-1]
            app = next((a for a in self.installed if a["slug"] == slug), None)
            if action in {"install", "update", "rebuild"}:
                config = yaml.safe_load(
                    (self.addons / slug.removeprefix("local_") / "config.yaml").read_text()
                )
                if (
                    action == "rebuild"
                    and app
                    and app.get("version") is not None
                    and str(app["version"]) != config["version"]
                ):
                    raise Problem("Supervisor no permite reconstruir otra versión.")
                if not app:
                    app = {"slug": slug, "state": "stopped"}
                    self.installed.append(app)
                app["version"] = config["version"]
                if action == "rebuild":
                    app["state"] = "started"
            elif app and action == "uninstall":
                self.installed.remove(app)
            elif app and action in {"start", "stop"}:
                app["state"] = "started" if action == "start" else "stopped"
        return {"addons": self.installed} if path == "/addons" else {}


@pytest.fixture
def manager(tmp_path):
    result = Manager(tmp_path / "data", tmp_path / "addons", FakeSupervisor())
    result.supervisor.addons = result.addons
    result.verify_checkout = lambda repo, root: (
        None
    )  # Synthetic deployment fixture; real transports test Git integrity.
    return result


def addon(path, version="1.0.0", slug="demo"):
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Demo",
                "version": version,
                "slug": slug,
                "description": "Test",
                "arch": ["aarch64", "amd64"],
            }
        )
    )
    (path / "Dockerfile").write_text("FROM alpine:3.22\n")
    (path / "payload").write_text(version)


def prepared(manager):
    repo_id = manager.repo_add("Demo", "https://example.org/user/repo.git", "main", token="secret")
    root = manager.data / "repos" / repo_id
    addon(root / "demo")
    manager.state["repos"][repo_id].update(commit="a" * 40, apps=manager.discover(root))
    return repo_id, root


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/x",
        "ext::sh -c x",
        "-bad",
        "https://u:token@host/repo",
        "https://token@host/repo",
        "ssh://git@-oops/repo",
        "ssh://git@host:99999/repo",
        "git@host:repo\n-oProxyCommand=x",
        "https://host/repo?token=x",
        "ssh://-bad@host/repo",
        "ssh://git@host/",
    ],
)
def test_reject_dangerous_urls(url):
    with pytest.raises(Problem):
        endpoint(url)


def test_forgejo_and_github_urls():
    assert endpoint("ssh://forgejo@gentedelcondado.es:2233/wolfbelmi88/pivigia.git") == (
        "ssh",
        "gentedelcondado.es",
        2233,
    )
    assert endpoint("git@github.com:user/repo.git") == ("ssh", "github.com", 22)
    assert endpoint("https://github.com/user/repo.git")[0] == "https"


@pytest.mark.parametrize("ref", ["-main", "../main", "main~1", "main;id", "main\n", "refs/../x"])
def test_reject_ref_injection(ref):
    with pytest.raises(Problem):
        validate_ref(ref)


def test_key_lifecycle_and_permissions(manager):
    key = manager.key_create("Forgejo")
    path = manager.data / "keys" / key["id"]
    assert path.stat().st_mode & 0o777 == 0o600
    assert key["public"].startswith("ssh-ed25519 ")
    manager.trust(
        "git@example.org:user/repo.git",
        "example.org " + " ".join(key["public"].split()[:2]),
        fingerprint("example.org " + " ".join(key["public"].split()[:2])),
    )
    repo_id = manager.repo_add("Repo", "git@example.org:user/repo.git", "main", key_id=key["id"])
    with pytest.raises(Problem, match="en uso"):
        manager.key_delete(key["id"])
    manager.repo_delete(repo_id)
    manager.key_delete(key["id"])
    assert not path.exists()


def test_host_requires_matching_fingerprint_and_marker(manager):
    key = manager.key_create("test")
    line = "[example.org]:2233 " + " ".join(key["public"].split()[:2])
    with pytest.raises(Problem):
        manager.trust("ssh://git@example.org:2233/u/r", line, "SHA256:wrong")
    with pytest.raises(Problem):
        manager.trust("ssh://git@other.org:2233/u/r", line, fingerprint(line))
    with pytest.raises(Problem):
        manager.trust("ssh://git@example.org:2233/u/r", "", "")
    manager.trust("ssh://git@example.org:2233/u/r", line, fingerprint(line))
    assert "example.org:2233" in manager.state["hosts"]


def test_secret_redaction_and_persistence(manager):
    repo_id = manager.repo_add("Demo", "https://example.org/u/r", "main", token="top-secret")
    assert "top-secret" not in str(manager.snapshot())
    assert manager.snapshot()["repos"][repo_id]["has_token"]
    assert manager.state_file.stat().st_mode & 0o777 == 0o600
    restored = Manager(manager.data, manager.addons, FakeSupervisor())
    assert restored.state["repos"][repo_id]["token"] == "top-secret"
    env = manager.git_env(manager.repo(repo_id))
    assert env["PGM_TOKEN"] == "top-secret"
    assert env["GIT_ALLOW_PROTOCOL"] == "ssh:https"


def test_detect_nested_and_root_configs(manager, tmp_path):
    addon(tmp_path / "repo" / "nested" / "one")
    assert manager.discover(tmp_path / "repo")[0]["path"] == "nested/one"
    addon(tmp_path / "root", slug="rootapp")
    assert manager.discover(tmp_path / "root")[0]["path"] == "."


def test_duplicate_slug_rejected(manager, tmp_path):
    addon(tmp_path / "r" / "one")
    addon(tmp_path / "r" / "two")
    with pytest.raises(Problem, match="mismo slug"):
        manager.discover(tmp_path / "r")


def test_symlink_never_copied(manager, tmp_path):
    source = tmp_path / "source"
    addon(source)
    (source / "escape").symlink_to("/etc/passwd")
    with pytest.raises(Problem, match="enlaces"):
        manager.safe_copy(source, tmp_path / "target")
    assert not (tmp_path / "target").exists()


def test_install_update_and_commit_tracking(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
    assert manager.state["deployments"]["demo"]["commit"] == "a" * 40
    assert ("POST", "/store/addons/local_demo/install") in manager.supervisor.calls
    manager.supervisor.installed = [{"slug": "local_demo", "version": "1.0.0", "state": "started"}]
    addon(root / "demo", "2.0.0")
    manager.repo(repo_id).update(commit="b" * 40, apps=manager.discover(root))
    manager.deploy(repo_id, "demo", update=True)
    calls = manager.supervisor.calls
    assert calls.index(("POST", "/addons/local_demo/stop")) < calls.index(
        ("POST", "/store/addons/local_demo/update")
    )
    assert manager.supervisor.installed[0]["state"] == "started"
    assert manager.state["deployments"]["demo"]["previous_commit"] == "a" * 40


def test_failure_restores_code_and_records_uncertainty(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    manager.supervisor.installed = [{"slug": "local_demo", "version": "1.0.0", "state": "started"}]
    addon(root / "demo", "2.0.0")
    manager.repo(repo_id).update(commit="b" * 40, apps=manager.discover(root))
    manager.supervisor.fail = "/store/addons/local_demo/update"
    with pytest.raises(Problem):
        manager.deploy(repo_id, "demo", update=True)
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
    assert manager.state["deployments"]["demo"]["commit"] == "a" * 40
    assert manager.state["deployments"]["demo"]["status"] == "error"


def test_first_install_failure_can_retry(manager):
    repo_id, root = prepared(manager)
    manager.supervisor.fail = "/store/addons/local_demo/install"
    with pytest.raises(Problem):
        manager.deploy(repo_id, "demo")
    assert not (manager.addons / "demo").exists()
    assert manager.state["deployments"]["demo"]["commit"] is None
    manager.supervisor.fail = None
    manager.recover("demo", accept_current=False)
    manager.deploy(repo_id, "demo")
    assert manager.state["deployments"]["demo"]["status"] == "installed"


def test_unmanaged_folder_not_overwritten(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "99")
    with pytest.raises(Problem, match="no pertenece"):
        manager.deploy(repo_id, "demo")
    assert (manager.addons / "demo" / "payload").read_text() == "99"


def test_slug_collision_in_other_folder(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "elsewhere")
    with pytest.raises(Problem, match="Otra carpeta"):
        manager.deploy(repo_id, "demo")


def test_real_git_sync_is_transactional(manager, tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    addon(remote / "demo")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(remote), *args], text=True).strip()

    git("init", "-b", "main")
    git("-c", "user.email=test@example.org", "-c", "user.name=Test", "add", ".")
    git("-c", "user.email=test@example.org", "-c", "user.name=Test", "commit", "-m", "initial")
    repo_id = manager.repo_add("Test", "https://example.org/u/r", "main")
    repo = manager.repo(repo_id)
    repo["url"] = str(remote)
    # Production rejects local transport. Only this fixture enables a local Git remote.
    monkeypatch.setattr(manager, "git_env", lambda _: dict(os.environ, GIT_ALLOW_PROTOCOL="file"))
    manager.sync(repo_id)
    first = repo["commit"]
    assert first == git("rev-parse", "HEAD")
    assert repo["apps"][0]["slug"] == "demo"
    repo["ref"] = "missing"
    with pytest.raises(Problem):
        manager.sync(repo_id)
    assert repo["commit"] == first
    assert (manager.data / "repos" / repo_id / "demo" / "payload").exists()
