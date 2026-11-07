import httpx
import pytest
from app import main


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
