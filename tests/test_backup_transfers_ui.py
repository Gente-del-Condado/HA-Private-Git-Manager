import shutil
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import uvicorn
from app import main
from app.backups import Backups
from fastapi import FastAPI
from test_adoption_ui import adoption_server as adoption_server
from test_backup_transfers import ARCHIVE, TransferSupervisor
from test_backups_ui import backup_server as backup_server


@contextmanager
def prefixed_server(original_url, ingress):
    if not ingress:
        yield original_url
        return
    prefix = "/api/hassio_ingress/manager-session"
    proxy = FastAPI()
    proxy.mount(prefix, main.app)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(proxy, log_level="error", access_log=False, lifespan="off")
        )
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.01)
        assert server.started
        try:
            yield f"http://127.0.0.1:{port}{prefix}/"
        finally:
            server.should_exit = True
            worker.join(timeout=5)


@pytest.fixture
def transfer_server(backup_server):
    url, manager, jobs = backup_server
    original = manager.supervisor
    manager.supervisor = TransferSupervisor()
    manager.supervisor.__dict__.update(original.__dict__)
    repo = next(iter(manager.state["repos"]))
    Backups(manager).create(
        repo, "demo", "Shared <script>window.transferXss=true</script>", "encrypted-password"
    )
    manager.supervisor.backups["backup1"].update(type="full", locations=[None, "NAS"])
    manager.supervisor.backups["backup1"]["addons"].append({"slug": "core_other", "version": "2"})
    return url, manager, jobs


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("ingress", [False, True])
def test_download_and_delete_shared_encrypted_backup_with_consent(
    transfer_server, language, ingress
):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = transfer_server
    labels = {
        "es": (
            "Copias de seguridad",
            "Descargar copia",
            "Borrar copia",
            "Cerrar",
            "Cancelar",
            "contiene también otros datos",
        ),
        "en": (
            "Backups",
            "Download backup",
            "Delete backup",
            "Close",
            "Cancel",
            "also contains other data",
        ),
    }
    catalogue, download, delete, close, cancel, warning = labels[language]
    with prefixed_server(url, ingress) as manager_url, playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
            page.goto(manager_url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            page.get_by_role("button", name=catalogue, exact=True).click()
            dialog = page.locator("#modal")
            dialog.get_by_role("button", name=download + ": Shared", exact=False).click()
            playwright.expect(dialog).to_contain_text(warning)
            assert dialog.locator("input[type=password]").count() == 0
            assert page.evaluate("window.transferXss") is None
            with page.expect_download() as result:
                dialog.get_by_role("link", name=download, exact=True).click()
            artifact = result.value
            assert artifact.suggested_filename == "ha-backup-backup1.tar"
            assert artifact.failure() is None
            assert Path(artifact.path()).read_bytes() == ARCHIVE
            assert page.url == manager_url
            assert all(stream.closed for stream in manager.supervisor.streams)
            dialog.get_by_role("button", name=close, exact=True).click()
            page.get_by_role("button", name=catalogue, exact=True).click()
            dialog.get_by_role("button", name=delete + ": Shared", exact=False).click()
            playwright.expect(dialog).to_contain_text(warning)
            playwright.expect(dialog).to_contain_text("NAS")
            assert dialog.get_by_role("button", name=cancel, exact=True).evaluate(
                "el => el===document.activeElement"
            )
            dialog.get_by_role("button", name=delete, exact=True).click()
            consent = dialog.locator("#backup-delete-consent")
            assert consent.evaluate("el => el.validity.valueMissing")
            assert not any(method == "DELETE" for method, _ in manager.supervisor.calls)
            page.keyboard.press("Escape")
            playwright.expect(dialog).not_to_be_visible()
            assert "backup1" in manager.supervisor.backups
            page.get_by_role("button", name=catalogue, exact=True).click()
            dialog.get_by_role("button", name=delete + ": Shared", exact=False).click()
            consent.check()
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            dialog.get_by_role("button", name=delete, exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            page.wait_for_function(
                "async () => { const state=await (await fetch('api/state')).json(); return Object.values(state.jobs).some(job => job.kind==='backup_delete' && job.status==='succeeded'); }"
            )
            page.get_by_role("button", name=catalogue, exact=True).click()
            playwright.expect(dialog.locator(".backup-card")).to_have_count(0)
            assert not manager.supervisor.backups
            assert manager.supervisor.installed[0]["slug"] == "local_demo"
            assert (
                "private-upstream-token" not in jobs.path.read_text() + manager.log_path.read_text()
            )
            assert not any(stream.reads == 0 for stream in manager.supervisor.streams)
        finally:
            browser.close()
