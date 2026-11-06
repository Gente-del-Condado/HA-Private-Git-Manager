import copy
import json
import threading
import time

import pytest
from app import main
from app.backups import Backups
from app.core import Problem, SupervisorRejected, SupervisorUncertain
from app.jobs import Jobs
from fastapi.testclient import TestClient
from test_application import ControlsSupervisor
from test_manager import manager as manager
from test_manager import prepared

HEADERS = {"X-PGM-Request": "1"}


class BackupSupervisor(ControlsSupervisor):
    def __init__(self):
        super().__init__()
        self.backups = {}
        self.backup_passwords = {}
        self.restore_started = threading.Event()
        self.release = None
        self.error = None
        self.unconfirmed = False

    def call(self, method, path, payload=None):
        if not path.startswith("/backups"):
            return super().call(method, path, payload)
        self.calls.append((method, path))
        self.payloads.append((method, path, copy.deepcopy(payload)))
        if method == "GET" and path == "/backups":
            return {"backups": [copy.deepcopy(item) for item in self.backups.values()]}
        if method == "GET":
            return copy.deepcopy(self.backups[path.split("/")[2]])
        if self.error:
            raise self.error
        if path == "/backups/new/partial":
            selected = f"backup{len(self.backups) + 1}"
            app = self.installed[0]
            self.backups[selected] = {
                "slug": selected,
                "name": payload["name"],
                "date": "2026-11-07T12:00:00+00:00",
                "size": 0.5,
                "type": "partial",
                "protected": bool(payload.get("password")),
                "location": None,
                "content": {"addons": payload["addons"]},
                "addons": [{"slug": app["slug"], "version": app["version"]}],
                "private_options": {"token": "native-backup-private-token"},
                "_settings": copy.deepcopy(self.settings),
            }
            self.backup_passwords[selected] = payload.get("password")
            return (
                {"job_id": "nativejob", "slug": selected}
                if not self.unconfirmed
                else {"job_id": "nativejob"}
            )
        if path.endswith("/restore/partial"):
            self.restore_started.set()
            if self.release:
                self.release.wait(timeout=5)
            selected = path.split("/")[2]
            if self.backup_passwords.get(selected) != payload.get("password"):
                raise SupervisorRejected("Supervisor rechazó la operación.", "supervisor_rejected")
            backup = self.backups[selected]
            self.settings = copy.deepcopy(backup["_settings"])
            if not self.installed:
                self.installed.append({"slug": "local_demo", "state": "stopped"})
            self.installed[0]["version"] = backup["addons"][0]["version"]
            return {"job_id": "nativejob"}
        raise AssertionError(path)


@pytest.fixture
def backups(manager):
    manager.supervisor = BackupSupervisor()
    manager.supervisor.addons = manager.addons
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    return manager, Backups(manager), repo_id


def test_create_native_backup_is_local_scoped_and_verified(backups):
    manager, service, repo = backups
    result = service.create(repo, "demo", "Before update", "backup-encryption-secret")
    assert result == {"ok": True, "backup": "backup1"}
    payload = next(
        p for m, path, p in manager.supervisor.payloads if path == "/backups/new/partial"
    )
    assert payload == {
        "name": "Before update",
        "addons": ["local_demo"],
        "folders": [],
        "homeassistant": False,
        "location": None,
        "compressed": True,
        "background": False,
        "password": "backup-encryption-secret",
    }
    listed = service.list(repo, "demo")
    assert listed["installed"] is True
    assert listed["backups"][0]["protected"] is True
    assert listed["backups"][0]["size_bytes"] == 524288
    detail = service.details(repo, "demo", "backup1")
    assert detail["version"] == "1.0.0"
    assert "native-backup-private-token" not in json.dumps(detail)
    assert "initial-app-secret" not in json.dumps(listed)
    for source in [manager.state_file.read_text(), manager.log_path.read_text()]:
        assert "backup-encryption-secret" not in source
        assert "initial-app-secret" not in source
        assert "Before update" not in source


def test_restore_from_full_backup_restores_only_selected_app_and_handles_uninstalled(backups):
    manager, service, repo = backups
    service.create(repo, "demo")
    native = manager.supervisor.backups["backup1"]
    native["type"] = "full"
    native["content"] = {
        "addons": ["local_demo", "core_other"],
        "homeassistant": True,
        "folders": ["share"],
    }
    native["addons"].append({"slug": "core_other", "version": "2.0"})
    manager.supervisor.settings["options"]["username"] = "changed"
    manager.supervisor.installed.clear()
    assert service.list(repo, "demo")["installed"] is False
    assert service.restore(repo, "demo", "backup1")["ok"]
    payload = next(
        p for _, path, p in manager.supervisor.payloads if path.endswith("/restore/partial")
    )
    assert payload == {
        "addons": ["local_demo"],
        "folders": [],
        "homeassistant": False,
        "location": None,
        "background": False,
    }
    assert manager.supervisor.settings["options"]["username"] == "demo"
    assert manager.supervisor.installed[0]["version"] == "1.0.0"
    assert (manager.addons / "demo" / "config.yaml").exists()


def test_list_filters_by_exact_app_and_handles_current_field_names_and_locations(backups):
    manager, service, repo = backups
    service.create(repo, "demo")
    seed = manager.supervisor.backups["backup1"]
    for selected, content, location in [
        ("other", ["local_demolition"], None),
        ("remote", ["local_demo"], "NAS"),
        ("cloud", ["local_demo"], ".cloud_backup"),
    ]:
        manager.supervisor.backups[selected] = {
            **copy.deepcopy(seed),
            "slug": selected,
            "content": {"apps": content},
            "location": location,
            "size_bytes": 100,
            "location_attributes": {location: {"protected": True, "size_bytes": 200}},
        }
    items = service.list(repo, "demo")["backups"]
    assert {b["slug"] for b in items} == {"backup1", "remote"}
    remote = next(b for b in items if b["slug"] == "remote")
    assert remote["protected"] is True
    assert remote["size_bytes"] == 200
    native = manager.supervisor.backups["remote"]
    native["apps"] = native.pop("addons")
    assert service.details(repo, "demo", "remote")["version"] == "1.0.0"


@pytest.mark.parametrize("operation", ["list", "create", "restore"])
def test_backup_ownership_and_self_protection(backups, operation):
    manager, service, repo = backups
    other = manager.repo_add("Other", "https://example.org/other/repo", "main")
    args = ("backup1",) if operation == "restore" else ()
    with pytest.raises(Problem) as caught:
        getattr(service, operation)(other, "demo", *args)
    assert caught.value.code == "slug_owned"
    with pytest.raises(Problem):
        getattr(service, operation)(repo, "private_git_manager", *args)
    assert not any(path.startswith("/backups") for _, path in manager.supervisor.calls)


def test_pending_transactions_and_missing_password_stop_mutation(backups):
    manager, service, repo = backups
    service.create(repo, "demo", password="encrypted-backup-secret")
    with pytest.raises(Problem) as caught:
        service.restore(repo, "demo", "backup1")
    assert caught.value.code == "backup_password_required"
    manager.state["transactions"]["demo"] = {"status": "pending"}
    manager.save()
    for action, args in [("create", ()), ("restore", ("backup1", "encrypted-backup-secret"))]:
        with pytest.raises(Problem) as caught:
            getattr(service, action)(repo, "demo", *args)
        assert caught.value.code == "recovery_required"
    assert not any(path.endswith("/restore/partial") for _, path in manager.supervisor.calls)


def test_restore_validates_backup_contents_again_and_rejects_path_injection(backups):
    manager, service, repo = backups
    service.create(repo, "demo")
    manager.supervisor.backups["backup1"]["addons"] = [{"slug": "local_other"}]
    with pytest.raises(Problem) as caught:
        service.restore(repo, "demo", "backup1")
    assert caught.value.code == "backup_app_missing"
    for value in ["../other", "bad?query=x", "x/restore/full", ""]:
        with pytest.raises(Problem) as caught:
            service.details(repo, "demo", value)
        assert caught.value.code == "backup_invalid"
    assert not any(path.endswith("/restore/partial") for _, path in manager.supervisor.calls)


@pytest.mark.parametrize("operation", ["create", "restore"])
def test_uncertain_outcome_is_explicit_and_not_retried(backups, operation):
    manager, service, repo = backups
    service.create(repo, "demo")
    manager.supervisor.error = SupervisorUncertain("timeout", "supervisor_uncertain")
    before = len(manager.supervisor.calls)
    with pytest.raises(Problem) as caught:
        getattr(service, operation)(repo, "demo", *(["backup1"] if operation == "restore" else []))
    assert caught.value.code == "backup_uncertain"
    assert sum(method == "POST" for method, _ in manager.supervisor.calls[before:]) == 1


def test_create_does_not_report_success_for_background_only_response(backups):
    manager, service, repo = backups
    manager.supervisor.unconfirmed = True
    with pytest.raises(Problem) as caught:
        service.create(repo, "demo")
    assert caught.value.code == "backup_uncertain"
    assert not any(e["code"] == "app_backup_created" for e in manager.state["events"])


def finish_job(jobs, selected):
    for _ in range(500):
        item = jobs.snapshot()[selected]
        if item["status"] not in {"queued", "running"}:
            return item
        time.sleep(0.01)
    raise AssertionError("Job did not finish")


def test_api_confirmation_csrf_privacy_and_queued_restore(backups, monkeypatch):
    manager, service, repo = backups
    jobs = Jobs(manager)
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "jobs", jobs)
    client = TestClient(main.app)
    base = f"/api/repos/{repo}/apps/demo/backups"
    try:
        assert client.post(base, json={}).status_code == 403
        assert client.post(base, json={}, headers=HEADERS).json()["code"] == "confirmation_required"
        assert (
            client.post(base + "/backup1/restore", json={}, headers=HEADERS).json()["code"]
            == "confirmation_required"
        )
        invalid = client.post(
            base,
            json={"confirmed": True, "name": "bad\nname", "password": "do-not-echo"},
            headers=HEADERS,
        )
        assert invalid.status_code == 422 and "do-not-echo" not in invalid.text
        response = client.post(
            base,
            json={"confirmed": True, "password": "queued-backup-secret"},
            headers={**HEADERS, "Idempotency-Key": "create-once"},
        )
        assert response.status_code == 202
        job = finish_job(jobs, response.json()["id"])
        assert job["status"] == "succeeded"
        assert (
            client.post(
                base,
                json={"confirmed": True},
                headers={**HEADERS, "Idempotency-Key": "create-once"},
            ).json()["id"]
            == job["id"]
        )
        assert len(manager.supervisor.backups) == 1
        response = client.get(base)
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["backups"][0]["protected"] is True
        assert "native-backup-private-token" not in client.get(base + "/backup1").text
        manager.supervisor.release = threading.Event()
        response = client.post(
            base + "/backup1/restore",
            json={"confirmed": True, "password": "queued-backup-secret"},
            headers=HEADERS,
        )
        assert response.status_code == 202
        assert manager.supervisor.restore_started.wait(timeout=2)
        started = time.monotonic()
        assert client.get("/api/state").status_code == 200
        assert time.monotonic() - started < 0.5
        manager.supervisor.release.set()
        assert finish_job(jobs, response.json()["id"])["status"] == "succeeded"
        sources = (
            jobs.path.read_text() + manager.state_file.read_text() + manager.log_path.read_text()
        )
        assert "queued-backup-secret" not in sources
        assert "initial-app-secret" not in sources
    finally:
        if manager.supervisor.release:
            manager.supervisor.release.set()
        jobs.executor.shutdown(wait=True)


def test_wrong_password_rejected_without_data_change_or_success_event(backups):
    manager, service, repo = backups
    service.create(repo, "demo", password="correct-password")
    manager.supervisor.settings["options"]["username"] = "keep-current"
    with pytest.raises(SupervisorRejected):
        service.restore(repo, "demo", "backup1", "incorrect-password")
    assert manager.supervisor.settings["options"]["username"] == "keep-current"
    assert not any(e["code"] == "app_backup_restored" for e in manager.state["events"])


def test_restore_verifies_version_and_preserves_git_source_state(backups):
    manager, service, repo = backups
    service.create(repo, "demo")
    source = (manager.addons / "demo" / "config.yaml").read_bytes()
    deployment = copy.deepcopy(manager.state["deployments"]["demo"])
    manager.supervisor.backups["backup1"]["addons"][0]["version"] = "0.5.0"
    service.restore(repo, "demo", "backup1")
    assert manager.supervisor.installed[0]["version"] == "0.5.0"
    assert manager.state["deployments"]["demo"] == deployment
    assert (manager.addons / "demo" / "config.yaml").read_bytes() == source


def test_remote_backup_restores_from_its_location(backups):
    manager, service, repo = backups
    service.create(repo, "demo")
    manager.supervisor.backups["backup1"]["location"] = "NAS-backups"
    service.restore(repo, "demo", "backup1")
    payload = next(
        p for _, path, p in manager.supervisor.payloads if path.endswith("/restore/partial")
    )
    assert payload["location"] == "NAS-backups"


def test_definitive_creation_rejection_is_not_reported_as_uncertain(backups):
    manager, service, repo = backups
    manager.supervisor.error = SupervisorRejected(
        "Supervisor rechazó la operación.", "supervisor_rejected"
    )
    with pytest.raises(SupervisorRejected) as caught:
        service.create(repo, "demo")
    assert caught.value.code == "supervisor_rejected"
    assert not manager.supervisor.backups


def test_interrupted_backup_job_never_replays_or_persists_password(backups):
    from app.storage import atomic_json

    manager, _, _ = backups
    jobs = Jobs(manager)
    jobs.close()
    atomic_json(
        jobs.path,
        {
            "interrupted-backup": {
                "id": "interrupted-backup",
                "kind": "backup_restore",
                "resource": "repo:test",
                "status": "running",
                "stage": "backupRestoring",
            }
        },
    )
    before = list(manager.supervisor.calls)
    restarted = Jobs(manager)
    try:
        item = restarted.snapshot()["interrupted-backup"]
        assert item["status"] == "interrupted"
        assert manager.supervisor.calls == before
        assert "password" not in restarted.path.read_text()
    finally:
        restarted.close()
