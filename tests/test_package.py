import hashlib
import subprocess
import sys
import tarfile
from pathlib import Path


def test_release_archive_reproducible_and_contains_no_runtime_data():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts/package.py"
    output = root / "dist/ha-private-git-manager-0.2.0.tar.gz"
    subprocess.check_call([sys.executable, str(script)], stdout=subprocess.DEVNULL)
    first = hashlib.sha256(output.read_bytes()).hexdigest()
    subprocess.check_call([sys.executable, str(script)], stdout=subprocess.DEVNULL)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == first
    with tarfile.open(output) as archive:
        names = archive.getnames()
        assert "private_git_manager/config.yaml" in names
        assert "private_git_manager/icon.png" in names
        assert "private_git_manager/logo.png" in names
        assert "private_git_manager/app/static/locales/en.json" in names
        assert not any(
            "__pycache__" in name
            or ".dev-" in name
            or name.endswith(("state.json", "jobs.json", ".log", ".pub"))
            for name in names
        )
        assert all(
            name.startswith("private_git_manager/") and ".." not in Path(name).parts
            for name in names
        )
