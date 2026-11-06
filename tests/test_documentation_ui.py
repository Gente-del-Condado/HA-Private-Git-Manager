import shutil
from pathlib import Path

import pytest
from app.documentation import RepositoryDocs
from test_adoption_ui import adoption_server as adoption_server
from test_manager import addon


@pytest.mark.parametrize("force_fallback", [False, True])
def test_private_catalog_readme_and_app_docs_in_browser(adoption_server, force_fallback):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, _ = adoption_server
    with manager.lock:
        repo = next(iter(manager.state["repos"].values()))
        root = manager.data / "repos" / repo["id"]
        (root / "repository.yaml").write_text(
            "name: Catálogo privado\nmaintainer: Equipo de prueba\n"
        )
        (root / "README.md").write_text("""# Presentación del catálogo

**Mis aplicaciones privadas**.

| Nombre | Tipo |
|---|---|
| Demo | Local |

![Icono local](icon.png)
![Imagen remota](https://example.org/tracker.png)

[Ayuda](docs/USAGE.md)

<script>window.readmeExecuted = true</script>
<img src="x" onerror="window.readmeExecuted=true">
""")
        shutil.copyfile(
            Path(__file__).resolve().parents[1] / "private_git_manager/icon.png", root / "icon.png"
        )
        (root / "docs").mkdir()
        (root / "docs/USAGE.md").write_text("# Ayuda privada\n\n[Volver](../README.md)")
        (root / "demo/README.md").write_text("# README de Demo\n\nEsta es la primera aplicación.")
        (root / "demo/DOCS.md").write_text("# Configurar Demo")
        addon(root / "second", slug="second")
        repo["apps"] = manager.discover(root)
        repo["catalog"] = RepositoryDocs(root, repo["id"]).catalog(repo["apps"])
        manager.save()
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            if force_fallback:
                page.add_init_script("delete Element.prototype.setHTML;")
            external_requests = []

            def external(route):
                external_requests.append(route.request.url)
                route.abort()

            page.route("https://example.org/**", external)
            page.goto(url)
            playwright.expect(page.get_by_text("Repositorio maestro", exact=True)).to_be_visible()
            playwright.expect(page.get_by_text("Equipo de prueba", exact=True)).to_be_visible()
            page.get_by_role("button", name="Ver catálogo", exact=True).click()
            playwright.expect(page.locator("#document-content h1")).to_have_text(
                "Presentación del catálogo"
            )
            playwright.expect(page.locator("#document-content table")).to_be_visible()
            playwright.expect(
                page.locator('#document-content img[alt="Icono local"]')
            ).to_have_js_property("naturalWidth", 256)
            assert page.evaluate("window.readmeExecuted") is None
            assert not external_requests
            assert page.locator("#document-content script").count() == 0
            if force_fallback:
                assert not page.evaluate("'setHTML' in Element.prototype")
            page.get_by_role("link", name="Ayuda", exact=True).click()
            playwright.expect(page.locator("#document-content h1")).to_have_text("Ayuda privada")
            page.get_by_role("button", name="Cerrar", exact=True).click()
            page.locator('.app-row button[data-action="readme"][data-slug="demo"]').filter(
                has_text="Ver README"
            ).click()
            playwright.expect(page.locator("#document-content h1")).to_have_text("README de Demo")
            page.get_by_role("button", name="Cerrar", exact=True).click()
            page.locator(
                '.app-row button[data-action="readme"][data-slug="demo"][data-document="docs"]'
            ).click()
            playwright.expect(page.locator("#document-content h1")).to_have_text("Configurar Demo")
            page.get_by_role("button", name="Cerrar", exact=True).click()
            page.get_by_role("searchbox", name="Buscar repositorios…").fill("Equipo de prueba")
            # Search currently covers catalog/app identity; maintainers are searchable too.
            playwright.expect(
                page.get_by_role("button", name="Ver catálogo", exact=True)
            ).to_be_visible()
        finally:
            browser.close()
