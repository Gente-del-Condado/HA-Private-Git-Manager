import pytest
import yaml
from app.application import Applications
from app.core import Problem
from test_application import ControlsSupervisor
from test_manager import manager as manager
from test_manager import prepared


class IngressSupervisor(ControlsSupervisor):
    def __init__(self, version="2026.11.0"):
        super().__init__()
        self.core_version = version
        self.ingress = True

    def call(self, method, path, payload=None):
        if path == "/core/info":
            self.calls.append((method, path))
            return {"version": self.core_version}
        result = super().call(method, path, payload)
        if path.endswith("/info"):
            result.update(
                ingress=self.ingress,
                ingress_url="/api/hassio_ingress/private-app-session/",
                webui="https://untrusted.example/",
                ingress_panel=False,
            )
        return result


def install_ingress(manager, version="2026.11.0"):
    manager.supervisor = IngressSupervisor(version)
    manager.supervisor.addons = manager.addons
    manager.verify_checkout = lambda repo, root: None
    repo_id, root = prepared(manager)
    config = root / "demo/config.yaml"
    manifest = yaml.safe_load(config.read_text())
    manifest["ingress"] = True
    config.write_text(yaml.safe_dump(manifest))
    manager.repo(repo_id)["apps"] = manager.discover(root)
    manager.deploy(repo_id, "demo")
    manager.supervisor.installed[0]["state"] = "started"
    manager.save()
    return repo_id


@pytest.mark.parametrize(
    "version,prefix",
    [
        ("2025.12.4", "/hassio/ingress/"),
        ("2026.1.3", "/hassio/ingress/"),
        ("2026.2.0", "/app/"),
        ("2026.11.0", "/app/"),
        ("2027.1.0b1", "/app/"),
    ],
)
def test_ingress_uses_core_frontend_route_without_session_tokens(manager, version, prefix):
    repo_id = install_ingress(manager, version)
    manager.supervisor.calls.clear()
    before = manager.state_file.read_bytes()
    result = Applications(manager).web_interface(repo_id, "demo")
    assert result == {"path": prefix + "local_demo"}
    assert manager.state_file.read_bytes() == before
    assert all(method == "GET" for method, _ in manager.supervisor.calls)
    assert not any("session" in path for _, path in manager.supervisor.calls)
    assert manager.repo(repo_id)["apps"][0]["ingress"] is True
    assert manager.state["deployments"]["demo"]["ingress"] is True


@pytest.mark.parametrize("state", ["stopped", "error", "unknown"])
def test_ingress_does_not_start_stopped_apps_or_use_direct_webui(manager, state):
    repo_id = install_ingress(manager)
    manager.supervisor.installed[0]["state"] = state
    with pytest.raises(Problem) as caught:
        Applications(manager).web_interface(repo_id, "demo")
    assert caught.value.code == "app_not_running"
    manager.supervisor.installed[0]["state"] = "started"
    manager.supervisor.ingress = False
    with pytest.raises(Problem) as caught:
        Applications(manager).web_interface(repo_id, "demo")
    assert caught.value.code == "app_no_ingress"


def test_ingress_rechecks_installation_ownership_and_pending_operations(manager):
    repo_id = install_ingress(manager)
    apps = Applications(manager)
    manager.state["transactions"]["demo"] = {"kind": "uninstall"}
    manager.save()
    with pytest.raises(Problem) as caught:
        apps.web_interface(repo_id, "demo")
    assert caught.value.code == "recovery_required"
    manager.state["transactions"].clear()
    manager.state["deployments"]["demo"]["repo_id"] = "foreign"
    manager.save()
    with pytest.raises(Problem) as caught:
        apps.web_interface(repo_id, "demo")
    assert caught.value.code == "slug_owned"
    manager.state["deployments"]["demo"]["repo_id"] = repo_id
    manager.supervisor.installed.clear()
    manager.save()
    with pytest.raises(Problem) as caught:
        apps.web_interface(repo_id, "demo")
    assert caught.value.code == "app_not_installed"


def test_unknown_core_version_does_not_guess_a_route(manager):
    repo_id = install_ingress(manager, "unknown")
    with pytest.raises(Problem) as caught:
        Applications(manager).web_interface(repo_id, "demo")
    assert caught.value.code == "ha_version_unavailable"
