"""Regression coverage for local folders already present under /addons."""

import shutil

import pytest
import yaml
from app.core import Manager, Problem, SupervisorUncertain
from test_manager import FakeSupervisor, addon, prepared


@pytest.fixture
def manager(tmp_path):
    manager = Manager(tmp_path / "data", tmp_path / "addons", FakeSupervisor())
    manager.supervisor.addons = manager.addons
    manager.verify_checkout = lambda repo, root: None  # Synthetic Supervisor fixture.
    return manager


def adopt(manager, repo_id, inspection=None):
    inspection = inspection or manager.inspect_deployment(repo_id, "demo")
    manager.deploy(
        repo_id,
        "demo",
        adopt_existing=True,
        expected_local_digest=inspection["local_digest"],
        expected_commit=inspection["commit"],
    )


def test_preflight_describes_existing_folder_without_taking_ownership(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    inspection = manager.inspect_deployment(repo_id, "demo")
    assert inspection["requires_adoption"] and not inspection["managed"]
    assert inspection["local_version"] == "0.5.0"
    assert inspection["path"] == str(manager.addons / "demo")
    assert len(inspection["local_digest"]) == 64
    assert not manager.state["deployments"]
    assert (manager.addons / "demo" / "payload").read_text() == "0.5.0"


def test_empty_existing_folder_is_reused(manager):
    repo_id, _ = prepared(manager)
    (manager.addons / "demo").mkdir()
    inspection = manager.inspect_deployment(repo_id, "demo")
    assert inspection["empty"] and not inspection["requires_adoption"]
    manager.deploy(repo_id, "demo")
    assert manager.state["deployments"]["demo"]["status"] == "installed"
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"


def test_adoption_requires_fingerprint_and_explicit_consent(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    inspection = manager.inspect_deployment(repo_id, "demo")
    with pytest.raises(Problem) as caught:
        manager.deploy(repo_id, "demo", expected_local_digest=inspection["local_digest"])
    assert caught.value.code == "folder_owned"
    with pytest.raises(Problem) as caught:
        manager.deploy(repo_id, "demo", adopt_existing=True)
    assert caught.value.code == "adoption_confirmation_required"
    assert not manager.state["deployments"]


def test_adopt_existing_uninstalled_app_and_install(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    adopt(manager, repo_id)
    assert manager.state["deployments"]["demo"]["commit"] == "a" * 40
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
    assert ("POST", "/store/addons/local_demo/install") in manager.supervisor.calls
    assert any(event["code"] == "local_adopted" for event in manager.state["events"])


def test_adopt_already_installed_app_updates_and_preserves_running_state(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    manager.supervisor.installed = [{"slug": "local_demo", "version": "0.5.0", "state": "started"}]
    adopt(manager, repo_id)
    assert ("POST", "/store/addons/local_demo/update") in manager.supervisor.calls
    assert ("POST", "/store/addons/local_demo/install") not in manager.supervisor.calls
    assert manager.supervisor.installed[0]["state"] == "started"


@pytest.mark.parametrize("runtime_state", ["started", "stopped"])
def test_identical_installed_prebuilt_app_can_be_adopted_without_image_update(
    manager, runtime_state
):
    repo_id, root = prepared(manager)
    manifest = root / "demo" / "config.yaml"
    content = yaml.safe_load(manifest.read_text())
    content["image"] = "ghcr.io/example/demo"
    manifest.write_text(yaml.safe_dump(content))
    manager.repo(repo_id)["apps"] = manager.discover(root)
    shutil.copytree(root / "demo", manager.addons / "demo")
    manager.supervisor.installed = [
        {"slug": "local_demo", "version": "1.0.0", "state": runtime_state}
    ]
    adopt(manager, repo_id)
    assert ("POST", "/store/addons/local_demo/update") not in manager.supervisor.calls
    assert manager.state["deployments"]["demo"]["status"] == "installed"
    assert ("POST", "/addons/local_demo/stop") not in manager.supervisor.calls
    assert ("POST", "/addons/local_demo/start") not in manager.supervisor.calls
    assert manager.supervisor.installed[0]["state"] == runtime_state


def test_changed_folder_requires_new_review(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    inspection = manager.inspect_deployment(repo_id, "demo")
    (manager.addons / "demo" / "payload").write_text("changed after review")
    with pytest.raises(Problem) as caught:
        adopt(manager, repo_id, inspection)
    assert caught.value.code == "local_folder_changed"
    assert not manager.state["transactions"]
    assert not any(method == "POST" for method, _ in manager.supervisor.calls)


def test_folder_changed_while_preparing_source_is_not_overwritten(manager, monkeypatch):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    original = manager.safe_copy

    def changed(source, target):
        original(source, target)
        (manager.addons / "demo" / "payload").write_text("external change during staging")

    monkeypatch.setattr(manager, "safe_copy", changed)
    with pytest.raises(Problem) as caught:
        adopt(manager, repo_id)
    assert caught.value.code == "local_folder_changed"
    assert (manager.addons / "demo" / "payload").read_text() == "external change during staging"
    assert not manager.state["transactions"]
    assert not list(manager.addons.glob(".pgm-*"))


def test_different_app_in_same_folder_is_not_adopted(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", slug="other_app")
    with pytest.raises(Problem) as caught:
        manager.inspect_deployment(repo_id, "demo")
    assert caught.value.code == "local_manifest_mismatch"


def test_symlink_folder_is_never_adopted(manager, tmp_path):
    repo_id, _ = prepared(manager)
    addon(tmp_path / "outside")
    (manager.addons / "demo").symlink_to(tmp_path / "outside", target_is_directory=True)
    with pytest.raises(Problem) as caught:
        manager.inspect_deployment(repo_id, "demo")
    assert caught.value.code == "unsafe_local_folder"


def test_failed_adoption_restores_original_source_without_claiming_it_after_recovery(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    manager.supervisor.fail = "/store/addons/local_demo/install"
    with pytest.raises(Problem):
        adopt(manager, repo_id)
    assert (manager.addons / "demo" / "payload").read_text() == "0.5.0"
    manager.supervisor.fail = None
    manager.recover("demo")
    assert "demo" not in manager.state["deployments"]
    assert (manager.addons / "demo" / "payload").read_text() == "0.5.0"


def test_uncertain_adoption_keeps_previous_source_for_explicit_recovery(manager, monkeypatch):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    original = manager.supervisor.call

    def uncertain(method, path):
        if path.endswith("/install"):
            raise SupervisorUncertain("simulated disconnect", "supervisor_uncertain")
        return original(method, path)

    monkeypatch.setattr(manager.supervisor, "call", uncertain)
    with pytest.raises(SupervisorUncertain):
        adopt(manager, repo_id)
    transaction = manager.state["transactions"]["demo"]
    assert transaction["unmanaged_existing"]
    assert (manager.addons / transaction["backup"] / "payload").read_text() == "0.5.0"
    manager.recover("demo")
    assert not manager.state["deployments"]
    assert (manager.addons / "demo" / "payload").read_text() == "0.5.0"


def test_missing_adoption_backup_does_not_delete_existing_source(manager, monkeypatch):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    original = manager.supervisor.call

    def uncertain(method, path):
        if path.endswith("/install"):
            raise SupervisorUncertain("simulated disconnect", "supervisor_uncertain")
        return original(method, path)

    monkeypatch.setattr(manager.supervisor, "call", uncertain)
    with pytest.raises(SupervisorUncertain):
        adopt(manager, repo_id)
    shutil.rmtree(manager.addons / manager.state["transactions"]["demo"]["backup"])
    with pytest.raises(Problem) as caught:
        manager.recover("demo")
    assert caught.value.code == "backup_missing"
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
    assert "demo" in manager.state["transactions"]
