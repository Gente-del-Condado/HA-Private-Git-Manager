import shutil

from app.core import Manager
from app.jobs import Jobs
from app.storage import migrate_app_data
from test_manager import manager as manager


def test_upgrade_and_reinstall_keep_keys_and_state(manager, tmp_path):
    legacy = manager.data
    public = manager.key_create("Migration test")
    key = public["id"]
    private = (legacy / "keys" / key).read_bytes()
    repo = manager.repo_add("Migration test", "https://example.org/u/r", "main", token="test-token")
    (legacy / "repos" / repo).mkdir()
    (legacy / "repos" / repo / "source.txt").write_text("cached source")
    jobs = Jobs(manager)
    jobs.close()
    target = tmp_path / "config" / "private-git-manager"

    migrate_app_data(legacy, target)
    assert (legacy / "keys" / key).read_bytes() == private
    assert (target.stat().st_mode & 0o777) == 0o700
    assert (target / "keys" / key).stat().st_mode & 0o077 == 0

    # Supervisor removes private app data when uninstalling while retaining app_config.
    shutil.rmtree(legacy)
    migrate_app_data(legacy, target)
    reinstalled = Manager(target, manager.addons, manager.supervisor)
    assert reinstalled.repo(repo)["token"] == "test-token"
    assert reinstalled.snapshot()["keys"][key] == public
    assert (target / "keys" / key).read_bytes() == private
    assert (target / "repos" / repo / "source.txt").read_text() == "cached source"
    assert (target / "jobs.json").exists()

    # A stale legacy volume must not overwrite the retained state.
    legacy.mkdir()
    (legacy / "state.json").write_text("{}")
    migrate_app_data(legacy, target)
    assert Manager(target, manager.addons, manager.supervisor).snapshot()["keys"][key] == public
