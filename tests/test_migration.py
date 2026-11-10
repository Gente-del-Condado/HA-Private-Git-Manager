import shutil
import subprocess

import pytest
from app.core import Manager, Problem
from app.migration import PREFIX, Migration


def test_encrypted_catalog_from_a_clean_manager(tmp_path, monkeypatch):
    if not shutil.which("age") or not shutil.which("age-keygen"):
        pytest.skip("Se necesita age y age-keygen para la prueba de cifrado real.")
    remote = tmp_path / "recovery.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    url = "ssh://git@example.test/team/recovery.git"
    origin = Manager(tmp_path / "origin", tmp_path / "origin-addons")
    target = Manager(tmp_path / "clean", tmp_path / "clean-addons")
    for manager in (origin, target):
        # Usa el transporte Git real con un destino local aislado. El mismo flujo se prueba por SSH.
        monkeypatch.setattr(manager, "git_env", lambda repo: {"GIT_ALLOW_PROTOCOL": "file"})
    writer = origin.repo_add("Recuperación", url, "main")
    reader = target.repo_add("Recuperación", url, "main")
    origin.repo_add(
        "Catálogo", "https://example.test/team/apps.git", "stable", token="secret-fixture"
    )
    identity = tmp_path / "identity.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipient = subprocess.check_output(["age-keygen", "-y", str(identity)], text=True).strip()
    secret = next(
        line for line in identity.read_text().splitlines() if line.startswith("AGE-SECRET")
    )

    outbound = Migration(origin, writer)
    inbound = Migration(target, reader)
    outbound.url = inbound.url = str(remote)
    result = outbound.export(recipient)
    assert inbound.copies() == [result]
    raw = subprocess.check_output(
        ["git", "--git-dir", str(remote), "show", f"{PREFIX}{result['id']}:config.json.age"]
    )
    assert raw.startswith(b"age-encryption.org/v1")
    assert b"secret-fixture" not in raw
    with pytest.raises(Problem) as stale:
        inbound.read(result["id"], "0" * 40, secret)
    assert stale.value.code == "migration_changed"
    catalog = inbound.read(result["id"], result["commit"], secret)
    assert "secret-fixture" not in catalog.model_dump_json()
    assert len(target.state["repos"]) == 1
    assert inbound.apply(catalog) == {"added": 1}
    assert inbound.apply(catalog) == {"added": 0}
    restored = Manager(target.data, target.addons).snapshot()
    imported = next(repo for repo in restored["repos"].values() if repo["name"] == "Catálogo")
    assert imported["ref"] == "stable"
    assert imported["has_token"] is False
    assert imported["commit"] is None
