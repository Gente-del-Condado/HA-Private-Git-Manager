import asyncio
import copy
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from app import main
from app.backups import Backups
from app.core import BackupDownload, Problem, Supervisor, SupervisorUncertain
from app.jobs import Jobs
from fastapi.testclient import TestClient
from test_backups import HEADERS, BackupSupervisor, finish_job
from test_backups import backups as backups
from test_manager import manager as manager

ARCHIVE = b"original-backup\x00" + bytes(range(256)) * 3000


class ArchiveStream(httpx.SyncByteStream):
    def __init__(self):
        self.reads = 0
        self.closed = False
        self.fail = False

    def __iter__(self):
        for offset in range(0, len(ARCHIVE), 16384):
            self.reads += 1
            yield ARCHIVE[offset : offset + 16384]
            if self.fail:
                raise httpx.ReadError("do-not-echo-upstream-secret")

    def close(self):
        self.closed = True


class TransferSupervisor(BackupSupervisor):
    def __init__(self):
        super().__init__()
        self.streams = []
        self.download_paths = []
        self.keep_backup = False
        self.download_status = 200

    def backup_download(self, path):
        self.download_paths.append(path)
        source = ArchiveStream()
        self.streams.append(source)

        def handler(request):
            assert request.headers["authorization"] == "Bearer private-upstream-token"
            assert request.headers["accept-encoding"] == "identity"
            return httpx.Response(
                self.download_status,
                stream=source,
                headers={
                    "Content-Type": "application/x-tar",
                    "Content-Length": str(len(ARCHIVE)),
                    "Set-Cookie": "upstream-private-cookie",
                    "Content-Disposition": 'attachment; filename="untrusted-name.tar"',
                },
            )

        return BackupDownload("private-upstream-token", httpx.MockTransport(handler), path)

    def call(self, method, path, payload=None):
        if method != "DELETE":
            return super().call(method, path, payload)
        self.calls.append((method, path))
        self.payloads.append((method, path, copy.deepcopy(payload)))
        if self.error:
            raise self.error
        if not self.keep_backup:
            selected = path.split("/")[2]
            backup = self.backups[selected]
            remaining = [
                value
                for value in backup.get("locations", [backup.get("location")])
                if value not in payload["location"]
            ]
            if remaining:
                backup["locations"] = remaining
                backup["location"] = remaining[0]
            else:
                del self.backups[selected]
        return {}


@pytest.fixture
def transfers(backups):
    manager, _, repo = backups
    original = manager.supervisor
    manager.supervisor = TransferSupervisor()
    manager.supervisor.__dict__.update(original.__dict__)
    service = Backups(manager)
    service.create(repo, "demo", "Transfer test", "native-password")
    return manager, service, repo


def test_download_stream_is_lazy_exact_and_closed(transfers):
    manager, service, repo = transfers
    revision = service.details(repo, "demo", "backup1")["revision"]
    stream = service.download(repo, "demo", "backup1", revision)
    source = manager.supervisor.streams[-1]
    assert source.reads == 0
    assert not source.closed
    chunks = list(stream.chunks())
    assert b"".join(chunks) == ARCHIVE
    assert max(map(len, chunks)) <= 64 * 1024
    assert source.closed
    assert stream.client.is_closed
    assert manager.supervisor.download_paths == ["/backups/backup1/download?location="]
    assert "native-password" not in manager.log_path.read_text()


def test_download_preserves_remote_location_and_stops_early(transfers):
    manager, service, repo = transfers
    manager.supervisor.backups["backup1"]["location"] = "NAS & backup"
    revision = service.details(repo, "demo", "backup1")["revision"]
    stream = service.download(repo, "demo", "backup1", revision)
    iterator = stream.chunks()
    assert next(iterator)
    iterator.close()
    assert manager.supervisor.streams[-1].closed
    assert manager.supervisor.streams[-1].reads < 10
    query = parse_qs(urlsplit(manager.supervisor.download_paths[-1]).query)
    assert query == {"location": ["NAS & backup"]}


@pytest.mark.parametrize(
    "status,mime",
    [
        (404, "application/x-tar"),
        (403, "application/json"),
        (302, "application/x-tar"),
        (200, "application/json"),
    ],
)
def test_upstream_download_errors_are_closed_and_not_returned_as_archives(status, mime):
    source = ArchiveStream()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, stream=source, headers={"Content-Type": mime})
    )
    with pytest.raises(Problem) as caught:
        BackupDownload("private-token", transport, "/backups/example/download")
    assert caught.value.code == "backup_download_failed"
    assert "private-token" not in str(caught.value)
    assert source.closed and source.reads == 0


def test_mid_download_failure_closes_stream_and_hides_diagnostics(transfers):
    manager, service, repo = transfers
    stream = service.download(
        repo, "demo", "backup1", service.details(repo, "demo", "backup1")["revision"]
    )
    source = manager.supervisor.streams[-1]
    source.fail = True
    with pytest.raises(Problem) as caught:
        list(stream.chunks())
    assert caught.value.code == "backup_download_failed"
    assert "do-not-echo" not in str(caught.value)
    assert source.closed and stream.client.is_closed


def test_response_closes_upstream_even_if_client_disconnects_before_first_chunk(transfers):
    manager, service, repo = transfers
    stream = service.download(
        repo, "demo", "backup1", service.details(repo, "demo", "backup1")["revision"]
    )
    response = main.BackupStreamingResponse(stream, "backup1")

    async def send(message):
        raise OSError("client disconnected")

    async def receive():
        return {"type": "http.disconnect"}

    async def exercise():
        try:
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        except Exception:
            pass

    asyncio.run(exercise())
    assert manager.supervisor.streams[-1].closed
    assert stream.client.is_closed


def test_delete_shared_backup_from_reviewed_locations_and_keep_cloud(transfers):
    manager, service, repo = transfers
    native = manager.supervisor.backups["backup1"]
    native.update(type="full", locations=[None, "NAS", ".cloud_backup"], homeassistant="2026.11.0")
    native["addons"].append({"slug": "core_other", "version": "2"})
    detail = service.details(repo, "demo", "backup1")
    assert detail["other_content"] is True
    assert detail["locations"] == [None, "NAS"]
    before = copy.deepcopy(manager.supervisor.installed)
    assert service.delete(repo, "demo", "backup1", detail["revision"])["ok"]
    payload = next(p for method, _, p in manager.supervisor.payloads if method == "DELETE")
    assert payload == {"location": [None, "NAS"]}
    assert manager.supervisor.backups["backup1"]["location"] == ".cloud_backup"
    assert manager.supervisor.installed == before
    assert service.list(repo, "demo")["backups"] == []


@pytest.mark.parametrize("operation", ["delete", "download"])
def test_changed_backup_and_wrong_owner_prevent_transfer(transfers, operation):
    manager, service, repo = transfers
    revision = service.details(repo, "demo", "backup1")["revision"]
    manager.supervisor.backups["backup1"]["locations"] = [None, "new-NAS"]
    with pytest.raises(Problem) as caught:
        getattr(service, operation)(repo, "demo", "backup1", revision)
    assert caught.value.code == "backup_changed"
    other = manager.repo_add("Other", "https://example.org/other/repo", "main")
    with pytest.raises(Problem) as caught:
        getattr(service, operation)(other, "demo", "backup1", revision)
    assert caught.value.code == "slug_owned"
    assert not manager.supervisor.streams
    assert not any(method == "DELETE" for method, _ in manager.supervisor.calls)


def test_delete_pending_transaction_and_partial_or_uncertain_result(transfers):
    manager, service, repo = transfers
    revision = service.details(repo, "demo", "backup1")["revision"]
    manager.state["transactions"]["demo"] = {"status": "pending"}
    manager.save()
    with pytest.raises(Problem) as caught:
        service.delete(repo, "demo", "backup1", revision)
    assert caught.value.code == "recovery_required"
    manager.state["transactions"].clear()
    manager.save()
    manager.supervisor.keep_backup = True
    with pytest.raises(Problem) as caught:
        service.delete(repo, "demo", "backup1", revision)
    assert caught.value.code == "backup_delete_uncertain"
    manager.supervisor.error = SupervisorUncertain("timeout", "supervisor_uncertain")
    before = len(manager.supervisor.calls)
    with pytest.raises(Problem) as caught:
        service.delete(repo, "demo", "backup1", revision)
    assert caught.value.code == "backup_delete_uncertain"
    assert sum(method == "DELETE" for method, _ in manager.supervisor.calls[before:]) == 1


def test_supervisor_delete_sends_json_and_timeout_remains_uncertain(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "private-test-token")

    def handler(request):
        assert request.method == "DELETE"
        assert json.loads(request.content) == {"location": [None, "NAS"]}
        assert request.extensions["timeout"]["read"] == 900
        return httpx.Response(200, json={"result": "ok", "data": {}})

    supervisor = Supervisor(httpx.MockTransport(handler))
    assert supervisor.call("DELETE", "/backups/backup1", {"location": [None, "NAS"]}) == {}

    def timeout(request):
        raise httpx.ReadTimeout("private-secret")

    supervisor.transport = httpx.MockTransport(timeout)
    with pytest.raises(SupervisorUncertain) as caught:
        supervisor.call("DELETE", "/backups/backup1", {"location": [None]})
    assert "private-secret" not in str(caught.value)


def test_api_download_and_delete_confirmation_and_idempotency(transfers, monkeypatch):
    manager, service, repo = transfers
    jobs = Jobs(manager)
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "jobs", jobs)
    client = TestClient(main.app)
    base = f"/api/repos/{repo}/apps/demo/backups/backup1"
    revision = service.details(repo, "demo", "backup1")["revision"]
    try:
        response = client.get(base + "/download", params={"expected_revision": revision})
        assert response.status_code == 200 and response.content == ARCHIVE
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="ha-backup-backup1.tar"'
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "application/x-tar"
        assert response.headers["content-length"] == str(len(ARCHIVE))
        assert "set-cookie" not in response.headers
        assert "private-upstream" not in str(response.headers)
        assert client.get(base + "/download").status_code == 422
        assert (
            client.post(base + "/delete", json={"expected_revision": revision}).status_code == 403
        )
        assert (
            client.post(
                base + "/delete", json={"expected_revision": revision}, headers=HEADERS
            ).json()["code"]
            == "confirmation_required"
        )
        body = {"confirmed": True, "expected_revision": revision}
        headers = {**HEADERS, "Idempotency-Key": "delete-once"}
        response = client.post(base + "/delete", json=body, headers=headers)
        assert response.status_code == 202
        assert finish_job(jobs, response.json()["id"])["status"] == "succeeded"
        assert (
            client.post(base + "/delete", json=body, headers=headers).json()["id"]
            == response.json()["id"]
        )
        assert sum(method == "DELETE" for method, _ in manager.supervisor.calls) == 1
        assert not manager.supervisor.backups
        assert "private-upstream" not in jobs.path.read_text() + manager.log_path.read_text()
    finally:
        jobs.executor.shutdown(wait=True)


def test_uninstalled_app_backups_can_be_downloaded_and_deleted(transfers):
    manager, service, repo = transfers
    manager.supervisor.installed.clear()
    source = (manager.addons / "demo" / "config.yaml").read_bytes()
    detail = service.details(repo, "demo", "backup1")
    stream = service.download(repo, "demo", "backup1", detail["revision"])
    assert b"".join(stream.chunks()) == ARCHIVE
    assert service.delete(repo, "demo", "backup1", detail["revision"])["ok"]
    assert (manager.addons / "demo" / "config.yaml").read_bytes() == source


@pytest.mark.parametrize("operation", ["delete", "download"])
def test_copy_without_selected_app_is_not_transferable(transfers, operation):
    manager, service, repo = transfers
    revision = service.details(repo, "demo", "backup1")["revision"]
    manager.supervisor.backups["backup1"]["addons"] = [{"slug": "local_other", "version": "2"}]
    with pytest.raises(Problem) as caught:
        getattr(service, operation)(repo, "demo", "backup1", revision)
    assert caught.value.code == "backup_app_missing"
    assert not manager.supervisor.streams
    assert not any(method == "DELETE" for method, _ in manager.supervisor.calls)


def test_download_closed_if_audit_record_cannot_be_written(transfers, monkeypatch):
    manager, service, repo = transfers
    revision = service.details(repo, "demo", "backup1")["revision"]

    def disk_full(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(manager, "event", disk_full)
    with pytest.raises(OSError):
        service.download(repo, "demo", "backup1", revision)
    assert manager.supervisor.streams[-1].closed
