import shutil
import time

import pytest
from test_adoption_ui import adoption_server as adoption_server
from test_application import ControlsSupervisor


@pytest.mark.parametrize("language", ["es", "en"])
def test_configuration_and_private_logs_in_browser(adoption_server, language, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = adoption_server
    manager.supervisor = ControlsSupervisor()
    manager.supervisor.addons = manager.addons
    repo = next(iter(manager.state["repos"].values()))
    inspection = manager.inspect_deployment(repo["id"], "demo")
    manager.deploy(
        repo["id"], "demo", adopt_existing=True, expected_local_digest=inspection["local_digest"]
    )
    manager.supervisor.installed[0]["state"] = "started"
    manager.save()
    configure, validate, save, cancel, logs, refresh, download = (
        (
            "Configurar",
            "Validar configuración",
            "Guardar configuración",
            "Cancelar",
            "Logs de la aplicación",
            "Actualizar estado",
            "Descargar logs",
        )
        if language == "es"
        else (
            "Configure",
            "Validate configuration",
            "Save configuration",
            "Cancel",
            "App logs",
            "Refresh status",
            "Download logs",
        )
    )
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(accept_downloads=True, viewport={"width": 1100, "height": 900})
            page.goto(url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            row = page.locator(
                '.app-row:has(button[data-slug="demo"][data-action="app-configuration"])'
            )
            row.get_by_role("button", name=configure, exact=True).click()
            dialog = page.locator("#modal")
            editor = dialog.locator("#app-configuration-yaml")
            assert "initial-app-secret" in editor.input_value()
            editor.fill("options: [broken")
            dialog.get_by_role("button", name=validate, exact=True).click()
            playwright.expect(editor).to_have_attribute("aria-invalid", "true")
            assert editor.input_value() == "options: [broken"
            editor.fill(
                "options:\n  username: demo\n  password: changed-app-secret\n  nested:\n    enabled: true\nboot: auto\nwatchdog: true\n"
            )
            dialog.get_by_role("button", name=validate, exact=True).click()
            playwright.expect(page.locator("#modal-notice")).to_contain_text(
                "preliminar" if language == "es" else "Preliminary"
            )
            dialog.get_by_role("button", name=cancel, exact=True).click()
            playwright.expect(dialog).to_be_visible()
            playwright.expect(
                dialog.locator('[data-action="discard-configuration"]')
            ).to_be_visible()
            assert "changed-app-secret" in editor.input_value()
            dialog.locator("#configuration-restart").check()
            dialog.get_by_role("button", name=save, exact=True).click()
            playwright.expect(dialog).not_to_be_visible()
            for _ in range(300):
                if manager.supervisor.settings["options"].get(
                    "password"
                ) == "changed-app-secret" and all(
                    j["status"] == "succeeded" for j in jobs.snapshot().values()
                ):
                    break
                time.sleep(0.01)
            assert manager.supervisor.settings["boot"] == "auto"
            assert manager.supervisor.settings["options"]["nested"]["enabled"] is True
            assert ("POST", "/addons/local_demo/restart") in manager.supervisor.calls
            assert "changed-app-secret" not in jobs.path.read_text()
            assert "changed-app-secret" not in manager.state_file.read_text()
            assert page.locator("#modal-body").inner_text() == ""
            row.get_by_role("button", name=configure, exact=True).click()
            editor.fill("options: {username: unsaved-edit}")
            manager.supervisor.settings["boot"] = "manual"  # Changed in another window.
            dialog.get_by_role("button", name=save, exact=True).click()
            playwright.expect(page.locator("#modal-notice")).to_contain_text(
                "configuración ha cambiado" if language == "es" else "Configuration changed",
                timeout=10000,
            )
            playwright.expect(dialog).to_be_visible()
            playwright.expect(editor).to_be_editable()
            assert editor.input_value() == "options: {username: unsaved-edit}"
            page.set_viewport_size({"width": 390, "height": 844})
            assert dialog.evaluate("el => el.scrollWidth <= el.clientWidth")
            dialog.get_by_role("button", name=cancel, exact=True).click()
            dialog.locator('[data-action="discard-configuration"]').click()
            playwright.expect(dialog).not_to_be_visible()
            page.set_viewport_size({"width": 1100, "height": 900})
            manager.supervisor.log_text = (
                "<script>window.logExecuted=true</script>\npassword: changed-app-secret\nReady\n"
            )
            row.get_by_role("button", name=logs, exact=True).click()
            output = dialog.locator("#application-log-output")
            playwright.expect(output).to_contain_text("Ready")
            assert "changed-app-secret" not in output.inner_text()
            assert page.evaluate("window.logExecuted") is None
            assert dialog.locator("script").count() == 0
            search = dialog.locator("#application-log-search")
            search.fill("Ready")
            playwright.expect(output).to_have_text("Ready")
            search.press("Enter")
            playwright.expect(dialog).to_be_visible()
            search.fill("")
            manager.supervisor.log_text = "Automatic new line\npassword: changed-app-secret\n"
            playwright.expect(output).to_contain_text("Automatic new line", timeout=8000)
            dialog.locator("#application-log-auto").uncheck()
            manager.supervisor.log_text = "Manual new line\npassword: changed-app-secret\n"
            dialog.get_by_role("button", name=refresh, exact=True).click()
            playwright.expect(output).to_contain_text("Manual new line")
            with page.expect_download() as pending:
                dialog.get_by_role("link", name=download, exact=True).click()
            artifact = pending.value
            path = tmp_path / "application.log"
            artifact.save_as(path)
            assert "Manual new line" in path.read_text()
            assert "changed-app-secret" not in path.read_text()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert dialog.evaluate("el => el.getBoundingClientRect().width <= innerWidth")
            dialog.get_by_role(
                "button", name="Cerrar" if language == "es" else "Close", exact=True
            ).click()
            playwright.expect(dialog).not_to_be_visible()
        finally:
            browser.close()
