import json
import shutil

import pytest
from test_adoption_ui import adoption_server as adoption_server


def test_component_catalog_search_status_and_review(adoption_server, monkeypatch, tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, _ = adoption_server
    repo = next(iter(manager.state["repos"].values()))
    checkout = manager.data / "repos" / repo["id"]
    component = checkout / "custom_components" / "pgm_forgejo_backup"
    component.mkdir(parents=True)
    (component / "__init__.py").touch()
    (component / "manifest.json").write_text(
        json.dumps({"name": "Forgejo Backup", "domain": component.name, "version": "0.1.0"})
    )
    config = tmp_path / "homeassistant"
    config.mkdir()
    monkeypatch.setenv("PGM_CORE_CONFIG", str(config))

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto(url)
            page.get_by_role("navigation").get_by_role("button", name="Componentes").click()
            playwright.expect(
                page.get_by_role("heading", name="Componentes", exact=True)
            ).to_be_focused()
            card = page.get_by_role("article").filter(has_text="Forgejo Backup")
            playwright.expect(card).to_contain_text("Catálogo: 0.1.0")
            search = page.get_by_label("Buscar componentes")
            search.fill("inexistente")
            playwright.expect(card).to_have_count(0)
            playwright.expect(search).to_be_focused()
            search.fill("pgm_forgejo_backup")
            filters = page.get_by_label("Estado", exact=True)
            filters.select_option("integrationOnDiskStatus")
            playwright.expect(card).to_have_count(0)
            filters.select_option("available")
            card.get_by_role("button", name="Instalar integración · Forgejo Backup").click()
            dialog = page.get_by_role("dialog")
            playwright.expect(dialog).to_contain_text(repo["commit"])
            playwright.expect(dialog.get_by_role("button", name="Cancelar")).to_be_focused()
            assert page.evaluate("document.documentElement.scrollWidth") == 390
        finally:
            browser.close()
