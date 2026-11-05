import pytest
from app import main
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(main.app)


def test_ingress_only(monkeypatch, client):
    monkeypatch.delenv("PGM_DEV", raising=False)
    assert client.get("/").status_code == 403
    assert client.get("/", headers={"X-Forwarded-For": "172.30.32.2"}).status_code == 403


def test_dev_and_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Private Git" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200


def test_csrf_and_cross_site(client):
    assert client.post("/api/keys", json={"name": "test"}).status_code == 403
    assert (
        client.post(
            "/api/keys",
            json={"name": "test"},
            headers={"X-PGM-Request": "1", "Sec-Fetch-Site": "cross-site"},
        ).status_code
        == 403
    )


def test_deployment_requires_confirmation(client):
    response = client.post(
        "/api/repos/missing/deploy",
        json={"slug": "demo", "expected_commit": "a" * 40},
        headers={"X-PGM-Request": "1"},
    )
    assert response.status_code == 400
    assert "Confirma" in response.json()["detail"]


def test_api_keys_and_state(client):
    response = client.post("/api/keys", json={"name": "API"}, headers={"X-PGM-Request": "1"})
    assert response.status_code == 200
    key = response.json()
    assert key["public"].startswith("ssh-ed25519")
    snapshot = client.get("/api/state").json()
    assert key["id"] in snapshot["keys"]
    assert "PRIVATE KEY" not in str(snapshot)
    assert (
        client.delete("/api/keys/" + key["id"], headers={"X-PGM-Request": "1"}).status_code == 200
    )
