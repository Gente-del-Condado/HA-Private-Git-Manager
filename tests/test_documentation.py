import os
import shutil
import subprocess
from pathlib import Path

import pytest
from app.core import Manager, Problem
from app.documentation import MAX_DOCUMENT, RepositoryDocs
from test_manager import addon


@pytest.fixture
def docs(tmp_path):
    return RepositoryDocs(tmp_path, "repo123")


def test_markdown_formats_headings_tables_code_and_blocks_active_html(docs):
    (docs.root / "README.md").write_text("""# App

**Presentación** con *formato*.

| A | B |
|---|---|
| 1 | 2 |

```python
print("hello")
```
<script>window.exposed=true</script>
[x](javascript:alert(1))
""")
    result = docs.document("README.md")
    assert '<h1 id="pgm-readme-app">' in result["html"]
    assert "<strong>Presentación</strong>" in result["html"]
    assert "<table>" in result["html"] and "<pre>" in result["html"]
    assert "<script>" not in result["html"]
    assert 'href="javascript:' not in result["html"]
    assert result["available"]


def test_local_docs_and_images_use_private_relative_ingress_urls(docs):
    (docs.root / "images").mkdir()
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "private_git_manager/icon.png",
        docs.root / "images/icon.png",
    )
    (docs.root / "DOCS.md").write_text("# Uso")
    (docs.root / "README.md").write_text(
        "![Icono](images/icon.png)\n\n[Uso](DOCS.md)\n\n[Web](https://example.org)"
    )
    result = docs.document("README.md")
    assert 'src="api/repos/repo123/asset?path=images%2Ficon.png"' in result["html"]
    assert 'href="api/repos/repo123/document?path=DOCS.md"' in result["html"]
    assert 'target="_blank"' in result["html"] and 'rel="noopener noreferrer"' in result["html"]
    assert docs.image("images/icon.png")[1] == "image/png"


def test_external_svg_and_data_images_do_not_load_automatically(docs):
    (docs.root / "unsafe.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
    )
    (docs.root / "README.md").write_text(
        "![Tracker](https://example.org/tracker.png)\n![SVG](unsafe.svg)\n![Inline](data:image/png;base64,AAAA)"
    )
    result = docs.document("README.md")
    assert "<img" not in result["html"]
    assert "[Tracker]" in result["html"]
    with pytest.raises(Problem):
        docs.image("unsafe.svg")


@pytest.mark.parametrize(
    "path", ["../secret.md", "/etc/passwd", ".git/config.md", ".ssh/key.md", "README.md\x00"]
)
def test_private_path_escape_is_rejected(docs, path):
    with pytest.raises(Problem):
        docs.document(path)


def test_symlinked_document_and_parent_directory_are_rejected(docs, tmp_path):
    (tmp_path / "source.md").write_text("private")
    (docs.root / "README.md").symlink_to(tmp_path / "source.md")
    with pytest.raises(Problem):
        docs.document("README.md")
    assert docs.find(".", ("README.md",)) is None
    (docs.root / "linked").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(Problem):
        docs.document("linked/source.md")


def test_markdown_size_and_file_type_limits(docs):
    (docs.root / "README.md").write_text("a" * (MAX_DOCUMENT + 1))
    (docs.root / "state.json").write_text('{"token":"private"}')
    for path in ["README.md", "state.json"]:
        with pytest.raises(Problem):
            docs.document(path)


def test_relative_parent_links_can_resolve_within_repository(docs):
    (docs.root / "app").mkdir()
    (docs.root / "README.md").write_text("# Catalog")
    (docs.root / "app/README.md").write_text("[Catálogo](../README.md) [Escape](../../outside.md)")
    result = docs.document("app/README.md")
    assert 'href="api/repos/repo123/document?path=README.md"' in result["html"]
    assert 'href="#"' in result["html"]


def test_master_repository_and_individual_app_are_detected(tmp_path, monkeypatch):
    remote = tmp_path / "remote"
    addon(remote / "one", slug="one")
    addon(remote / "two", slug="two")
    (remote / "README.md").write_text("# Mis aplicaciones\n\nColección de aplicaciones privadas.\n")
    (remote / "repository.yaml").write_text(
        "name: Mi catálogo\nmaintainer: Mi equipo\nurl: https://example.org\n"
    )
    (remote / "one/README.md").write_text("# Aplicación uno")
    (remote / "two/DOCS.md").write_text("# Configuración de dos")
    subprocess.run(["git", "init", "-b", "main", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(remote),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-m",
            "catalog",
        ],
        check=True,
        capture_output=True,
    )
    manager = Manager(tmp_path / "data", tmp_path / "addons")
    repo_id = manager.repo_add("Mis apps", "https://example.org/u/r", "main")
    manager.repo(repo_id)["url"] = str(remote)
    monkeypatch.setattr(manager, "git_env", lambda _: dict(os.environ, GIT_ALLOW_PROTOCOL="file"))
    manager.sync(repo_id)
    repo = manager.repo(repo_id)
    assert repo["catalog"]["kind"] == "collection"
    assert repo["catalog"]["name"] == "Mi catálogo"
    assert repo["catalog"]["maintainer"] == "Mi equipo"
    assert repo["catalog"]["app_count"] == 2
    assert "Colección" in repo["catalog"]["description"]
    original_digests = dict(repo["app_digests"])
    original_commit = repo["commit"]
    (remote / "README.md").write_text("# Otro título\n\nSolo cambia la presentación del catálogo.")
    subprocess.run(["git", "-C", str(remote), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(remote),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-m",
            "root README only",
        ],
        check=True,
        capture_output=True,
    )
    manager.sync(repo_id)
    assert repo["commit"] != original_commit
    assert repo["app_digests"] == original_digests

    assert "Otro título" in manager.read_document(repo_id)["html"]
    assert "Aplicación uno" in manager.read_document(repo_id, "one")["html"]
    assert "Configuración de dos" in manager.read_document(repo_id, "two", "docs")["html"]
    assert not manager.read_document(repo_id, "two")["available"]
    # Existing data gains presentation metadata after an application restart.
    repo.pop("catalog")
    for app in repo["apps"]:
        for key in ("readme_path", "docs_path", "icon_path", "blocked_reason"):
            app.pop(key)
    manager.save()
    restarted = Manager(manager.data, manager.addons)
    assert restarted.repo(repo_id)["catalog"]["name"] == "Mi catálogo"
    assert restarted.repo(repo_id)["apps"][0]["readme_path"] == "one/README.md"
    assert restarted.repo(repo_id)["apps"] == restarted.discover(restarted.data / "repos" / repo_id)


def test_single_root_app_does_not_require_repository_manifest(docs):
    addon(docs.root)
    (docs.root / "README.md").write_text("# Mi app\n\nDescripción de una aplicación.")
    assert docs.catalog([{"slug": "demo"}])["kind"] == "single"
    assert docs.app_files(".")["readme_path"] == "README.md"


def test_invalid_repository_metadata_is_reported(docs):
    (docs.root / "repository.yaml").write_text("name: [not, a, string]")
    with pytest.raises(Problem) as caught:
        docs.catalog([])
    assert caught.value.code == "catalog_invalid"


def test_master_catalog_can_include_the_manager_without_blocking_other_apps(tmp_path):
    manager = Manager(tmp_path / "data", tmp_path / "addons")
    repo_id = manager.repo_add("Master", "https://example.org/u/r", "main")
    root = manager.data / "repos" / repo_id
    addon(root / "first", slug="first")
    addon(root / "private_git_manager", slug="private_git_manager")
    manager.repo(repo_id).update(commit="a" * 40, apps=manager.discover(root))
    apps = {app["slug"]: app for app in manager.repo(repo_id)["apps"]}
    assert apps["first"]["blocked_reason"] is None
    assert apps["private_git_manager"]["blocked_reason"] == "manager_self"
    with pytest.raises(Problem) as caught:
        manager.deploy(repo_id, "private_git_manager")
    assert caught.value.code == "manager_self"
