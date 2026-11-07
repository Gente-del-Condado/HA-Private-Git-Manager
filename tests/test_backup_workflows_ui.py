import shutil

import pytest
from app.backups import Backups
from test_adoption_ui import adoption_server as adoption_server
from test_backup_workflows import archive_for
from test_backups_ui import backup_server as backup_server
from test_manager import addon


def test_new_backup_controls_use_the_manager_workflows(backup_server, monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, _ = backup_server
    repo = next(iter(manager.state["repos"]))
    service = Backups(manager)
    service.create(repo, "demo", "Imported test metadata")
    archive = archive_for("local_demo")

    def upload(stream):
        assert stream.read() == archive
        manager.supervisor.backups["imported1"] = dict(
            manager.supervisor.backups["backup1"], slug="imported1"
        )
        return {"slug": "imported1"}

    monkeypatch.setattr(manager.supervisor, "backup_upload", upload, raising=False)
    checkout = manager.data / "repos" / repo
    addon(checkout / "demo", "2.0.0")
    (checkout / "demo" / "CHANGELOG.md").write_text("# Test release notes")
    manager.repo(repo).update(apps=manager.discover(checkout), commit="b" * 40)
    manager.save()

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(url)
            dialog = page.locator("#modal")
            page.get_by_role("button", name="Copias de seguridad", exact=True).click()
            dialog.get_by_role("button", name="Programar copias", exact=True).click()
            dialog.get_by_label("Intervalo en horas").fill("24")
            dialog.get_by_label("Número de copias a conservar").fill("2")
            dialog.get_by_role("button", name="Guardar", exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            assert manager.repo(repo)["backup_schedules"]["demo"]["keep"] == 2
            page.get_by_role("button", name="Copias de seguridad", exact=True).click()
            dialog.get_by_role("button", name="Importar copia", exact=True).click()
            dialog.get_by_label("Archivo de copia .tar").set_input_files(
                {"name": "backup.tar", "mimeType": "application/x-tar", "buffer": archive}
            )
            dialog.get_by_role("button", name="Importar copia", exact=True).click()
            playwright.expect(dialog.get_by_role("heading")).to_contain_text("Restaurar copia")
            playwright.expect(dialog).to_contain_text("1.0.0")
            playwright.expect(dialog.locator("#backup-restore-consent")).not_to_be_checked()
            page.keyboard.press("Escape")
            page.locator('[data-action="deploy"][data-slug="demo"]').click()
            dialog.get_by_text("Registro de cambios del repositorio", exact=False).click()
            playwright.expect(dialog).to_contain_text("Test release notes")
            playwright.expect(dialog).to_contain_text("2.0.0")
            dialog.get_by_role("button", name="Crear copia y actualizar", exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            page.wait_for_function("""
                async () => {
                    const result = await (await fetch('api/state')).json();
                    return Object.values(result.jobs).some(
                        (job) => job.kind === 'deploy' && job.status === 'succeeded'
                    );
                }
            """)
            assert (manager.addons / "demo" / "payload").read_text() == "2.0.0"
            assert len(manager.supervisor.backups) == 3
        finally:
            browser.close()
