import shutil

import pytest
from test_adoption_ui import adoption_server as adoption_server
from test_manager import addon


@pytest.mark.parametrize("language", ["es", "en"])
def test_delete_confirmation_hide_and_restore_in_master(adoption_server, language):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = adoption_server
    repo = next(iter(manager.state["repos"].values()))
    root = manager.data / "repos" / repo["id"]
    addon(root / "second", slug="second")
    addon(manager.addons / "second", slug="second")
    repo["apps"] = manager.discover(root)
    manager.save()
    delete, cancel, restore = (
        ("Borrar aplicación", "Cancelar", "Volver a mostrar")
        if language == "es"
        else ("Delete app", "Cancel", "Show again")
    )
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            row = page.locator('.app-row:has(button[data-slug="demo"][data-action="remove-app"])')
            row.get_by_role("button", name=delete, exact=True).click()
            dialog = page.locator("#modal")
            playwright.expect(dialog).to_be_visible()
            assert dialog.get_by_role("button", name=cancel, exact=True).evaluate(
                "el => el === document.activeElement"
            )
            consent = dialog.locator("#removal-consent")
            playwright.expect(consent).not_to_be_checked()
            dialog.get_by_role("button", name=delete, exact=True).click()
            assert consent.evaluate("el => el.validity.valueMissing")
            assert not jobs.snapshot()
            consent.check()
            dialog.get_by_role("button", name=delete, exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            playwright.expect(row).to_have_count(0, timeout=10000)
            assert not (manager.addons / "demo").exists()
            assert (manager.addons / "second/payload").exists()
            assert (root / "demo/payload").exists()
            page.locator("details summary").click()
            page.get_by_role("button", name=restore, exact=True).click()
            playwright.expect(row).to_have_count(1)
            assert not repo["hidden_apps"]
            assert not (manager.addons / "demo").exists()  # Show again never installs.
        finally:
            browser.close()
