import copy
import io
import json
import shutil
import subprocess
import tarfile
import time

import pytest
from app import backup_git, main
from app.core import Problem
from app.jobs import Jobs, Scheduler
from fastapi.testclient import TestClient
from test_adoption_ui import adoption_server as adoption_server
from test_backups import HEADERS, finish_job
from test_backups import backups as backups
from test_backups_ui import backup_server as backup_server
from test_manager import manager as manager

PASSWORD = "scheduled-native-password"


def native_tar(backup):
    archive = io.BytesIO()
    fields = {key: backup[key] for key in ("slug", "addons", "type", "protected")}
    with tarfile.open(fileobj=archive, mode="w") as tar:
        for name, data in (
            ("backup.json", json.dumps(fields).encode()),
            ("local_demo.tar.gz", b"contenido cifrado simulado" * 1024),
        ):
            item = tarfile.TarInfo(name)
            item.size = len(data)
            tar.addfile(item, io.BytesIO(data))
    return archive.getvalue()


class Stream(io.BytesIO):
    def chunks(self):
        while data := self.read(1024):
            yield data


@pytest.fixture
def destination(backups, monkeypatch, tmp_path):
    manager, _, _ = backups
    return local_destination(manager, monkeypatch, tmp_path)


def local_destination(manager, monkeypatch, tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(bare)], check=True)
    url = "ssh://git@example.test/group/backup.git"
    real_env = manager.git_env

    def env(repo):
        if repo["url"] != url:
            return real_env(repo)
        return dict(
            manager.local_git_env(),
            GIT_ALLOW_PROTOCOL="file",
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0=f"url.{bare}.insteadOf",
            GIT_CONFIG_VALUE_0=url,
        )

    monkeypatch.setattr(manager, "git_env", env)
    monkeypatch.setattr(backup_git, "CHUNK", 4096)
    return manager.repo_add("Copias privadas", url, "main", key_id="fixture")


def test_scheduled_git_backup_and_restore(backups, destination, monkeypatch):
    manager, service, repo = backups
    supervisor = manager.supervisor
    downloads = []

    def download(path):
        selected = path.split("/")[2]
        data = native_tar(supervisor.backups[selected])
        downloads.append(data)
        return Stream(data)

    monkeypatch.setattr(supervisor, "backup_download", download, raising=False)
    monkeypatch.setattr(main, "manager", manager)
    jobs = Jobs(manager)
    monkeypatch.setattr(main, "jobs", jobs)
    scheduler = Scheduler(manager, jobs)
    client = TestClient(main.app)
    path = f"/api/repos/{repo}/apps/demo/backups"
    try:
        params = {"hours": 1, "keep": 2, "destination": destination}
        assert (
            client.post(path + "/schedule", json=params, headers=HEADERS).json()["code"]
            == "backup_git_password"
        )
        assert client.post(
            path + "/schedule", json={**params, "password": PASSWORD}, headers=HEADERS
        ).is_success
        assert client.post(path + "/schedule", json=params, headers=HEADERS).is_success
        schedule = manager.repo(repo)["backup_schedules"]["demo"]
        assert PASSWORD not in client.get("/api/state").text
        assert manager.state_file.stat().st_mode & 0o777 == 0o600
        schedule["next_at"] = time.time() - 1
        manager.save()

        def fail(*args):
            raise Problem("Error de red simulado.", "backup_git_failed")

        with monkeypatch.context() as failure:
            failure.setattr(backup_git.BackupGit, "export", fail)
            scheduler.tick()
            job = list(jobs.snapshot().values())[-1]
            assert finish_job(jobs, job["id"])["code"] == "backup_git_failed"
        assert schedule["git_pending"]["slug"] == "backup1"
        assert len(supervisor.backups) == 1
        schedule["next_at"] = time.time() - 1
        manager.save()
        scheduler.tick()
        job = list(jobs.snapshot().values())[-1]
        assert finish_job(jobs, job["id"])["status"] == "succeeded"
        assert len(supervisor.backups) == 1
        assert "git_pending" not in schedule
        listing = client.get(path + "/git", params={"destination": destination}).json()["copies"]
        [saved] = listing
        revision = service.details(repo, "demo", "backup1")["revision"]
        assert (
            service.git_export(repo, "demo", destination, "backup1", revision)["commit"]
            == saved["commit"]
        )

        original = supervisor.backups.pop("backup1")
        supervisor.settings["options"]["username"] = "changed"

        def upload(stream):
            assert stream.read() == downloads[0]
            supervisor.backups["backup1"] = copy.deepcopy(original)
            return {"slug": "backup1"}

        monkeypatch.setattr(supervisor, "backup_upload", upload, raising=False)
        response = client.post(
            path + "/git",
            json={
                "confirmed": True,
                "destination": destination,
                "copy_id": saved["id"],
                "commit": "a" * 40,
            },
            headers=HEADERS,
        )
        assert finish_job(jobs, response.json()["id"])["code"] == "backup_git_changed"
        response = client.post(
            path + "/git",
            json={
                "confirmed": True,
                "destination": destination,
                "copy_id": saved["id"],
                "commit": saved["commit"],
            },
            headers=HEADERS,
        )
        assert finish_job(jobs, response.json()["id"])["status"] == "succeeded"
        assert not supervisor.restore_started.is_set()
        for password, expected in (("incorrecta", "failed"), (PASSWORD, "succeeded")):
            response = client.post(
                path + "/backup1/restore",
                json={
                    "confirmed": True,
                    "password": password,
                },
                headers=HEADERS,
            )
            assert finish_job(jobs, response.json()["id"])["status"] == expected
        assert supervisor.settings == original["_settings"]
        assert PASSWORD not in (manager.data / "jobs.json").read_text()
        assert PASSWORD not in manager.log_path.read_text()
        assert client.post(
            path + "/schedule", json={**params, "hours": 0}, headers=HEADERS
        ).is_success
        assert PASSWORD not in manager.state_file.read_text()
    finally:
        jobs.executor.shutdown(wait=True)


def test_git_export_rejects_unencrypted_and_shared_archives(backups, destination):
    manager, service, repo = backups
    service.create(repo, "demo")
    for protected in (False, True):
        backup = manager.supervisor.backups["backup1"]
        backup["protected"] = protected
        if protected:
            backup["type"] = "full"
        detail = service.details(repo, "demo", "backup1")
        with pytest.raises(Problem) as caught:
            service.git_export(repo, "demo", destination, "backup1", detail["revision"])
        assert caught.value.code == "backup_git_encrypted"
    assert service.git_copies(repo, "demo", destination) == {"copies": []}


def test_git_backup_portal(backup_server, monkeypatch, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = backup_server
    repo = next(iter(manager.state["repos"]))
    remote = local_destination(manager, monkeypatch, tmp_path)
    supervisor = manager.supervisor
    path = f"/api/repos/{repo}/apps/demo/backups"
    client = TestClient(main.app)
    response = client.post(path, json={"confirmed": True, "password": PASSWORD}, headers=HEADERS)
    assert finish_job(jobs, response.json()["id"])["status"] == "succeeded"
    original = copy.deepcopy(supervisor.backups["backup1"])
    archive = native_tar(original)
    monkeypatch.setattr(supervisor, "backup_download", lambda _: Stream(archive), raising=False)

    def upload(stream):
        assert stream.read() == archive
        supervisor.backups["backup1"] = copy.deepcopy(original)
        return {"slug": "backup1"}

    monkeypatch.setattr(supervisor, "backup_upload", upload, raising=False)

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(url)
        dialog = page.get_by_role("dialog")
        backups_button = page.get_by_role("button", name="Copias de seguridad", exact=True)
        backups_button.click()
        dialog.get_by_role("button", name="Guardar en Git", exact=True).click()
        dialog.get_by_label("Repositorio privado por SSH").select_option(remote)
        dialog.get_by_role("button", name="Guardar en Git", exact=True).click()
        playwright.expect(dialog).not_to_be_visible()
        job = list(jobs.snapshot().values())[-1]
        assert finish_job(jobs, job["id"])["status"] == "succeeded"
        del supervisor.backups["backup1"]
        supervisor.settings["options"]["username"] = "changed"
        backups_button.click()
        dialog.get_by_role("button", name="Recuperar desde Git").click()
        dialog.get_by_label("Repositorio privado por SSH").select_option(remote)
        dialog.get_by_role("button", name="Buscar copias").click()
        playwright.expect(dialog.get_by_label("Copia cifrada")).to_contain_text("backup1")
        dialog.get_by_role("button", name="Importar copia", exact=True).click()
        playwright.expect(dialog.get_by_role("heading")).to_have_text("Restaurar copia: demo")
        consent = dialog.locator("#backup-restore-consent")
        playwright.expect(consent).not_to_be_checked()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        dialog.get_by_label("Contraseña de la copia", exact=True).fill(PASSWORD)
        consent.check()
        dialog.get_by_role("button", name="Restaurar copia", exact=True).click()
        playwright.expect(dialog).not_to_be_visible()
        job = list(jobs.snapshot().values())[-1]
        assert finish_job(jobs, job["id"])["status"] == "succeeded"
        assert supervisor.settings == original["_settings"]
        browser.close()
