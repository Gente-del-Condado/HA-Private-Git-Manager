import json
import shutil
import time

import pytest
import yaml
from test_adoption_ui import adoption_server as adoption_server
from test_application import ControlsSupervisor


class NativeSchemaSupervisor(ControlsSupervisor):
    """Fixtures follow Supervisor UiOptions output, including nested/multiple nodes."""

    def __init__(self):
        super().__init__()
        self.settings.update(audio_input=None, audio_output=None, ingress_panel=None)
        self.settings["options"] = {
            "username": "demo",
            "password": "native-app-secret",
            "count": 2,
            "ratio": 0.5,
            "enabled": False,
            "color": "red",
            "connection": {"host": "server", "port": 8123},
            "devices": ["/dev/a"],
            "accounts": [{"name": "one", "admin": False, "note": "first-note"}],
            "secret_number": "!secret app_number",
            "legacy": "preserve-me",
            "future": {"private": "preserved"},
            "__proto__": {"polluted": True},
        }
        self.schema = [
            {
                "name": "username",
                "type": "string",
                "required": True,
                "lengthMin": 3,
                "lengthMax": 20,
            },
            {"name": "password", "type": "string", "format": "password", "required": True},
            {"name": "count", "type": "integer", "required": True, "lengthMin": 1, "lengthMax": 5},
            {"name": "ratio", "type": "float", "required": True, "lengthMin": 0, "lengthMax": 1},
            {"name": "enabled", "type": "boolean", "required": True},
            {"name": "color", "type": "select", "required": True, "options": ["red", "green"]},
            {"name": "email", "type": "string", "format": "email", "optional": True},
            {"name": "feature", "type": "boolean", "optional": True},
            {"name": "absent", "type": "boolean", "optional": True},
            {
                "name": "connection",
                "type": "schema",
                "optional": True,
                "schema": [
                    {"name": "host", "type": "string", "required": True},
                    {"name": "port", "type": "integer", "required": True},
                ],
            },
            {
                "name": "devices",
                "type": "select",
                "multiple": True,
                "required": True,
                "options": ["/dev/a", "/dev/b"],
            },
            {
                "name": "accounts",
                "type": "schema",
                "optional": True,
                "multiple": True,
                "schema": [
                    {"name": "name", "type": "string", "required": True},
                    {"name": "admin", "type": "boolean", "required": True},
                    {"name": "note", "type": "string", "optional": True},
                ],
            },
            {"name": "secret_number", "type": "integer", "required": True},
            {"name": "future", "type": "future-type", "optional": True},
        ]
        self.translations = {
            "en": {
                "configuration": {
                    "count": {"name": "Attempts", "description": "Between one and five"},
                    "color": {"name": "Color"},
                    "connection": {"name": "Connection", "fields": {"host": {"name": "Host"}}},
                }
            },
            "es": {
                "configuration": {
                    "count": {"name": "Intentos", "description": "Entre uno y cinco"},
                    "connection": {"name": "Conexión", "fields": {"host": {"name": "Servidor"}}},
                },
                "network": {"1234/tcp": "Puerto del servicio"},
            },
        }

    def call(self, method, path, payload=None):
        result = super().call(method, path, payload)
        if path.endswith("/info"):
            result.update(schema=self.schema, translations=self.translations)
        return result


@pytest.mark.parametrize("language", ["es", "en"])
def test_native_schema_form_roundtrip_and_save_without_yaml(adoption_server, language):
    playwright = pytest.importorskip("playwright.sync_api")
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    if not executable:
        pytest.skip("A local Chrome/Chromium binary is needed")
    url, manager, jobs = adoption_server
    manager.supervisor = NativeSchemaSupervisor()
    manager.supervisor.addons = manager.addons
    repo = next(iter(manager.state["repos"].values()))
    info = manager.inspect_deployment(repo["id"], "demo")
    manager.deploy(
        repo["id"], "demo", adopt_existing=True, expected_local_digest=info["local_digest"]
    )
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(executable_path=executable, headless=True)
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 900})
            page.goto(url)
            if language == "en":
                page.get_by_role("combobox", name="Idioma / Language").select_option("en")
            page.get_by_role(
                "button", name="Configurar" if language == "es" else "Configure", exact=True
            ).click()
            dialog = page.locator("#modal")
            form_label, yaml_label, save = (
                ("Formulario", "YAML avanzado", "Guardar configuración")
                if language == "es"
                else ("Form", "Advanced YAML", "Save configuration")
            )
            playwright.expect(
                dialog.get_by_role("button", name=form_label, exact=True)
            ).to_have_attribute("aria-pressed", "true")
            playwright.expect(dialog.locator("#app-configuration-yaml")).not_to_be_visible()

            def field(path):
                return dialog.locator(
                    f"[data-option-path='{json.dumps(path, separators=(',', ':'))}']"
                )

            def optional(path):
                return dialog.locator(
                    f"[data-optional-path='{json.dumps(path, separators=(',', ':'))}']"
                )

            playwright.expect(
                dialog.get_by_label("Intentos *" if language == "es" else "Attempts *", exact=True)
            ).to_be_visible()
            playwright.expect(
                dialog.get_by_text(
                    "Entre uno y cinco" if language == "es" else "Between one and five", exact=True
                )
            ).to_be_visible()
            playwright.expect(
                dialog.get_by_label("Color *", exact=True)
            ).to_be_visible()  # English fallback.
            assert field(["password"]).get_attribute("type") == "password"
            dialog.get_by_role(
                "button",
                name="Mostrar contraseña" if language == "es" else "Show password",
                exact=True,
            ).click()
            assert field(["password"]).get_attribute("type") == "text"
            field(["password"]).fill("updated-native-secret")
            field(["count"]).fill("10")
            dialog.get_by_role("button", name=save, exact=True).click()
            assert field(["count"]).evaluate("el => el.validity.rangeOverflow")
            assert not jobs.snapshot()
            field(["count"]).fill("3")
            field(["ratio"]).fill("0.75")
            field(["enabled"]).check()
            field(["color"]).select_option("green")
            field(["connection", "host"]).fill("updated-host")
            optional(["feature"]).check()
            playwright.expect(field(["feature"])).not_to_be_checked()
            # Disable/enable must not erase existing nested values.
            optional(["connection"]).uncheck()
            optional(["connection"]).check()
            assert field(["connection", "host"]).input_value() == "updated-host"
            dialog.locator("[data-list-path='[\"devices\"]']").click()
            field(["devices", 1]).select_option("/dev/b")
            first_device = field(["devices", 0]).locator("xpath=ancestor::fieldset[1]")
            first_device.get_by_role(
                "button", name="Quitar elemento" if language == "es" else "Remove item", exact=True
            ).click()
            assert field(["devices", 0]).input_value() == "/dev/b"
            dialog.locator("[data-list-path='[\"accounts\"]']").click()
            field(["accounts", 1, "name"]).fill("two")
            field(["accounts", 1, "admin"]).check()
            optional(["accounts", 1, "note"]).check()
            field(["accounts", 1, "note"]).fill("second-note")
            optional(["accounts", 0, "note"]).uncheck()
            optional(["accounts", 1, "note"]).uncheck()
            first_account = field(["accounts", 0, "name"]).locator(
                'xpath=ancestor::fieldset[contains(@class,"schema-list-item")][1]'
            )
            first_account.get_by_role(
                "button", name="Quitar elemento" if language == "es" else "Remove item", exact=True
            ).click()
            optional(["accounts", 0, "note"]).check()
            assert field(["accounts", 0, "note"]).input_value() == "second-note"
            assert field(["secret_number"]).input_value() == "!secret app_number"
            assert page.evaluate("({}).polluted") is None
            page.set_viewport_size({"width": 390, "height": 844})
            assert dialog.evaluate("el => el.scrollWidth <= el.clientWidth")
            page.set_viewport_size({"width": 1100, "height": 900})
            # Save directly from the form first, without opening YAML.
            dialog.get_by_role("button", name=save, exact=True).click()
            playwright.expect(dialog).not_to_be_visible(timeout=10000)
            assert manager.supervisor.settings["options"]["count"] == 3
            assert manager.supervisor.settings["options"]["feature"] is False
            assert manager.supervisor.settings["options"]["devices"] == ["/dev/b"]
            page.get_by_role(
                "button", name="Configurar" if language == "es" else "Configure", exact=True
            ).click()
            playwright.expect(
                dialog.get_by_role("button", name=form_label, exact=True)
            ).to_have_attribute("aria-pressed", "true")
            dialog.get_by_role("button", name=yaml_label, exact=True).click()
            editor = dialog.locator("#app-configuration-yaml")
            playwright.expect(editor).to_be_visible()
            playwright.expect(editor).to_be_enabled()
            snapshot = yaml.safe_load(editor.input_value())
            assert snapshot["options"]["feature"] is False
            assert "absent" not in snapshot["options"]
            assert snapshot["options"]["devices"] == ["/dev/b"]
            assert snapshot["options"]["future"] == {"private": "preserved"}
            snapshot["options"]["count"] = 4
            editor.fill(yaml.safe_dump(snapshot))
            dialog.get_by_role("button", name=form_label, exact=True).click()
            playwright.expect(field(["count"])).to_be_visible()
            playwright.expect(field(["count"])).to_have_value("4")
            assert field(["accounts", 0, "name"]).input_value() == "two"
            dialog.get_by_role("button", name=save, exact=True).click()
            playwright.expect(dialog).not_to_be_visible(timeout=10000)
            for _ in range(200):
                if manager.supervisor.settings["options"]["count"] == 4:
                    break
                time.sleep(0.01)
            options = manager.supervisor.settings["options"]
            assert options["count"] == 4 and isinstance(options["count"], int)
            assert options["ratio"] == 0.75
            assert options["enabled"] is True and options["feature"] is False
            assert options["accounts"][0] == {"name": "two", "admin": True, "note": "second-note"}
            assert options["connection"]["host"] == "updated-host"
            assert options["legacy"] == "preserve-me"
            assert options["future"] == {"private": "preserved"}
            assert options["__proto__"] == {"polluted": True}
            assert "updated-native-secret" not in manager.state_file.read_text()
            assert "updated-native-secret" not in jobs.path.read_text()
        finally:
            browser.close()
