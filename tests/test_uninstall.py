"""Native Supervisor lifecycle, explicit consent, and uncertain-result recovery."""

import json

import httpx
import pytest
from app.core import Manager, Problem, Supervisor, SupervisorUncertain
from test_manager import FakeSupervisor, addon, prepared
from test_manager import manager as manager


def installed(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    inspection = manager.inspect_removal(repo_id, "demo", allow_installed=True)
    return repo_id, root, inspection["local_digest"]


@pytest.mark.parametrize("remove_config", [False, True])
def test_uninstall_keeps_source_then_can_reinstall(manager, remove_config):
    repo_id, root, digest = installed(manager)
    manager.uninstall_app(repo_id, "demo", digest, remove_config)
    assert not manager.supervisor.installed
    assert (manager.addons / "demo/payload").exists()
    assert (root / "demo/payload").exists()
    assert not manager.state["transactions"]
    assert manager.state["deployments"]["demo"]["status"] == "uninstalled"
    assert manager.supervisor.payloads[-2] == (
        "POST",
        "/addons/local_demo/uninstall",
        {"remove_config": remove_config},
    )
    manager.deploy(repo_id, "demo")
    assert manager.installed_info("demo")["version"] == "1.0.0"


def test_combined_uninstall_and_delete_preserves_master_and_other_apps(manager):
    repo_id, root, digest = installed(manager)
    addon(root / "second", slug="second")
    manager.repo(repo_id)["apps"] = manager.discover(root)
    manager.deploy(repo_id, "second")
    manager.remove_app(repo_id, "demo", digest, uninstall=True)
    assert not (manager.addons / "demo").exists()
    assert manager.installed_info("second")
    assert (manager.addons / "second/payload").exists()
    assert (root / "demo/payload").exists()
    assert manager.repo(repo_id)["hidden_apps"] == ["demo"]
    assert (
        "POST",
        "/addons/local_demo/uninstall",
        {"remove_config": False},
    ) in manager.supervisor.payloads


def test_changed_source_cannot_authorize_uninstall(manager):
    repo_id, _, digest = installed(manager)
    (manager.addons / "demo/payload").write_text("changed")
    with pytest.raises(Problem) as caught:
        manager.uninstall_app(repo_id, "demo", digest)
    assert caught.value.code == "local_folder_changed"
    assert manager.installed_info("demo")
    assert not manager.state["transactions"]


@pytest.mark.parametrize("remove", [False, True])
def test_timeout_does_not_delete_source_or_repeat_uninstall_on_recovery(
    manager, monkeypatch, remove
):
    repo_id, _, digest = installed(manager)
    original = manager.supervisor.call
    attempts = []

    def uncertain(method, path, payload=None):
        if path.endswith("/uninstall"):
            attempts.append(path)
            raise SupervisorUncertain("simulated timeout", "supervisor_uncertain")
        return original(method, path, payload)

    monkeypatch.setattr(manager.supervisor, "call", uncertain)
    with pytest.raises(SupervisorUncertain):
        if remove:
            manager.remove_app(repo_id, "demo", digest, uninstall=True)
        else:
            manager.uninstall_app(repo_id, "demo", digest)
    assert (manager.addons / "demo/payload").exists()
    assert manager.state["transactions"]["demo"]["uninstall_requested"]
    with pytest.raises(SupervisorUncertain):
        manager.recover("demo")
    assert len(attempts) == 1
    assert (manager.addons / "demo/payload").exists()
    # A confirmed explicit retry may send another destructive request.
    monkeypatch.setattr(manager.supervisor, "call", original)
    manager.recover("demo", retry_uninstall=True)
    assert not manager.installed_info("demo")
    assert (manager.addons / "demo").exists() is not remove
    assert not manager.state["transactions"]


@pytest.mark.parametrize("remove", [False, True])
def test_restart_after_uninstall_succeeded_finishes_without_repeating_request(
    manager, monkeypatch, remove
):
    repo_id, root, digest = installed(manager)
    original = manager.supervisor.call

    def disconnected(method, path, payload=None):
        result = original(method, path, payload)
        if path.endswith("/uninstall"):
            raise SupervisorUncertain("lost response", "supervisor_uncertain")
        return result

    monkeypatch.setattr(manager.supervisor, "call", disconnected)
    with pytest.raises(SupervisorUncertain):
        if remove:
            manager.remove_app(repo_id, "demo", digest, uninstall=True)
        else:
            manager.uninstall_app(repo_id, "demo", digest)
    fake = FakeSupervisor()
    restarted = Manager(manager.data, manager.addons, fake)
    assert restarted.state["transactions"]["demo"]["uninstall_requested"]
    assert not fake.calls  # Restart never replays an operation.
    restarted.recover("demo")
    assert not any(path.endswith("/uninstall") for _, path in fake.calls)
    assert (root / "demo/payload").exists()
    assert not restarted.state["transactions"]


def test_unmanaged_installed_copy_can_be_uninstalled_but_unrelated_source_cannot(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo")
    manager.supervisor.installed = [{"slug": "local_demo", "version": "1.0.0"}]
    info = manager.inspect_removal(repo_id, "demo", allow_installed=True)
    manager.uninstall_app(repo_id, "demo", info["local_digest"])
    assert (manager.addons / "demo/payload").exists()
    assert not manager.supervisor.installed
    manager.state["deployments"].clear()
    manager.supervisor.installed = [{"slug": "local_demo", "version": "1.0.0"}]
    (manager.addons / "demo").rename(manager.addons / "unrelated")
    with pytest.raises(Problem):
        manager.uninstall_app(repo_id, "demo")
    assert manager.supervisor.installed


def test_native_install_and_uninstall_http_contract(manager, monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "isolated-test-token")
    present = []
    requests = []

    def handle(request):
        assert request.headers["Authorization"] == "Bearer isolated-test-token"
        path = request.url.path
        body = json.loads(request.content) if request.method == "POST" else None
        requests.append((request.method, path, body))
        if path == "/store/addons/local_demo/install":
            present.append({"slug": "local_demo", "version": "1.0.0", "state": "stopped"})
        elif path == "/addons/local_demo/uninstall":
            assert body == {"remove_config": False}
            present.clear()
        elif path not in {"/addons", "/store/reload"}:
            pytest.fail("Unexpected native endpoint: " + path)
        data = {"addons": list(present)} if path == "/addons" else {}
        return httpx.Response(200, json={"result": "ok", "data": data})

    manager.supervisor = Supervisor(httpx.MockTransport(handle))
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    digest = manager.inspect_removal(repo_id, "demo", allow_installed=True)["local_digest"]
    manager.uninstall_app(repo_id, "demo", digest)
    assert ("POST", "/store/addons/local_demo/install", {}) in requests
    assert not present
    assert (manager.addons / "demo/payload").exists()


def test_completed_rename_recovery_does_not_uninstall_a_new_installation(manager):
    repo_id, _, digest = installed(manager)
    manager.supervisor.fail = "/store/reload"
    with pytest.raises(Problem):
        manager.remove_app(repo_id, "demo", digest, uninstall=True)
    manager.state["transactions"]["demo"]["phase"] = "prepared"
    # A different install appeared after the reviewed folder was already staged.
    manager.supervisor.installed = [{"slug": "local_demo", "version": "9.0.0"}]
    calls = len(manager.supervisor.calls)
    with pytest.raises(Problem):
        manager.recover("demo", retry_uninstall=True)
    assert not any(path.endswith("/uninstall") for _, path in manager.supervisor.calls[calls:])
    assert manager.installed_info("demo")["version"] == "9.0.0"


@pytest.mark.parametrize(
    "version,endpoint",
    [("1.0.0", "/addons/local_demo/rebuild"), ("2.0.0", "/store/addons/local_demo/update")],
)
def test_local_build_update_selects_native_endpoint_for_its_version(manager, version, endpoint):
    repo_id, root, _ = installed(manager)
    addon(root / "demo", version)
    (root / "demo/payload").write_text("changed code")
    manager.repo(repo_id).update(commit="b" * 40, apps=manager.discover(root))
    manager.supervisor.calls.clear()
    manager.deploy(repo_id, "demo", update=True)
    assert ("POST", endpoint) in manager.supervisor.calls
    assert manager.installed_info("demo")["version"] == version
    assert (manager.addons / "demo/payload").read_text() == "changed code"
