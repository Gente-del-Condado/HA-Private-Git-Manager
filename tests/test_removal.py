"""Deleting one local app must never delete its repository or its siblings."""

import json

import pytest
from app.core import Manager, Problem
from test_manager import FakeSupervisor, addon, prepared
from test_manager import manager as manager


def remove(manager, repo_id, hide=True):
    inspection = manager.inspect_removal(repo_id, "demo")
    manager.remove_app(repo_id, "demo", inspection["local_digest"], hide)


def test_remove_one_app_from_master_preserves_other_app_and_checkout(manager):
    repo_id, root = prepared(manager)
    addon(root / "second", slug="second")
    repo = manager.repo(repo_id)
    repo["apps"] = manager.discover(root)
    addon(manager.addons / "demo")
    addon(manager.addons / "second", slug="second")
    manager.state["deployments"]["second"] = {"repo_id": repo_id, "slug": "second"}
    before = manager.tree_digest(root)
    remove(manager, repo_id)
    assert not (manager.addons / "demo").exists()
    assert (manager.addons / "second" / "payload").read_text() == "1.0.0"
    assert manager.tree_digest(root) == before
    assert "second" in manager.state["deployments"]
    assert "demo" not in manager.state["deployments"]
    assert repo["hidden_apps"] == ["demo"]
    assert not manager.state["transactions"]
    assert not list(manager.addons.glob(".pgm-remove-*"))
    loaded = Manager(manager.data, manager.addons, FakeSupervisor())
    assert loaded.repo(repo_id)["hidden_apps"] == ["demo"]
    loaded.restore_app(repo_id, "demo")
    assert not json.loads(loaded.state_file.read_text())["repos"][repo_id]["hidden_apps"]


def test_released_source_can_be_deleted_without_hiding(manager):
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    manager.supervisor.installed.clear()  # Uninstalled in Home Assistant.
    manager.release("demo")
    assert (manager.addons / "demo").exists()
    remove(manager, repo_id, hide=False)
    assert not (manager.addons / "demo").exists()
    assert not manager.repo(repo_id).get("hidden_apps")


def test_installed_app_is_never_deleted_or_uninstalled(manager):
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    before = list(manager.supervisor.calls)
    with pytest.raises(Problem, match="Desinstala"):
        remove(manager, repo_id)
    assert (manager.addons / "demo").exists()
    assert not manager.state["transactions"]
    assert manager.supervisor.calls[len(before) :] == [("GET", "/addons")]


def test_changed_folder_requires_review_again(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo")
    inspection = manager.inspect_removal(repo_id, "demo")
    (manager.addons / "demo/payload").write_text("edited")
    with pytest.raises(Problem) as caught:
        manager.remove_app(repo_id, "demo", inspection["local_digest"])
    assert caught.value.code == "local_folder_changed"
    assert not manager.state["transactions"]


@pytest.mark.parametrize(
    "unsafe", ["wrong_slug", "nested", "symlink", "self", "traversal", "other_owner"]
)
def test_removal_rejects_unsafe_targets(manager, unsafe):
    repo_id, root = prepared(manager)
    slug = "demo"
    if unsafe == "wrong_slug":
        addon(manager.addons / "demo", slug="other")
    elif unsafe == "nested":
        addon(manager.addons / "demo")
        addon(manager.addons / "demo/second", slug="second")
    elif unsafe == "symlink":
        (manager.addons / "demo").symlink_to(root / "demo", target_is_directory=True)
    elif unsafe == "self":
        slug = "private_git_manager"
    elif unsafe == "traversal":
        slug = "../demo"
    else:
        manager.state["deployments"]["demo"] = {"repo_id": "another"}
    with pytest.raises(Problem):
        manager.inspect_removal(repo_id, slug)
    assert not manager.state["transactions"]
    assert (root / "demo/payload").exists()


def test_pending_removal_survives_restart_and_preserves_new_target(manager):
    repo_id, root = prepared(manager)
    addon(manager.addons / "demo")
    manager.supervisor.fail = "/store/reload"
    with pytest.raises(Problem):
        remove(manager, repo_id)
    pending = manager.state["transactions"]["demo"]
    stage = manager.addons / pending["stage"]
    assert stage.exists() and not (manager.addons / "demo").exists()
    assert pending["phase"] == "staged"
    addon(manager.addons / "demo", "9.0.0")  # Unrelated copy created later.
    restored = Manager(manager.data, manager.addons, FakeSupervisor())
    restored.recover("demo")
    assert not stage.exists()
    assert (manager.addons / "demo/payload").read_text() == "9.0.0"
    assert (root / "demo/payload").exists()
    assert not restored.state["transactions"]


def test_interrupted_rename_can_be_finished(manager):
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo")
    manager.supervisor.fail = "/store/reload"
    with pytest.raises(Problem):
        remove(manager, repo_id)
    # Emulate restart between rename and saving the new journal phase.
    manager.state["transactions"]["demo"]["phase"] = "prepared"
    manager.supervisor.fail = None
    manager.recover("demo")
    assert not (manager.addons / "demo").exists()
    assert not manager.state["transactions"]


def test_manual_uninstall_allows_reinstallation_of_managed_app(manager):
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    manager.supervisor.installed.clear()
    manager.supervisor.calls.clear()
    manager.deploy(repo_id, "demo", update=False)
    assert ("POST", "/store/addons/local_demo/install") in manager.supervisor.calls
    assert manager.state["deployments"]["demo"]["status"] == "installed"


def test_partial_cleanup_can_be_retried_without_touching_other_folders(manager, monkeypatch):
    import app.core as core

    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo")
    addon(manager.addons / "second", slug="second")
    original = core.shutil.rmtree

    def interrupted(path, *args, **kwargs):
        (path / "payload").unlink()
        raise OSError("simulated interruption")

    monkeypatch.setattr(core.shutil, "rmtree", interrupted)
    with pytest.raises(OSError):
        remove(manager, repo_id)
    assert manager.state["transactions"]["demo"]["phase"] == "purging"
    monkeypatch.setattr(core.shutil, "rmtree", original)
    manager.recover("demo")
    assert not manager.state["transactions"]
    assert (manager.addons / "second/payload").exists()


def test_listing_can_be_hidden_when_no_local_folder_exists(manager):
    repo_id, _ = prepared(manager)
    remove(manager, repo_id)
    assert manager.repo(repo_id)["hidden_apps"] == ["demo"]
    assert not manager.state["deployments"]
