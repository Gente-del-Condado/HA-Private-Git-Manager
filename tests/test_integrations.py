import json
from pathlib import Path

import pytest
from app.core import Manager, Problem, run
from app.integrations import Integrations, catalog


def test_deploy_integration_from_reviewed_checkout(tmp_path):
    manager = Manager(tmp_path / "data", tmp_path / "addons")
    config = tmp_path / "core"
    config.mkdir()
    installer = Integrations(manager, config)
    repo_id = manager.repo_add("Forgejo", "https://git.example.test/team/repo.git", "main")
    checkout = manager.data / "repos" / repo_id
    source = checkout / "custom_components" / "demo_integration"
    source.mkdir(parents=True)
    run(["git", "init", str(checkout)])

    def commit(version):
        (source / "__init__.py").write_text(f'VERSION = "{version}"\n')
        (source / "manifest.json").write_text(
            json.dumps({"domain": source.name, "name": "Demo", "version": version})
        )
        run(["git", "-C", str(checkout), "add", "."])
        run(
            [
                "git",
                "-C",
                str(checkout),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                version,
            ]
        )
        manager.repo(repo_id)["commit"] = manager.checkout_commit(checkout)

    commit("1.0.0")
    assert [item["domain"] for item in catalog(checkout)] == [source.name]
    first = installer.inspect(repo_id, source.name)
    assert first["installed_version"] is None
    installer.deploy(repo_id, source.name, first["commit"], None, False)

    commit("1.1.0")
    next_ = installer.inspect(repo_id, source.name)
    target = config / "custom_components" / source.name
    with pytest.raises(Problem) as stale:
        installer.deploy(repo_id, source.name, first["commit"], next_["local_digest"], False)
    assert stale.value.code == "integration_changed"
    assert '"1.0.0"' in (target / "__init__.py").read_text()

    result = installer.deploy(repo_id, source.name, next_["commit"], next_["local_digest"], False)
    assert result["restart_required"]
    assert '"1.1.0"' in (target / "__init__.py").read_text()
    previous = config / Path(result["previous"])
    assert '"1.0.0"' in (previous / "__init__.py").read_text()
