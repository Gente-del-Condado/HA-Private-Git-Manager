"""Optional browser regressions; use an isolated headless Chrome profile."""

import shutil
import socket
import threading
import time

import pytest
import uvicorn
from app import main
from app.core import Manager
from app.jobs import Jobs, Scheduler
from test_manager import FakeSupervisor, addon, prepared


@pytest.fixture
def adoption_server(tmp_path, monkeypatch):
    manager = Manager(tmp_path / "data", tmp_path / "addons", FakeSupervisor())
    manager.supervisor.addons = manager.addons
    manager.verify_checkout = lambda repo, root: None  # Synthetic Supervisor fixture.
    prepared(manager)
    addon(manager.addons / "demo", "0.5.0")
    manager.save()
    jobs = Jobs(manager)
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "jobs", jobs)
    monkeypatch.setattr(main, "scheduler", Scheduler(manager, jobs))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", access_log=False))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        for _ in range(200):
            if server.started:
                break
            time.sleep(0.01)
        assert server.started
        try:
            yield f"http://127.0.0.1:{port}/", manager, jobs
        finally:
            server.should_exit = True
            worker.join(timeout=5)
            jobs.close()


@pytest.mark.parametrize("language", ["es", "en"])
def test_adoption_dialog_requires_consent_and_applies_code(adoption_server, language):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed for optional browser tests")
    url, manager, jobs = adoption_server
    labels = {
        "es": ("Instalar", "Adoptar y aplicar", "Cancelar", "Actualizar / reconstruir"),
        "en": ("Install", "Adopt and apply", "Cancel", "Update / rebuild"),
    }
    install, adopt_label, cancel, update = labels[language]
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            page.get_by_role("button", name=install, exact=True).click()
            dialog = page.locator("#modal")
            playwright.expect(dialog).to_be_visible()
            playwright.expect(dialog.get_by_role("heading", name=adopt_label)).to_be_visible()
            assert dialog.get_by_role("button", name=cancel, exact=True).evaluate(
                "el => el === document.activeElement"
            )
            consent = dialog.locator("#adoption-consent")
            playwright.expect(consent).not_to_be_checked()
            dialog.get_by_role("button", name=adopt_label, exact=True).click()
            assert consent.evaluate("el => el.validity.valueMissing")
            assert not jobs.snapshot()
            assert (manager.addons / "demo" / "payload").read_text() == "0.5.0"
            consent.check()
            dialog.get_by_role("button", name=adopt_label, exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            playwright.expect(page.get_by_role("button", name=update, exact=True)).to_be_visible(
                timeout=10000
            )
            assert (manager.addons / "demo" / "payload").read_text() == "1.0.0"
            assert manager.state["deployments"]["demo"]["status"] == "installed"
        finally:
            browser.close()
