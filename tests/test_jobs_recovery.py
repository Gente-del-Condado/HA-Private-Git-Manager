import json
import threading
import time

import httpx
import pytest
from app.core import VERSION, Manager, Problem, Supervisor, SupervisorUncertain
from app.jobs import Jobs, Scheduler
from test_manager import FakeSupervisor, addon, prepared


@pytest.fixture
def manager(tmp_path):
    result = Manager(tmp_path / "data", tmp_path / "addons", FakeSupervisor())
    result.supervisor.addons = result.addons
    result.verify_checkout = lambda repo, root: None  # Synthetic Supervisor fixture.
    return result


def wait_job(jobs, job_id):
    for _ in range(200):
        item = jobs.snapshot()[job_id]
        if item["status"] not in {"running", "queued"}:
            return item
        time.sleep(0.01)
    pytest.fail("Background job did not finish")


def test_background_job_nonblocking_snapshot_and_duplicate_rejection(manager):
    jobs = Jobs(manager)
    started, finish = threading.Event(), threading.Event()

    def operation():
        started.set()
        finish.wait(timeout=5)
        manager.progress("validating")
        return {"done": True}

    try:
        job = jobs.submit("sync", "repo:one", operation, "request-one")
        assert started.wait(timeout=2)
        before = time.monotonic()
        assert manager.snapshot()["version"] == VERSION
        assert time.monotonic() - before < 0.1
        assert jobs.submit("sync", "repo:one", operation, "request-one")["id"] == job["id"]
        with pytest.raises(Problem) as caught:
            jobs.submit("sync", "repo:one", operation)
        assert caught.value.code == "busy"
        finish.set()
        assert wait_job(jobs, job["id"])["status"] == "succeeded"
    finally:
        finish.set()
        jobs.close()


def test_failure_is_persistent_and_redacts_secret(manager):
    manager.repo_add("Private", "https://example.org/u/r", "main", token="secret-token")
    jobs = Jobs(manager)

    def failure():
        raise Problem("Server returned secret-token")

    try:
        item = jobs.submit("sync", "repo:one", failure)
        result = wait_job(jobs, item["id"])
        assert result["status"] == "failed"
        assert "secret-token" not in json.dumps(result)
        assert "secret-token" not in jobs.path.read_text()
        assert "secret-token" not in manager.log_path.read_text()
        assert jobs.path.stat().st_mode & 0o777 == 0o600
    finally:
        jobs.close()


def test_restart_marks_jobs_interrupted(manager):
    path = manager.data / "jobs.json"
    path.write_text(
        json.dumps(
            {"abc": {"id": "abc", "status": "running", "kind": "deploy", "resource": "app:demo"}}
        )
    )
    jobs = Jobs(manager)
    try:
        assert jobs.snapshot()["abc"]["status"] == "interrupted"
    finally:
        jobs.close()


def test_scheduler_checks_only_and_throttles_failures(manager, monkeypatch):
    repo_id = manager.repo_add("Repo", "https://example.org/u/r", "main")
    manager.repo_edit(repo_id, "Repo", "main", 300)
    manager.repo(repo_id)["created_at"] = 1000
    manager.save()
    calls = []

    class Queue:
        def submit(self, kind, resource, callback):
            calls.append((kind, resource))

    scheduler = Scheduler(manager, Queue())
    scheduler.tick(now=1299)
    assert not calls
    scheduler.tick(now=1301)
    scheduler.tick(now=1302)
    assert calls == [("sync", "repo:" + repo_id)]


def test_stopped_app_stays_stopped_after_rebuild(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    manager.deploy(repo_id, "demo", update=True)
    assert manager.supervisor.installed[0]["state"] == "stopped"
    assert manager.supervisor.calls[-1] == ("POST", "/addons/local_demo/stop")


def test_stale_confirmation_cannot_install_new_commit(manager):
    repo_id, _ = prepared(manager)
    with pytest.raises(Problem) as caught:
        manager.deploy(repo_id, "demo", expected_commit="b" * 40)
    assert caught.value.code == "commit_changed"
    assert not manager.supervisor.calls


def test_uncertain_supervisor_preserves_both_sources_and_requires_recovery(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    addon(root / "demo", "2.0.0")
    manager.repo(repo_id).update(commit="b" * 40, apps=manager.discover(root))
    original = manager.supervisor.call

    def uncertain(method, path):
        if path.endswith("/rebuild"):
            raise SupervisorUncertain("May still be running", "supervisor_uncertain")
        return original(method, path)

    manager.supervisor.call = uncertain
    with pytest.raises(SupervisorUncertain):
        manager.deploy(repo_id, "demo", update=True)
    transaction = manager.state["transactions"]["demo"]
    assert (manager.addons / transaction["backup"] / "payload").read_text() == "1.0.0"
    assert (manager.addons / "demo" / "payload").read_text() == "2.0.0"
    assert manager.snapshot()["deployments"]["demo"]["status"] == "uncertain"
    with pytest.raises(Problem) as caught:
        manager.deploy(repo_id, "demo", update=True)
    assert caught.value.code == "recovery_required"
    manager.supervisor.call = original
    manager.recover("demo")
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
    assert "demo" not in manager.state["transactions"]


def test_crash_between_renames_can_restore_previous_folder(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    previous = dict(manager.state["deployments"]["demo"])
    (manager.addons / "demo").rename(manager.addons / ".pgm-backup-test")
    manager.state["transactions"]["demo"] = {
        "stage": ".pgm-stage-test",
        "backup": ".pgm-backup-test",
        "previous": previous,
        "record": dict(previous),
        "phase": "swapping",
        "was_running": False,
    }
    manager.state["deployments"]["demo"]["status"] = "pending"
    manager.save()
    restarted = Manager(manager.data, manager.addons, manager.supervisor)
    assert restarted.snapshot()["deployments"]["demo"]["status"] == "interrupted"
    restarted.recover("demo")
    assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"


def test_accepting_current_requires_both_image_version_and_source_digest(manager):
    repo_id, root = prepared(manager)
    manager.supervisor.fail = "/store/addons/local_demo/install"
    with pytest.raises(Problem):
        manager.deploy(repo_id, "demo")
    manager.supervisor.fail = None
    manager.supervisor.installed = [{"slug": "local_demo", "version": "1.0.0", "state": "stopped"}]
    with pytest.raises(Problem):
        manager.recover("demo", accept_current=True)


def test_supervisor_uses_bearer_and_classifies_disconnect(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "fixture-token")

    def handle(request):
        assert request.headers["Authorization"] == "Bearer fixture-token"
        return httpx.Response(200, json={"result": "ok", "data": {"addons": []}})

    assert Supervisor(httpx.MockTransport(handle)).call("GET", "/addons") == {"addons": []}

    def disconnect(request):
        raise httpx.ReadTimeout("timeout")

    with pytest.raises(SupervisorUncertain):
        Supervisor(httpx.MockTransport(disconnect)).call("POST", "/addons/local_demo/rebuild")


def test_missing_previous_backup_cannot_claim_successful_restore(manager):
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    previous = dict(manager.state["deployments"]["demo"])
    addon(manager.addons / "demo", "99.0.0")
    manager.state["transactions"]["demo"] = {
        "stage": ".pgm-stage-gone",
        "backup": ".pgm-backup-gone",
        "previous": previous,
        "record": dict(previous),
        "phase": "supervisor",
        "was_running": False,
    }
    manager.save()
    with pytest.raises(Problem) as caught:
        manager.recover("demo")
    assert caught.value.code == "backup_missing"
    assert "demo" in manager.state["transactions"]


def test_package_cannot_register_nested_apps(manager):
    repo_id, root = prepared(manager)
    addon(root / "demo" / "nested", slug="nested")
    manager.repo(repo_id)["apps"] = manager.discover(root)
    with pytest.raises(Problem) as caught:
        manager.deploy(repo_id, "demo")
    assert caught.value.code == "nested_apps"
    assert not (manager.addons / "demo").exists()
