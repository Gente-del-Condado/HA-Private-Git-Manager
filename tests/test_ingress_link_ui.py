import shutil

import pytest
from test_adoption_ui import adoption_server as adoption_server
from test_ingress_link import install_ingress


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize(
    "version,prefix", [("2026.11.0", "/app/"), ("2026.1.3", "/hassio/ingress/")]
)
def test_open_ingress_leaves_manager_iframe_and_uses_native_ha_route(
    adoption_server, language, version, prefix
):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, _ = adoption_server
    # Reuse the existing fixture repository and install it with an Ingress declaration.
    existing = next(iter(manager.state["repos"].values()))
    manager.repo_delete(existing["id"])
    shutil.rmtree(manager.addons / "demo")
    install_ingress(manager, version)
    proxy_path = "/api/hassio_ingress/manager-session/"
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.route(
                url + "ha-shell",
                lambda route: route.fulfill(
                    content_type="text/html",
                    body=f'<iframe title="Manager" src="{proxy_path}"></iframe>',
                ),
            )

            def proxy(route):
                response = route.fetch(url=route.request.url.replace(proxy_path, "/", 1))
                route.fulfill(response=response)

            page.route(url.rstrip("/") + proxy_path + "**", proxy)
            page.route(
                url.rstrip("/") + prefix + "local_demo",
                lambda route: route.fulfill(
                    content_type="text/html", body="Home Assistant Ingress panel"
                ),
            )
            page.goto(url + "ha-shell")
            frame = page.frame_locator('iframe[title="Manager"]')
            if language == "en":
                frame.get_by_role("combobox", name="Idioma / Language").select_option("en")
            link = frame.get_by_role(
                "button",
                name="Abrir interfaz web: Demo" if language == "es" else "Open web interface: Demo",
                exact=True,
            )
            playwright.expect(link).to_be_enabled()
            link.click()
            page.wait_for_url(url.rstrip("/") + prefix + "local_demo")
            assert page.locator("iframe").count() == 0
            assert "private-app-session" not in page.url
            assert page.locator("body").inner_text() == "Home Assistant Ingress panel"
        finally:
            browser.close()


def test_stopped_app_disables_open_and_stale_capability_does_not_navigate(adoption_server):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, _ = adoption_server
    existing = next(iter(manager.state["repos"].values()))
    manager.repo_delete(existing["id"])
    shutil.rmtree(manager.addons / "demo")
    install_ingress(manager)
    manager.supervisor.installed[0]["state"] = "stopped"
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()
            page.goto(url)
            button = page.get_by_role("button", name="Abrir interfaz web: Demo", exact=True)
            playwright.expect(button).to_be_disabled()
            manager.supervisor.installed[0]["state"] = "started"
            page.reload()
            playwright.expect(button).to_be_enabled()
            manager.supervisor.ingress = False
            button.click()
            playwright.expect(page.locator("#notice-message")).to_contain_text(
                "no ofrece interfaz web"
            )
            assert page.url == url
            assert not any("/ingress/session" in path for _, path in manager.supervisor.calls)
        finally:
            browser.close()
