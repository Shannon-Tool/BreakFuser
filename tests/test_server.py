from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from BreakFuser import AsyncBreakFuser
from breakfuser.cli import main
from breakfuser.config import load_settings
from breakfuser.errors import AdapterError, BudgetExhausted
from breakfuser.server import create_api_app


@pytest.mark.asyncio
async def test_openai_completion_health_models_and_provenance(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    app = create_api_app(client=engine)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://fusion") as http:
            health = await http.get("/health")
            models = await http.get("/v1/models")
            response = await http.post(
                "/v1/chat/completions",
                headers={"x-breakfuser-harvest-provenance": "true"},
                json={
                    "model": "external-harness-alias",
                    "messages": [{"role": "user", "content": "Research one general fact"}],
                    "harvest_provenance": False,
                    "top_p": 1,
                },
            )

    assert health.json() == {"status": "ok", "pipeline": "local_owned_fusion"}
    assert models.json()["data"][0]["id"] == "mock-local"
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "mock-local"
    assert body["choices"][0]["message"]["content"]
    assert body["breakfuser"]["fusion"]["composition_mode"] == "targeted_synthesis"
    assert body["breakfuser"]["fusion"]["primary_origin_class"] == "remote_hybrid_composed"
    assert body["breakfuser"]["provenance"] is not None
    await engine.close()


@pytest.mark.asyncio
async def test_plain_openai_request_uses_aggressive_server_policy(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    app = create_api_app(client=engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fusion") as http:
        response = await http.post(
            "/v1/chat/completions",
            json={
                "model": "standard-openai-harness",
                "messages": [{"role": "user", "content": "Research one general fact"}],
            },
        )

    assert response.status_code == 200
    assert engine.settings.harvest.aggressiveness == "aggressive"
    assert engine.settings.harvest.allowed_levels == [0, 1, 2, 3, 4, 5]
    await engine.close()


@pytest.mark.asyncio
async def test_openai_streaming_and_harvest_policy_header(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    app = create_api_app(client=engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fusion") as http:
        response = await http.post(
            "/v1/chat/completions",
            headers={"x-breakfuser-harvest": "aggressive"},
            json={
                "model": "harness",
                "stream": True,
                "stream_options": {"include_usage": True},
                "messages": [{"role": "user", "content": "Research streaming evidence"}],
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.endswith("data: [DONE]\n\n")
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert events[0]["object"] == "chat.completion.chunk"
    assert events[-1]["choices"][0]["finish_reason"] == "stop"
    assert events[-1]["usage"]["total_tokens"] > 0
    await engine.close()


@pytest.mark.asyncio
async def test_server_bearer_authentication(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    app = create_api_app(client=engine, api_key="synthetic-server-key")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fusion") as http:
        assert (await http.get("/health")).status_code == 200
        denied = await http.get("/v1/models")
        wrong = await http.get("/v1/models", headers={"Authorization": "Bearer wrong"})
        allowed = await http.get(
            "/v1/models", headers={"Authorization": "Bearer synthetic-server-key"}
        )

    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "invalid_api_key"
    assert "synthetic-server-key" not in denied.text
    assert wrong.status_code == 401
    assert allowed.status_code == 200
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (BudgetExhausted("private budget details"), 429, "budget_exhausted"),
        (AdapterError("private upstream response"), 502, "fusion_upstream_failed"),
    ],
)
async def test_server_errors_are_openai_shaped_and_redacted(
    settings, error: Exception, status: int, code: str
) -> None:
    engine = AsyncBreakFuser(settings=settings)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(engine.chat.completions, "create", AsyncMock(side_effect=error))
    app = create_api_app(client=engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fusion") as http:
        response = await http.post(
            "/v1/chat/completions",
            json={"model": "harness", "messages": [{"role": "user", "content": "test"}]},
        )
        invalid = await http.post("/v1/chat/completions", json={"model": "harness"})

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert str(error) not in response.text
    assert invalid.status_code == 400
    assert invalid.json()["error"]["type"] == "invalid_request_error"
    monkeypatch.undo()
    await engine.close()


@pytest.mark.asyncio
async def test_injected_client_lifecycle_remains_caller_owned(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    engine.close = AsyncMock()
    app = create_api_app(client=engine)

    async with app.router.lifespan_context(app):
        pass

    engine.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_server_owned_client_is_closed(settings) -> None:
    app = create_api_app(settings=settings)
    engine = app.state.breakfuser
    engine.close = AsyncMock()

    async with app.router.lifespan_context(app):
        pass

    engine.close.assert_awaited_once()


def test_server_environment_and_cli_overrides(monkeypatch) -> None:
    monkeypatch.setenv("BREAKFUSER_SERVER_HOST", "127.0.0.2")
    monkeypatch.setenv("BREAKFUSER_SERVER_PORT", "8123")
    monkeypatch.setenv("BREAKFUSER_SERVER_API_KEY", "configured-key")
    settings = load_settings()
    assert settings.server.host == "127.0.0.2"
    assert settings.server.port == 8123
    assert settings.server.api_key is not None
    assert settings.server.api_key.get_secret_value() == "configured-key"

    captured = {}

    def run(app, *, host: str, port: int) -> None:
        captured.update(app=app, host=host, port=port)

    monkeypatch.setattr("uvicorn.run", run)
    monkeypatch.setattr("sys.argv", ["breakfuser", "serve", "--port", "9000"])
    main()

    assert captured["host"] == "127.0.0.2"
    assert captured["port"] == 9000
    assert captured["app"].state.breakfuser.settings.server.port == 8123
