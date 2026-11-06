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


def test_private_document_api_and_raster_assets(client):
    import shutil
    from pathlib import Path

    from test_manager import prepared

    repo_id, root = prepared(main.manager)
    (root / "README.md").write_text("# Documentación privada\n\n**Hola**")
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "private_git_manager/icon.png", root / "icon.png"
    )
    document = client.get(f"/api/repos/{repo_id}/document")
    assert document.status_code == 200
    assert "<strong>Hola</strong>" in document.json()["html"]
    image = client.get(f"/api/repos/{repo_id}/asset?path=icon.png")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.headers["cross-origin-resource-policy"] == "same-origin"
    assert client.get(f"/api/repos/{repo_id}/document?path=../README.md").status_code == 400
    assert client.get(f"/api/repos/{repo_id}/document?path=.git/config.md").status_code == 400


def test_remove_api_requires_confirmation_and_runs_in_background(client):
    import time

    from test_manager import FakeSupervisor, addon, prepared

    manager = main.manager
    manager.supervisor = FakeSupervisor()
    repo_id, _ = prepared(manager)
    addon(manager.addons / "demo")
    preflight = client.post(
        f"/api/repos/{repo_id}/remove-preflight", json={"slug": "demo"}, headers=HEADERS
    )
    assert preflight.status_code == 200
    body = {"slug": "demo", "expected_local_digest": preflight.json()["local_digest"]}
    response = client.post(f"/api/repos/{repo_id}/remove-app", json=body, headers=HEADERS)
    assert response.status_code == 400 and response.json()["code"] == "confirmation_required"
    assert (manager.addons / "demo").exists()
    body["confirmed"] = True
    assert client.post(f"/api/repos/{repo_id}/remove-app", json=body).status_code == 403
    response = client.post(f"/api/repos/{repo_id}/remove-app", json=body, headers=HEADERS)
    assert response.status_code == 202
    for _ in range(200):
        job = main.jobs.snapshot()[response.json()["id"]]
        if job["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.01)
    assert job["status"] == "succeeded"
    assert not (manager.addons / "demo").exists()
    assert manager.repo(repo_id)["hidden_apps"] == ["demo"]
    assert (
        client.post(
            f"/api/repos/{repo_id}/restore-app", json={"slug": "demo"}, headers=HEADERS
        ).status_code
        == 200
    )
    assert not manager.repo(repo_id)["hidden_apps"]


def test_uninstall_api_requires_consent_and_verifies_native_result(client):
    from test_jobs_recovery import wait_job
    from test_manager import FakeSupervisor, prepared

    manager = main.manager
    manager.supervisor = FakeSupervisor()
    manager.supervisor.addons = manager.addons
    manager.verify_checkout = lambda repo, root: None
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    preflight = client.post(
        f"/api/repos/{repo_id}/remove-preflight", json={"slug": "demo"}, headers=HEADERS
    )
    assert preflight.status_code == 200 and preflight.json()["installed"]
    body = {"slug": "demo", "expected_local_digest": preflight.json()["local_digest"]}
    url = f"/api/repos/{repo_id}/uninstall-app"
    assert client.post(url, json=body, headers=HEADERS).status_code == 400
    body["confirmed"] = True
    assert client.post(url, json=body).status_code == 403
    response = client.post(url, json=body, headers=HEADERS)
    assert response.status_code == 202
    assert wait_job(main.jobs, response.json()["id"])["status"] == "succeeded"
    assert not manager.installed_info("demo")
    assert (manager.addons / "demo/payload").exists()
    assert (
        "POST",
        "/addons/local_demo/uninstall",
        {"remove_config": False},
    ) in manager.supervisor.payloads


def test_app_configuration_and_logs_api_keep_secrets_out_of_history(client):
    from test_application import ControlsSupervisor
    from test_jobs_recovery import wait_job
    from test_manager import prepared

    manager = main.manager
    manager.supervisor = ControlsSupervisor()
    manager.supervisor.addons = manager.addons
    manager.verify_checkout = lambda repo, root: None
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    base = f"/api/repos/{repo_id}/apps/demo"
    response = client.get(base + "/configuration")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    config = response.json()
    body = {
        "yaml": "options: {password: new-private-setting}",
        "expected_revision": config["revision"],
    }
    assert client.post(base + "/configuration", json=body, headers=HEADERS).status_code == 400
    body["confirmed"] = True
    assert client.post(base + "/configuration", json=body).status_code == 403
    response = client.post(base + "/configuration", json=body, headers=HEADERS)
    assert response.status_code == 202
    assert wait_job(main.jobs, response.json()["id"])["status"] == "succeeded"
    assert "new-private-setting" not in main.jobs.path.read_text()
    assert "new-private-setting" not in manager.state_file.read_text()
    assert "new-private-setting" not in client.get("/api/state").text
    manager.supervisor.log_text = "password: new-private-setting\nReady\n"
    logs = client.get(base + "/logs")
    assert logs.status_code == 200 and "new-private-setting" not in logs.text
    download = client.get(base + "/logs?download=true")
    assert download.headers["content-type"].startswith("text/plain")
    assert 'filename="demo.log"' in download.headers["content-disposition"]
    assert "new-private-setting" not in download.text
    assert client.get("/api/repos/missing/apps/demo/logs").status_code == 400


def test_native_form_metadata_and_conversion_are_private_and_read_only(client):
    from test_manager import prepared
    from test_schema_form_ui import NativeSchemaSupervisor

    manager = main.manager
    manager.supervisor = NativeSchemaSupervisor()
    manager.supervisor.addons = manager.addons
    manager.verify_checkout = lambda repo, root: None
    repo_id, _ = prepared(manager)
    manager.deploy(repo_id, "demo")
    base = f"/api/repos/{repo_id}/apps/demo/configuration"
    config = client.get(base)
    assert config.status_code == 200 and config.headers["cache-control"] == "no-store"
    data = config.json()
    assert data["schema"] == manager.supervisor.schema
    assert data["translations"]["es"]["configuration"]["count"]["name"] == "Intentos"
    body = {"yaml": json.dumps(data["values"])}
    assert client.post(base + "/convert", json=body).status_code == 403
    converted = client.post(base + "/convert", json=body, headers=HEADERS)
    assert converted.status_code == 200
    assert converted.json()["values"] == data["values"]
    assert not main.jobs.snapshot()
    assert "native-app-secret" not in manager.state_file.read_text()
    assert "native-app-secret" not in client.get("/api/state").text
    assert client.get("/static/schema-form.js").status_code == 200
