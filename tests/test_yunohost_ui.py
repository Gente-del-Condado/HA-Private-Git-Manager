import shutil
from urllib.parse import parse_qs, urlsplit

import pytest
from test_adoption_ui import adoption_server as adoption_server


def test_native_actions_from_portal_subpath(adoption_server):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, _ = adoption_server
    repo = next(iter(manager.state["repos"].values()))
    package = {"id": "testapp", "name": "Private YunoHost app", "version": "2.0~ynh1"}
    stage = {"id": "a" * 32, "path": "/home/yunohost.app/privategit/staging", "package": package}
    native_mutations, preparations = [], []
    authenticated = False
    requirement_error = conditional = False
    native_status = 200

    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page()

            def portal(route):
                path = route.request.url.removeprefix(url + "private-git/")
                if path.endswith("/yunohost-stage"):
                    preparations.append(route.request.post_data_json)
                    route.fulfill(json=stage)
                elif path.startswith("api/yunohost-stages/"):
                    route.fulfill(json={"ok": True})
                else:
                    response = route.fetch(url=url + path)
                    if path == "api/state":
                        state = response.json()
                        state["platform"] = "yunohost"
                        state["repos"][repo["id"]]["yunohost_package"] = package
                        route.fulfill(response=response, json=state)
                    else:
                        route.fulfill(response=response)

            def native(route):
                request = route.request
                parsed = urlsplit(request.url)
                assert request.headers["x-requested-with"] == "XMLHttpRequest"
                if not authenticated:
                    route.fulfill(status=401, json={"error": "Unauthorized"})
                elif parsed.path.endswith("/manifest"):
                    assert parse_qs(parsed.query) == {"app": [stage["path"]]}
                    route.fulfill(
                        json={
                            **package,
                            "integration": {"multi_instance": True},
                            "requirements": {
                                "arch": {
                                    "passed": not requirement_error,
                                    "error": "Arquitectura incompatible",
                                }
                            },
                            "install": [
                                {
                                    "id": "domain",
                                    "type": "domain",
                                    "ask": "Domain",
                                    "help": "Elige el dominio",
                                    "visible": "other == 'yes'" if conditional else True,
                                    "choices": {"site.example": "site.example"},
                                },
                                {"id": "hidden_file", "type": "file", "visible": False},
                            ],
                        }
                    )
                elif request.method == "GET":
                    route.fulfill(
                        json={
                            "apps": [
                                {"id": "testapp", "version": "1.0~ynh1"},
                                {"id": "testapp__2", "version": "1.1~ynh1"},
                                {"id": "testapp-extra", "version": "2.0~ynh1"},
                            ]
                        }
                    )
                else:
                    native_mutations.append(
                        (request.method, parsed.path, parse_qs(request.post_data or ""))
                    )
                    route.fulfill(status=native_status, json={})

            page.route(url + "private-git/**", portal)
            page.route(url + "yunohost/api/**", native)
            page.goto(url + "private-git/")
            row = page.locator(".app-row").filter(has_text=package["name"])
            dialog = page.get_by_role("dialog")
            row.get_by_role("button", name="Instalar", exact=True).click()
            playwright.expect(dialog).to_contain_text("Inicia sesión como administrador")
            assert not preparations
            dialog.locator("#modal-actions").get_by_role("button", name="Cerrar").click()
            authenticated = True
            row.get_by_role("button", name="Instalar", exact=True).click()
            playwright.expect(dialog.get_by_role("button", name="Cancelar")).to_be_focused()
            domain = dialog.get_by_label("Domain")
            playwright.expect(domain).to_have_accessible_description("Elige el dominio")
            assert dialog.locator('[name="arg:hidden_file"]').count() == 0
            domain.select_option("site.example")
            dialog.get_by_role("button", name="Instalar", exact=True).click()
            assert not native_mutations
            dialog.get_by_role("checkbox").check()
            dialog.get_by_role("button", name="Instalar", exact=True).click()
            playwright.expect(dialog).not_to_be_visible()

            for label in ("Actualizar", "Desinstalar"):
                row.get_by_role("button", name=label, exact=True).click()
                select = dialog.get_by_label("Instancia instalada")
                playwright.expect(select.locator("option")).to_have_count(3)
                select.select_option("testapp__2")
                dialog.get_by_role("checkbox").check()
                dialog.get_by_role("button", name=label, exact=True).click()
                playwright.expect(dialog).not_to_be_visible()
            assert preparations == [{"expected_commit": repo["commit"]}] * 2
            assert native_mutations == [
                (
                    "POST",
                    "/yunohost/api/apps",
                    {
                        "app": [stage["path"]],
                        "label": [package["name"]],
                        "args": ["domain=site.example"],
                    },
                ),
                ("PUT", "/yunohost/api/apps/testapp__2/upgrade", {"file": [stage["path"]]}),
                ("DELETE", "/yunohost/api/apps/testapp__2", {}),
            ]
            requirement_error = True
            row.get_by_role("button", name="Instalar", exact=True).click()
            playwright.expect(dialog).to_contain_text("Arquitectura incompatible")
            assert len(native_mutations) == 3
            dialog.locator("#modal-actions").get_by_role("button", name="Cerrar").click()

            requirement_error = False
            conditional = True
            row.get_by_role("button", name="Instalar", exact=True).click()
            playwright.expect(dialog).to_contain_text("preguntas condicionales")
            assert len(native_mutations) == 3
            dialog.locator("#modal-actions").get_by_role("button", name="Cerrar").click()

            native_status = 504
            row.get_by_role("button", name="Actualizar", exact=True).click()
            dialog.get_by_label("Instancia instalada").select_option("testapp__2")
            dialog.get_by_role("checkbox").check()
            submit = dialog.get_by_role("button", name="Actualizar", exact=True)
            submit.click()
            playwright.expect(dialog).to_contain_text("No se pudo confirmar el resultado")
            playwright.expect(submit).to_be_disabled()
            assert len(native_mutations) == 4
        finally:
            browser.close()
