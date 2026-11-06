import shutil

import pytest
from test_adoption_ui import adoption_server as adoption_server
from test_backups import BackupSupervisor


@pytest.fixture
def backup_server(adoption_server):
    url, manager, jobs = adoption_server
    repo = next(iter(manager.state["repos"].values()))
    shutil.rmtree(manager.addons / "demo")
    manager.supervisor = BackupSupervisor()
    manager.supervisor.addons = manager.addons
    manager.deploy(repo["id"], "demo")
    return url, manager, jobs


@pytest.mark.parametrize("language", ["es", "en"])
def test_backup_create_encrypted_and_restore_with_explicit_consent(backup_server, language):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = backup_server
    labels = {
        "es": (
            "Copias de seguridad",
            "Crear copia",
            "Restaurar copia",
            "Nombre de la copia (opcional)",
            "Contraseña para cifrar (opcional)",
            "Repite la contraseña",
            "Contraseña de la copia",
            "Cancelar",
            "Las contraseñas no coinciden.",
        ),
        "en": (
            "Backups",
            "Create backup",
            "Restore backup",
            "Backup name (optional)",
            "Encryption password (optional)",
            "Repeat password",
            "Backup password",
            "Cancel",
            "Passwords do not match.",
        ),
    }
    catalogue, create, restore, name, password, repeat, restore_password, cancel, mismatch = labels[
        language
    ]
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            page.get_by_role("button", name=catalogue, exact=True).click()
            dialog = page.locator("#modal")
            dialog.get_by_role("button", name=create, exact=True).click()
            dialog.get_by_label(name, exact=True).fill(
                "Before <script>window.backupXss=true</script>"
            )
            dialog.get_by_label(password, exact=True).fill("browser-backup-secret")
            dialog.get_by_label(repeat, exact=True).fill("typo")
            dialog.get_by_role("button", name=create, exact=True).click()
            playwright.expect(page.locator("#modal-notice")).to_have_text(mismatch)
            assert not manager.supervisor.backups
            dialog.get_by_label(repeat, exact=True).fill("browser-backup-secret")
            dialog.get_by_role("button", name=create, exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            page.wait_for_function(
                "async () => { const s = await (await fetch('api/state')).json(); return Object.values(s.jobs).some(j => j.kind === 'backup_create' && j.status === 'succeeded'); }"
            )
            manager.supervisor.settings["options"]["username"] = "changed-after-backup"
            page.get_by_role("button", name=catalogue, exact=True).click()
            playwright.expect(dialog.locator(".backup-card strong")).to_have_text(
                "Before <script>window.backupXss=true</script>"
            )
            assert page.evaluate("window.backupXss") is None
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            dialog.get_by_role("button", name=restore + ": Before", exact=False).click()
            playwright.expect(dialog.get_by_role("heading")).to_have_text(restore + ": demo")
            assert dialog.get_by_role("button", name=cancel, exact=True).evaluate(
                "el => el === document.activeElement"
            )
            dialog.get_by_label(restore_password, exact=True).fill("browser-backup-secret")
            consent = dialog.locator("#backup-restore-consent")
            dialog.get_by_role("button", name=restore, exact=True).click()
            assert consent.evaluate("el => el.validity.valueMissing")
            assert not manager.supervisor.restore_started.is_set()
            # Esc dismisses without enqueuing a restoration.
            page.keyboard.press("Escape")
            playwright.expect(dialog).not_to_be_visible()
            assert not manager.supervisor.restore_started.is_set()
            page.get_by_role("button", name=catalogue, exact=True).click()
            dialog.get_by_role("button", name=restore + ": Before", exact=False).click()
            dialog.get_by_label(restore_password, exact=True).fill("browser-backup-secret")
            consent.check()
            dialog.get_by_role("button", name=restore, exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            page.wait_for_function(
                "async () => { const s = await (await fetch('api/state')).json(); return Object.values(s.jobs).some(j => j.kind === 'backup_restore' && j.status === 'succeeded'); }"
            )
            assert manager.supervisor.settings["options"]["username"] == "demo"
            assert page.locator("input[type=password]").count() == 0
            assert "browser-backup-secret" not in jobs.path.read_text()
            assert "browser-backup-secret" not in manager.state_file.read_text()
            assert "browser-backup-secret" not in manager.log_path.read_text()
            assert all(j["status"] == "succeeded" for j in jobs.snapshot().values())
        finally:
            browser.close()


def test_uninstalled_app_can_restore_but_cannot_create_backup(backup_server):
    from app.backups import Backups

    url, manager, _ = backup_server
    repo = next(iter(manager.state["repos"]))
    Backups(manager).create(repo, "demo", "Recovery")
    manager.supervisor.installed.clear()
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            page.get_by_role("button", name="Copias de seguridad", exact=True).click()
            dialog = page.locator("#modal")
            playwright.expect(
                dialog.get_by_role("button", name="Crear copia", exact=True)
            ).to_be_disabled()
            dialog.get_by_role("button", name="Restaurar copia: Recovery", exact=True).click()
            assert dialog.locator("input[type=password]").count() == 0
            dialog.locator("#backup-restore-consent").check()
            dialog.get_by_role("button", name="Restaurar copia", exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            page.wait_for_function(
                "async () => { const s = await (await fetch('api/state')).json(); return Object.values(s.jobs).some(j => j.kind === 'backup_restore' && j.status === 'succeeded'); }"
            )
            assert manager.supervisor.installed[0]["slug"] == "local_demo"
        finally:
            browser.close()
