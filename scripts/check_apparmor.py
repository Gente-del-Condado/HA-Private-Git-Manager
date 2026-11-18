#!/usr/bin/env python3
"""Comprueba permisos del gestor solo en una instalación de laboratorio aislada."""

import argparse
import errno
import os
import re
import socket
import ssl
import subprocess
import tempfile
from pathlib import Path


def denied(action):
    try:
        action()
    except OSError as error:
        assert error.errno in (errno.EACCES, errno.EPERM), error.errno
    else:
        raise AssertionError("Se permitió una operación prohibida")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-disposable-lab", action="store_true", required=True)
    parser.parse_args()
    profile = Path("/proc/self/attr/current").read_text().strip()
    assert profile.endswith("_private_git_manager_apparmor_lab (enforce)"), profile
    assert Path("/data/.apparmor-lab").read_text().strip() == "disposable-lab"
    # Nunca dirigir las pruebas de integración al montaje real de Core.
    assert not os.path.ismount("/homeassistant")
    assert (
        Path("/homeassistant/custom_components/.apparmor-lab").read_text().strip()
        == "isolated-core-fixture"
    )
    environment = dict(os.environ)
    environment.pop("SUPERVISOR_TOKEN", None)

    def run(command, data=None):
        return subprocess.run(
            command, input=data, env=environment, check=True, capture_output=True, timeout=90
        )

    with tempfile.TemporaryDirectory(prefix="pgm-apparmor-") as folder:
        root = Path(folder)
        key = root / "ssh-key"
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)])
        assert key.with_suffix(".pub").read_text().startswith("ssh-ed25519 ")
        run(["ssh", "-V"])
        repo = root / "repo"
        run(["git", "init", "--quiet", str(repo)])
        run(["git", "-C", str(repo), "config", "core.hooksPath", "/dev/null"])
        (repo / "fixture.txt").write_text("fixture-only")
        run(["git", "-C", str(repo), "add", "fixture.txt"])
        run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=AppArmor Lab",
                "-c",
                "user.email=lab@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ]
        )
        assert run(["git", "-C", str(repo), "show", "HEAD:fixture.txt"]).stdout == b"fixture-only"
        identity = root / "age-key"
        generated = run(["age-keygen", "-o", str(identity)])
        recipient = re.search(rb"age1[a-z0-9]{58}", generated.stderr)[0].decode()
        encrypted = run(["age", "--encrypt", "--recipient", recipient], b"fixture-roundtrip").stdout
        assert (
            run(["age", "--decrypt", "--identity", str(identity)], encrypted).stdout
            == b"fixture-roundtrip"
        )
    askpass = "/config/private-git-manager/askpass.sh"
    environment.update(PGM_USERNAME="fixture-user", PGM_TOKEN="fixture-token")
    assert run([askpass, "Username"]).stdout == b"fixture-user"
    assert run([askpass, "Password"]).stdout == b"fixture-token"
    assert socket.getaddrinfo("supervisor", 80)
    assert ssl.create_default_context().get_ca_certs()
    denied(lambda: os.open("/etc/shadow", os.O_RDONLY))
    denied(lambda: Path("/homeassistant/.storage/apparmor-canary").read_bytes())
    denied(lambda: Path("/app/.apparmor-write-probe").write_text("fixture"))
    denied(
        lambda: subprocess.run(["/usr/local/bin/pip", "--version"], check=True, capture_output=True)
    )
    print(
        "PGM_APPARMOR_OK: enforce, Git, SSH, age, askpass y DNS/TLS; secretos de Core y escritura de programas denegados"
    )


if __name__ == "__main__":
    main()
