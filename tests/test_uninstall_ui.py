import shutil

import pytest
from test_adoption_ui import adoption_server as adoption_server
from test_manager import addon


@pytest.mark.parametrize("language", ["es", "en"])
def test_uninstall_reinstall_and_combined_delete_from_manager(adoption_server, language):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = adoption_server
    repo = next(iter(manager.state["repos"].values()))
    root = manager.data / "repos" / repo["id"]
    addon(root / "second", slug="second")
    repo["apps"] = manager.discover(root)
    inspection = manager.inspect_deployment(repo["id"], "demo")
    manager.deploy(
        repo["id"], "demo", adopt_existing=True, expected_local_digest=inspection["local_digest"]
    )
    manager.deploy(repo["id"], "second")
    install, uninstall, delete, combined, cancel, confirm = (
        (
            "Instalar",
            "Desinstalar",
            "Borrar aplicación",
            "Desinstalar y borrar",
            "Cancelar",
            "Confirmar",
        )
        if language == "es"
        else ("Install", "Uninstall", "Delete app", "Uninstall and delete", "Cancel", "Confirm")
    )
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            row = page.locator('.app-row:has(button[data-slug="demo"][data-action="remove-app"])')
            row.get_by_role("button", name=uninstall, exact=True).click()
            dialog = page.locator("#modal")
            playwright.expect(dialog).to_be_visible()
            assert dialog.get_by_role("button", name=cancel, exact=True).evaluate(
                "el => el === document.activeElement"
            )
            consent = dialog.locator("#uninstall-consent")
            playwright.expect(consent).not_to_be_checked()
            playwright.expect(dialog.locator("#remove-config")).not_to_be_checked()
            dialog.get_by_role("button", name=uninstall, exact=True).click()
            assert consent.evaluate("el => el.validity.valueMissing")
            assert not jobs.snapshot()
            consent.check()
            dialog.get_by_role("button", name=uninstall, exact=True).click()
            playwright.expect(row.get_by_role("button", name=install, exact=True)).to_be_visible(
                timeout=10000
            )
            assert (manager.addons / "demo/payload").exists()
            assert not manager.installed_info("demo")
            assert (
                "POST",
                "/addons/local_demo/uninstall",
                {"remove_config": False},
            ) in manager.supervisor.payloads
            row.get_by_role("button", name=install, exact=True).click()
            dialog.get_by_role("button", name=confirm, exact=True).click()
            playwright.expect(row.get_by_role("button", name=uninstall, exact=True)).to_be_visible(
                timeout=10000
            )
            assert manager.installed_info("demo")
            row.get_by_role("button", name=delete, exact=True).click()
            dialog.locator("#uninstall-consent").check()
            dialog.locator("#removal-consent").check()
            dialog.locator("#remove-config").check()
            dialog.get_by_role("button", name=combined, exact=True).click()
            playwright.expect(row).to_have_count(0, timeout=10000)
            assert not (manager.addons / "demo").exists()
            assert manager.installed_info("second")
            assert (manager.addons / "second/payload").exists()
            assert (root / "demo/payload").exists()
            assert (
                "POST",
                "/addons/local_demo/uninstall",
                {"remove_config": True},
            ) in manager.supervisor.payloads
        finally:
            browser.close()
