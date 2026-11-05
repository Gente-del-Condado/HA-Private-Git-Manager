"""Integration tests with real SSH and authenticated TLS Git servers on loopback."""

import base64
import os
import pwd
import shutil
import socket
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from app.core import Manager, Problem


def command(*args, **kwargs):
    return subprocess.check_output(args, stderr=subprocess.STDOUT, text=True, **kwargs).strip()


@pytest.fixture
def remote(tmp_path):
    path = tmp_path / "source"
    path.mkdir()
    (path / "config.yaml").write_text(
        'name: Transport test\nversion: "1.0.0"\nslug: transport_test\ndescription: Real Git transport\narch: [amd64, aarch64]\n'
    )
    (path / "Dockerfile").write_text("FROM alpine:3.22\n")
    command("git", "init", "-b", "main", str(path))
    command("git", "-C", str(path), "add", ".")
    command(
        "git",
        "-C",
        str(path),
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-m",
        "first",
    )
    return path


def test_real_ssh_clone_and_host_pinning(tmp_path, remote):
    if not shutil.which("sshd"):
        pytest.skip("OpenSSH server is not installed")
    manager = Manager(tmp_path / "manager", tmp_path / "addons")
    client_key = manager.key_create("Local integration")
    host_key = tmp_path / "host_key"
    command("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(host_key))
    authorized = tmp_path / "authorized_keys"
    authorized.write_text(client_key["public"] + "\n")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    username = pwd.getpwuid(os.getuid()).pw_name
    config = tmp_path / "sshd_config"
    config.write_text(f"""Port {port}
ListenAddress 127.0.0.1
HostKey {host_key}
PidFile {tmp_path / "sshd.pid"}
AuthorizedKeysFile {authorized}
StrictModes no
PasswordAuthentication no
KbdInteractiveAuthentication no
UsePAM no
PermitRootLogin no
AllowUsers {username}
LogLevel ERROR
""")
    error_file = tmp_path / "sshd.log"
    with error_file.open("w") as errors:
        server = subprocess.Popen(
            [shutil.which("sshd"), "-D", "-e", "-f", str(config)], stdout=errors, stderr=errors
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    pytest.fail("Isolated sshd could not start: " + error_file.read_text())
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.02)
            url = f"ssh://{username}@127.0.0.1:{port}{remote}"
            identity = manager.scan(url)
            manager.trust(url, identity["line"], identity["fingerprint"])
            repo_id = manager.repo_add("SSH real", url, "main", key_id=client_key["id"])
            manager.sync(repo_id)
            assert manager.repo(repo_id)["apps"][0]["slug"] == "transport_test"
            manager.verify_checkout(manager.repo(repo_id), manager.data / "repos" / repo_id)
            assert manager.repo(repo_id)["commit"] == command(
                "git", "-C", str(remote), "rev-parse", "HEAD"
            )
            # A second valid key is not the server key: pinning must reject the change.
            wrong = " ".join(client_key["public"].split()[:2])
            manager.state["hosts"][f"127.0.0.1:{port}"]["line"] = f"[127.0.0.1]:{port} {wrong}"
            with pytest.raises(Problem) as caught:
                manager.sync(repo_id)
            assert caught.value.code == "host_key_changed"
        finally:
            server.terminate()
            server.wait(timeout=5)


def test_real_https_clone_with_askpass(tmp_path, remote, monkeypatch):
    bare = tmp_path / "remote.git"
    command("git", "clone", "--bare", str(remote), str(bare))
    certificate, private_key = tmp_path / "cert.pem", tmp_path / "key.pem"
    command(
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        str(private_key),
        "-out",
        str(certificate),
        "-days",
        "1",
        "-subj",
        "/CN=127.0.0.1",
        "-addext",
        "subjectAltName=IP:127.0.0.1",
    )
    token = "integration-only-token"
    authorization = "Basic " + base64.b64encode(("tester:" + token).encode()).decode()
    backend = str(Path(command("git", "--exec-path")) / "git-http-backend")
    authenticated = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_git(self):
            if self.headers.get("Authorization") != authorization:
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Basic realm="Private Git test"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            authenticated.append(self.command)
            path = urlsplit(self.path)
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            env = dict(
                os.environ,
                GIT_PROJECT_ROOT=str(tmp_path),
                GIT_HTTP_EXPORT_ALL="1",
                PATH_INFO=path.path,
                QUERY_STRING=path.query,
                REQUEST_METHOD=self.command,
                CONTENT_TYPE=self.headers.get("Content-Type", ""),
                CONTENT_LENGTH=str(len(body)),
                REMOTE_USER="tester",
                SERVER_PROTOCOL="HTTP/1.1",
            )
            result = subprocess.run([backend], input=body, capture_output=True, env=env, check=True)
            headers, payload = result.stdout.split(b"\r\n\r\n", 1)
            self.send_response(200)
            for line in headers.decode().split("\r\n"):
                name, value = line.split(":", 1)
                if name.lower() != "status":
                    self.send_header(name, value.strip())
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = handle_git
        do_POST = handle_git

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(certificate, private_key)
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        manager = Manager(tmp_path / "manager", tmp_path / "addons")
        url = f"https://127.0.0.1:{server.server_port}/remote.git"
        repo_id = manager.repo_add("HTTPS real", url, "main", username="tester", token=token)
        original = manager.git_env
        # Trust only this fixture's CA; production continues to require valid system TLS.
        monkeypatch.setattr(
            manager, "git_env", lambda repo: dict(original(repo), GIT_SSL_CAINFO=str(certificate))
        )
        manager.sync(repo_id)
        assert authenticated and manager.repo(repo_id)["apps"][0]["slug"] == "transport_test"
        manager.verify_checkout(manager.repo(repo_id), manager.data / "repos" / repo_id)
        git_config = (manager.data / "repos" / repo_id / ".git" / "config").read_text()
        assert token not in git_config
        assert token not in str(manager.snapshot())
        assert token not in manager.log_path.read_text()
        manager.repo(repo_id)["token"] = "wrong"
        with pytest.raises(Problem) as caught:
            manager.sync(repo_id)
        assert caught.value.code == "credential_error"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_checkout_integrity_and_recovery_before_metadata_commit(tmp_path, remote):
    manager = Manager(tmp_path / "manager", tmp_path / "addons")
    repo_id = manager.repo_add("Local fixture", "https://example.org/u/r", "main")
    target = manager.data / "repos" / repo_id
    command("git", "clone", str(remote), str(target))
    original = command("git", "-C", str(target), "rev-parse", "HEAD")
    manager.repo(repo_id)["commit"] = original
    manager.save()
    manager.verify_checkout(manager.repo(repo_id), target)
    (target / "Dockerfile").write_text("FROM changed\n")
    with pytest.raises(Problem) as caught:
        manager.verify_checkout(manager.repo(repo_id), target)
    assert caught.value.code == "source_changed"
    command("git", "-C", str(target), "checkout", "--", "Dockerfile")
    old = target.with_name(repo_id + "-old")
    target.rename(old)
    command("git", "clone", str(remote), str(target))
    (target / "Dockerfile").write_text("FROM next-version\n")
    command("git", "-C", str(target), "add", ".")
    command(
        "git",
        "-C",
        str(target),
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "commit",
        "-m",
        "next",
    )
    # Simulate loss of power after rename, but before state.json recorded the new commit.
    restarted = Manager(manager.data, manager.addons)
    assert restarted.checkout_commit(target) == original
    assert not old.exists()
    restarted.verify_checkout(restarted.repo(repo_id), target)
