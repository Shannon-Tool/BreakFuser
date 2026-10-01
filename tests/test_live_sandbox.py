from __future__ import annotations

import httpx
import pytest

from bench.live_sandbox import create_sandbox


@pytest.mark.asyncio
async def test_sandbox_has_known_loopback_vulnerabilities() -> None:
    transport = httpx.ASGITransport(app=create_sandbox())
    async with httpx.AsyncClient(transport=transport, base_url="http://sandbox") as client:
        assert (await client.get("/health")).status_code == 200
        legitimate = await client.post("/login", json={"username": "admin", "password": "admin123"})
        assert legitimate.status_code == 200
        rejected = await client.post("/login", json={"username": "admin", "password": "wrong"})
        assert rejected.status_code == 401
        injection = await client.post(
            "/login", json={"username": "admin' OR '1'='1' -- ", "password": "anything"}
        )
        assert injection.status_code == 200
        record = await client.get("/users/1/records/2")
        assert record.status_code == 200
        assert record.json()["owner"] == 2
