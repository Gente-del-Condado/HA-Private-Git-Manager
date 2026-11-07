import io
import json
import tarfile
import time

from app import main
from app.core import Problem
from app.jobs import Jobs, Scheduler
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_backup_transfers import transfers as transfers
from test_backups import HEADERS, finish_job
from test_backups import backups as backups
from test_manager import addon
from test_manager import manager as manager


def archive_for(slug):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        manifest = json.dumps(
            {
                "slug": "imported1",
                "addons": [{"slug": slug, "version": "1.0.0"}],
            }
        ).encode()
        for name, body in [("./backup.json", manifest), (f"./{slug}.tar.gz", b"test" * 25000)]:
            item = tarfile.TarInfo(name)
            item.size = len(body)
            tar.addfile(item, io.BytesIO(body))
    return archive.getvalue()


def test_import_upload_checks_app_before_supervisor_and_never_restores(transfers, monkeypatch):
    manager, service, repo = transfers
    monkeypatch.setattr(main, "manager", manager)
    proxy = FastAPI()
    prefix = "/api/hassio_ingress/test"
    proxy.mount(prefix, main.app)
    client = TestClient(proxy)
    path = f"{prefix}/api/repos/{repo}/apps/demo/backups/import"
    headers = {**HEADERS, "Content-Type": "application/x-tar"}
    valid = archive_for("local_demo")

    def upload(stream):
        assert stream.read() == valid
        result = dict(manager.supervisor.backups["backup1"], slug="imported1")
        manager.supervisor.backups["imported1"] = result
        return {"slug": "imported1"}

    monkeypatch.setattr(manager.supervisor, "backup_upload", upload, raising=False)
    assert client.post(path, content=valid).status_code == 403
    assert (
        client.post(path, content=archive_for("local_other"), headers=headers).json()["code"]
        == "backup_app_missing"
    )
    response = client.post(path, content=valid, headers=headers)
    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"
    assert (
        client.post(path, content=valid, headers=headers).json()["code"]
        == "backup_import_duplicate"
    )
    assert not any("/restore/" in path for _, path in manager.supervisor.calls)
    assert len(service.list(repo, "demo")["backups"]) == 2


def test_backup_failure_blocks_update_through_api(transfers, monkeypatch):
    manager, _, repo = transfers
    checkout = manager.data / "repos" / repo / "demo"
    addon(checkout, "2.0.0")
    record = manager.repo(repo)
    record["apps"] = manager.discover(checkout.parent)
    record["commit"] = "b" * 40
    manager.save()
    jobs = Jobs(manager)
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "jobs", jobs)
    manager.supervisor.error = Problem("Copia simulada fallida.", "supervisor_rejected")
    try:
        response = TestClient(main.app).post(
            f"/api/repos/{repo}/deploy",
            json={
                "slug": "demo",
                "confirmed": True,
                "backup_first": True,
                "expected_commit": record["commit"],
            },
            headers=HEADERS,
        )
        assert response.status_code == 202
        assert finish_job(jobs, response.json()["id"])["status"] == "failed"
        assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
        manager.supervisor.error = None
        response = TestClient(main.app).post(
            f"/api/repos/{repo}/deploy",
            json={
                "slug": "demo",
                "confirmed": True,
                "backup_first": True,
                "expected_commit": record["commit"],
            },
            headers=HEADERS,
        )
        assert finish_job(jobs, response.json()["id"])["status"] == "succeeded"
        assert (manager.addons / "demo" / "payload").read_text() == "2.0.0"
        assert manager.supervisor.backups["backup2"]["addons"][0]["version"] == "1.0.0"
    finally:
        jobs.executor.shutdown(wait=True)


def test_schedule_prunes_only_its_local_copy(transfers):
    manager, service, repo = transfers
    service.configure_schedule(repo, "demo", 1, 1)
    schedule = manager.repo(repo)["backup_schedules"]["demo"]
    jobs = Jobs(manager)
    scheduler = Scheduler(manager, jobs)
    try:
        for _ in range(2):
            schedule["next_at"] = time.time() - 1
            manager.save()
            scheduler.tick()
            job = list(jobs.snapshot().values())[-1]
            assert finish_job(jobs, job["id"])["status"] == "succeeded"
            if len(manager.supervisor.backups) == 2:
                manager.supervisor.backups["backup2"]["locations"] = [None, "NAS"]
        assert set(manager.supervisor.backups) == {"backup1", "backup2", "backup3"}
        assert manager.supervisor.backups["backup2"]["locations"] == ["NAS"]
        assert [item["slug"] for item in schedule["copies"]] == ["backup3"]
        assert schedule["last_success"] > 0
        assert schedule["next_at"] > time.time()
    finally:
        jobs.executor.shutdown(wait=True)
