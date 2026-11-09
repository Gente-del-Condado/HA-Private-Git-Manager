from pathlib import Path

import httpx
import pytest
from app import main
from app.core import Manager, run


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_yunohost_requires_the_local_proxy(monkeypatch):
    monkeypatch.setattr(main, "YUNOHOST", True)
    marker = {"X-PGM-Proxy": "yunohost"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app, client=("127.0.0.1", 1234)),
        base_url="http://test",
    ) as client:
        assert (await client.get("/api/state", headers=marker)).status_code == 403
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app, client=None),
        base_url="http://test",
    ) as client:
        assert (await client.get("/api/state")).status_code == 403
        response = await client.get("/api/state", headers=marker)
        assert response.status_code == 200
        assert response.json()["platform"] == "yunohost"
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]
        assert (
            await client.post("/api/keys", headers=marker, json={"name": "Denied"})
        ).status_code == 403
        assert (
            await client.post(
                "/api/keys",
                headers={**marker, "X-PGM-Request": "1", "Sec-Fetch-Site": "cross-site"},
                json={"name": "Denied"},
            )
        ).status_code == 403


@pytest.fixture
def native_repo(tmp_path, monkeypatch):
    manager = Manager(tmp_path / "data", tmp_path / "addons")
    repo_id = "private-package"
    source = manager.data / "repos" / repo_id
    source.mkdir()
    (source / "manifest.toml").write_text(
        'packaging_format = 2\nid = "2fa_auth"\nname = "Private package"\nversion = "1.0~ynh1"\n'
    )
    (source / ".gitignore").write_text("local-secret\n")
    (source / "scripts").mkdir()
    for name in ("install", "upgrade", "remove"):
        path = source / "scripts" / name
        path.write_text("#!/bin/bash\nexit 0\n")
        path.chmod(0o755)
    run(["git", "init", "-q", str(source)])
    run(["git", "add", "."], cwd=source)
    run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Fixture",
        ],
        cwd=source,
    )
    commit = run(["git", "rev-parse", "HEAD"], cwd=source)
    manager.state["repos"][repo_id] = {"id": repo_id, "commit": commit}
    manager.save()
    monkeypatch.setattr(main, "manager", manager)
    monkeypatch.setattr(main, "YUNOHOST", True)
    return repo_id, source, commit


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_native_package_is_pinned_and_clean(native_repo):
    repo_id, source, commit = native_repo
    headers = {"X-PGM-Proxy": "yunohost", "X-PGM-Request": "1"}
    endpoint = f"/api/repos/{repo_id}/yunohost-stage"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app, client=None),
        base_url="https://test",
        headers=headers,
    ) as client:
        state = (await client.get("/api/state")).json()
        assert state["repos"][repo_id]["yunohost_package"] == {
            "id": "2fa_auth",
            "name": "Private package",
            "version": "1.0~ynh1",
        }
        stale = await client.post(endpoint, json={"expected_commit": "a" * 40})
        assert stale.json()["code"] == "yunohost_source_changed"
        (source / "local-secret").write_text("ignored contents")
        dirty = await client.post(endpoint, json={"expected_commit": commit})
        assert dirty.json()["code"] == "yunohost_source_changed"
        (source / "local-secret").unlink()
        ready = await client.post(endpoint, json={"expected_commit": commit})
        assert ready.status_code == 200, ready.text
        path = Path(ready.json()["path"])
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert not (path / ".git").exists()
        assert (path / "scripts" / "install").stat().st_mode & 0o111
        (source / "manifest.toml").write_text("Changed after preparation")
        assert 'version = "1.0~ynh1"' in (path / "manifest.toml").read_text()
        removed = await client.delete(f"/api/yunohost-stages/{ready.json()['id']}")
        assert removed.status_code == 200
        assert not path.exists()
        assert source.exists()


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_native_staging_is_not_exposed_on_home_assistant(monkeypatch):
    monkeypatch.setattr(main, "YUNOHOST", False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app),
        base_url="http://test",
        headers={"X-PGM-Request": "1"},
    ) as client:
        assert (
            await client.post(
                "/api/repos/unused/yunohost-stage", json={"expected_commit": "a" * 40}
            )
        ).status_code == 404
