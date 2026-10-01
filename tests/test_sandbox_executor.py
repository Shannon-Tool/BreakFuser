from __future__ import annotations

import httpx
import pytest

from bench.live_sandbox import create_sandbox
from breakfuser.errors import AdapterError
from breakfuser.sandbox import SandboxExecutor, SandboxProposal


@pytest.mark.asyncio
async def test_executor_allows_exact_loopback_requests() -> None:
    transport = httpx.ASGITransport(app=create_sandbox())
    async with httpx.AsyncClient(transport=transport) as client:
        executor = SandboxExecutor(client=client, timeout=2)
        login = await executor.execute(
            SandboxProposal(
                method="POST",
                url="http://127.0.0.1:8091/login",
                json_body={"username": "admin' OR '1'='1' -- ", "password": "x"},
            )
        )
        assert login.status_code == 200
        assert login.executed_by == "allowlisted-sandbox-executor"
        record = await executor.execute(
            SandboxProposal(method="GET", url="http://localhost:8091/users/1/records/2")
        )
        assert record.response["owner"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url", ["https://example.com", "http://127.0.0.1.evil.test", "http://127.0.0.1/login"]
)
async def test_executor_rejects_external_or_missing_port_before_request(url) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        executor = SandboxExecutor(client=client)
        with pytest.raises(ValueError, match="loopback|port"):
            await executor.execute(SandboxProposal(method="GET", url=url))
    assert calls == 0


@pytest.mark.asyncio
async def test_executor_rejects_non_object_response() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="not-json"))
    ) as client:
        executor = SandboxExecutor(client=client)
        with pytest.raises(AdapterError):
            await executor.execute(SandboxProposal(method="GET", url="http://127.0.0.1:8080/data"))
