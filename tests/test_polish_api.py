import json
import threading
import time
from pathlib import Path

import pytest
from app import main
from app.core import Manager
from app.jobs import Jobs
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    manager = Manager(tmp_path / "data", tmp_path / "addons")
    queue = Jobs(manager)
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "jobs", queue)
    yield TestClient(main.app)
    queue.close()


HEADERS = {"X-PGM-Request": "1"}


def test_validation_does_not_echo_a_submitted_token(client):
    response = client.post("/api/repos", json={"token": "do-not-echo-this-secret"}, headers=HEADERS)
    assert response.status_code == 422
    assert "do-not-echo" not in response.text
    assert response.json()["code"] == "validation"


def test_body_limit_including_chunked_encoding(client):
    response = client.post("/api/repos", content=iter([b"x" * 10000] * 4), headers=HEADERS)
    assert response.status_code == 413


def test_production_accepts_ingress_peer_and_rejects_spoofed_headers(monkeypatch):
    monkeypatch.delenv("PGM_DEV", raising=False)
    ingress = TestClient(main.app, client=("172.30.32.2", 12345))
    outside = TestClient(main.app, client=("192.168.1.10", 12345))
    assert ingress.get("/").status_code == 200
    assert ingress.get("/health").json() == {"ok": True}
    assert outside.get("/api/state", headers={"X-Forwarded-For": "172.30.32.2"}).status_code == 403
    assert TestClient(main.app, client=("127.0.0.1", 1234)).get("/health").json() == {"ok": True}
    assert TestClient(main.app, client=("127.0.0.1", 1234)).get("/api/state").status_code == 403


def test_interface_and_assets_under_ingress_prefix(client):
    proxy = FastAPI()
    proxy.mount("/api/hassio_ingress/test-token", main.app)
    browser = TestClient(proxy)
    base = "/api/hassio_ingress/test-token/"
    response = browser.get(base)
    assert response.status_code == 200
    assert 'src="static/app.js"' in response.text
    assert 'href="static/style.css"' in response.text
    for path in ["api/state", "static/app.js", "static/locales/es.json", "static/locales/en.json"]:
        assert browser.get(base + path).status_code == 200


def test_long_sync_returns_202_and_polling_remains_available(client, monkeypatch):
    repo_id = main.manager.repo_add("Public", "https://example.org/u/r", "main")
    started, finish = threading.Event(), threading.Event()

    def slow(repo):
        started.set()
        finish.wait(timeout=5)

    monkeypatch.setattr(main.manager, "sync", slow)
    try:
        response = client.post(f"/api/repos/{repo_id}/sync", headers=HEADERS)
        assert response.status_code == 202
        assert started.wait(timeout=2)
        start = time.monotonic()
        snapshot = client.get("/api/state")
        assert snapshot.status_code == 200
        assert time.monotonic() - start < 0.5
        assert snapshot.json()["jobs"][response.json()["id"]]["status"] == "running"
        assert client.post("/api/keys", json={"name": "busy"}, headers=HEADERS).status_code == 409
    finally:
        finish.set()
        for _ in range(200):
            if main.jobs.snapshot()[response.json()["id"]]["status"] not in {"queued", "running"}:
                break
            time.sleep(0.01)


def test_log_translation_filtering_and_export(client):
    main.manager.event("key_created", key_id="example")
    main.manager.event("job_failed", "error", error="An isolated test error")
    spanish = client.get("/api/logs?language=es").json()["events"]
    english = client.get("/api/logs?language=en").json()["events"]
    assert spanish[0]["message"] == "Operación fallida."
    assert english[0]["message"] == "Operation failed."
    filtered = client.get("/api/logs?level=error").json()["events"]
    assert len(filtered) == 1
    export = client.get("/api/logs?download=true&language=en")
    assert "attachment" in export.headers["content-disposition"]
    assert "SSH key created." in export.text


def test_complete_language_catalogs_and_manifest_version():
    root = Path(__file__).resolve().parents[1]
    catalogs = [
        json.loads((root / "private_git_manager/app/static/locales" / (lang + ".json")).read_text())
        for lang in ["es", "en"]
    ]
    assert catalogs[0].keys() == catalogs[1].keys()
    assert catalogs[0]["events"].keys() == catalogs[1]["events"].keys()
    assert len(catalogs[0]) > 170
    import yaml

    manifest = yaml.safe_load((root / "private_git_manager/config.yaml").read_text())
    assert manifest["version"] == main.VERSION
    assert manifest["ingress"] and manifest["panel_admin"]
    assert "ports" not in manifest


def test_preflight_api_reports_collision_without_claiming_folder(client):
    from test_manager import FakeSupervisor, addon, prepared

    fake = FakeSupervisor()
    fake.addons = main.manager.addons
    main.manager.supervisor = fake
    repo_id, _ = prepared(main.manager)
    addon(main.manager.addons / "demo", "0.5.0")
    response = client.post(
        f"/api/repos/{repo_id}/preflight", headers=HEADERS, json={"slug": "demo"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_adoption"] and not body["installed"]
    assert len(body["local_digest"]) == 64
    assert not main.manager.state["deployments"]
