import copy
import json

import httpx
import pytest
import yaml
from app.application import Applications, parse_configuration
from app.core import Problem, Supervisor, SupervisorUncertain
from test_manager import FakeSupervisor, prepared
from test_manager import manager as manager


class ControlsSupervisor(FakeSupervisor):
    def __init__(self):
        super().__init__()
        self.settings = {
            "options": {"username": "demo", "password": "initial-app-secret"},
            "boot": "manual",
            "watchdog": False,
            "network": {"1234/tcp": 1234},
        }
        self.log_text = "\x1b[31mStarted\x1b[0m\n<script>window.logExecuted=true</script>\npassword: initial-app-secret\nReady\n"
        self.truncated = False

    def call(self, method, path, payload=None):
        if path.endswith("/info"):
            self.calls.append((method, path))
            slug = path.split("/")[2]
            app = next(a for a in self.installed if a["slug"] == slug)
            return copy.deepcopy(
                {
                    **app,
                    **self.settings,
                    "name": "Demo",
                    "schema": [{"name": "username", "type": "string"}],
                }
            )
        if path.endswith("/options/validate"):
            self.calls.append((method, path))
            return {"valid": not payload.get("invalid"), "message": "Bad value initial-app-secret"}
        if path.endswith("/options"):
            self.calls.append((method, path))
            self.settings.update(copy.deepcopy(payload))
            return {}
        return super().call(method, path, payload)

    def logs(self, path):
        assert path == "/addons/local_demo/logs"
        return self.log_text, self.truncated


@pytest.fixture
def controls(manager):
    manager.supervisor = ControlsSupervisor()
    manager.supervisor.addons = manager.addons
    repo_id, root = prepared(manager)
    manager.deploy(repo_id, "demo")
    return manager, Applications(manager), repo_id, root


def test_configuration_validates_saves_and_does_not_persist_options(controls):
    manager, apps, repo_id, _ = controls
    config = apps.configuration(repo_id, "demo")
    assert "initial-app-secret" in config["yaml"]
    changes = yaml.safe_load(config["yaml"])
    changes["options"] = {
        "password": "new-app-secret",
        "nested": {"enabled": True, "list": [1, "two"]},
    }
    changes["boot"] = "auto"
    changes["network"] = {"1234/tcp": 5678}
    source = yaml.safe_dump(changes)
    assert apps.validate(repo_id, "demo", source) == changes
    result = apps.save(repo_id, "demo", source, config["revision"], restart=True)
    assert result == {"ok": True}
    assert manager.supervisor.settings == changes
    assert not any(
        path.endswith("/restart") for _, path in manager.supervisor.calls
    )  # Stopped apps stay stopped.
    assert "new-app-secret" not in manager.state_file.read_text()
    assert "initial-app-secret" not in manager.log_path.read_text()
    assert "new-app-secret" not in json.dumps(manager.snapshot())


def test_changed_settings_and_invalid_schema_do_not_get_saved(controls):
    manager, apps, repo_id, _ = controls
    config = apps.configuration(repo_id, "demo")
    manager.supervisor.settings["watchdog"] = True
    with pytest.raises(Problem) as caught:
        apps.save(repo_id, "demo", config["yaml"], config["revision"])
    assert caught.value.code == "config_changed"
    with pytest.raises(Problem) as caught:
        apps.validate(
            repo_id, "demo", "options:\n  invalid: true\n  password: initial-app-secret\n"
        )
    assert caught.value.code == "config_invalid"
    assert "initial-app-secret" not in str(caught.value)
    assert not any(path.endswith("/options") for _, path in manager.supervisor.calls)


@pytest.mark.parametrize(
    "source",
    [
        "[]",
        "options: []",
        "options: {a: 1, a: 2}",
        "options: {1: test}",
        "options: {day: 2026-11-06}",
        "options: {number: .inf}",
        "options: &cycle {again: *cycle}",
        "protected: false",
        "boot: never",
        "watchdog: test",
        "options: !!python/object:evil {}",
    ],
)
def test_yaml_rejects_ambiguous_unsafe_or_unsupported_values(source):
    with pytest.raises(Problem):
        parse_configuration(source)


def test_yaml_supports_secret_references_and_nested_options():
    assert parse_configuration(
        "options:\n  password: !secret private_password\n  list: [true, null, 42]\n"
    )["options"] == {"password": "!secret private_password", "list": [True, None, 42]}


def test_configuration_restart_and_partial_failure_are_explicit(controls):
    manager, apps, repo_id, _ = controls
    manager.supervisor.installed[0]["state"] = "started"
    config = apps.configuration(repo_id, "demo")
    apps.save(repo_id, "demo", config["yaml"], config["revision"], restart=True)
    assert ("POST", "/addons/local_demo/restart") in manager.supervisor.calls
    manager.supervisor.fail = "/addons/local_demo/restart"
    with pytest.raises(Problem) as caught:
        apps.save(repo_id, "demo", config["yaml"], config["revision"], restart=True)
    assert caught.value.code == "config_restart_failed"


def test_read_only_logs_work_during_pending_recovery_and_redact_credentials(controls):
    manager, apps, repo_id, _ = controls
    manager.state["transactions"]["demo"] = {"kind": "uninstall"}
    manager.save()
    result = apps.logs(repo_id, "demo")
    assert "Started" in result["text"] and "\x1b" not in result["text"]
    assert "initial-app-secret" not in result["text"]
    assert "<script>" in result["text"]  # Plain text, never rendered as markup.
    with pytest.raises(Problem) as caught:
        apps.validate(repo_id, "demo", "options: {}")
    assert caught.value.code == "recovery_required"


def test_uninstalled_foreign_and_self_apps_cannot_be_configured(controls):
    manager, apps, repo_id, _ = controls
    with pytest.raises(Problem):
        apps.configuration(repo_id, "private_git_manager")
    manager.state["deployments"]["demo"]["repo_id"] = "foreign"
    manager.save()
    with pytest.raises(Problem):
        apps.configuration(repo_id, "demo")
    manager.state["deployments"]["demo"]["repo_id"] = repo_id
    manager.supervisor.installed.clear()
    manager.save()
    with pytest.raises(Problem) as caught:
        apps.configuration(repo_id, "demo")
    assert caught.value.code == "app_not_installed"


def test_logs_http_is_bounded_plain_text_and_authenticated(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "isolated-token")

    def response(request):
        assert request.url.path == "/addons/local_demo/logs"
        assert request.headers["Authorization"] == "Bearer isolated-token"
        return httpx.Response(200, content=b"line\n" * 150000)

    text, truncated = Supervisor(httpx.MockTransport(response)).logs("/addons/local_demo/logs")
    assert len(text) == 512 * 1024 and truncated


def test_uncertain_config_save_does_not_leak_values(controls, monkeypatch):
    manager, apps, repo_id, _ = controls
    config = apps.configuration(repo_id, "demo")
    original = manager.supervisor.call

    def uncertain(method, path, payload=None):
        result = original(method, path, payload)
        if path.endswith("/options"):
            raise SupervisorUncertain("lost response", "supervisor_uncertain")
        return result

    monkeypatch.setattr(manager.supervisor, "call", uncertain)
    with pytest.raises(Problem) as caught:
        apps.save(repo_id, "demo", config["yaml"], config["revision"])
    assert caught.value.code == "config_uncertain"
    assert "initial-app-secret" not in manager.log_path.read_text()
