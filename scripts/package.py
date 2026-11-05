#!/usr/bin/env python3
"""Build an allowlisted, reproducible archive; never package user data or keys."""

import gzip
import hashlib
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "private_git_manager"
# Deliberately explicit: new top-level files need a packaging decision.
FILES = {
    "config.yaml",
    "Dockerfile",
    "requirements.txt",
    ".dockerignore",
    "README.md",
    "DOCS.md",
    "CHANGELOG.md",
    "icon.png",
    "logo.png",
}
manifest = (SOURCE / "config.yaml").read_text()
version = next(
    line.split(":", 1)[1].strip().strip('"')
    for line in manifest.splitlines()
    if line.startswith("version:")
)
paths = sorted(
    [SOURCE / name for name in FILES]
    + [
        p
        for p in (SOURCE / "app").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    ]
)
for path in paths:
    if path.is_symlink() or not path.is_file():
        raise SystemExit(f"Invalid package file: {path}")
    if path.suffix in {".json", ".py", ".js", ".md", ".txt", ".yaml", ".yml", ".html", ".css"}:
        if "-----BEGIN OPENSSH PRIVATE KEY-----" in path.read_text():
            raise SystemExit("A private key was found in a package file")
output = ROOT / "dist" / f"ha-private-git-manager-{version}.tar.gz"
output.parent.mkdir(exist_ok=True)
with output.open("wb") as raw:
    with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as archive:
            for path in paths:
                info = archive.gettarinfo(str(path), arcname=str(path.relative_to(ROOT)))
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.mode = 0o644
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
checksum = hashlib.sha256(output.read_bytes()).hexdigest()
output.with_suffix(output.suffix + ".sha256").write_text(checksum + "  " + output.name + "\n")
print(f"{output.name}: {len(paths)} files, SHA256 {checksum}")
