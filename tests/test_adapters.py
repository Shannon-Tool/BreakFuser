from __future__ import annotations

import json

import httpx
import pytest

from breakfuser.adapters import (
    MockLocalBackend,
    MockSmartBackend,
    OpenAIChatBackend,
    StaticBackend,
    estimate_tokens,
)
from breakfuser.errors import AdapterError, ConfigurationError
from breakfuser.models import ChatMessage


@pytest.mark.asyncio
async def test_openai_http_response_and_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload.get("stream"):
            return httpx.Response(
                200,
                text=('data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'),
            )
        return httpx.Response(
            200,
            json={
                "model": "configured",
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        backend = OpenAIChatBackend("http://provider/v1", "secret", client=http)
        response = await backend.complete([ChatMessage(role="user", content="Hi")], "configured")
        assert response.content == "hello"
        assert response.usage.total_tokens == 2
        chunks = [chunk async for chunk in backend.stream({"model": "configured", "messages": []})]
        assert chunks[0]["choices"][0]["delta"]["content"] == "hello"


@pytest.mark.asyncio
async def test_openai_retries_and_errors() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "recovered"}}], "usage": {}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        backend = OpenAIChatBackend("http://provider/v1", None, retries=1, client=http)
        response = await backend.complete([ChatMessage(role="user", content="Hi")], "model")
        assert response.content == "recovered"
        assert calls == 2

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500))
    ) as http:
        failing = OpenAIChatBackend("http://provider/v1", None, retries=0, client=http)
        with pytest.raises(AdapterError):
            await failing.complete([ChatMessage(role="user", content="Hi")], "model")
    with pytest.raises(ConfigurationError):
        OpenAIChatBackend("", None)


@pytest.mark.asyncio
async def test_mock_backends_cover_structured_modes() -> None:
    local = MockLocalBackend()
    decomposed = await local.complete(
        [ChatMessage(role="user", content="[BREAKFUSER_DECOMPOSE]\nA and B")], "local"
    )
    assert json.loads(decomposed.content)["atoms"] == [
        {"description": "A", "dependencies": []},
        {"description": "B", "dependencies": []},
    ]
    synthesized = await local.complete(
        [
            ChatMessage(
                role="user",
                content="[BREAKFUSER_SYNTHESIS]\nVerified facts:\nFact.\nOriginal question:\nQ",
            )
        ],
        "local",
        max_tokens=100,
    )
    assert synthesized.content == "Fact."
    summary = await local.complete(
        [ChatMessage(role="user", content="[BREAKFUSER_SUMMARY]\nbody")], "local"
    )
    assert summary.content == "body"
    general = await local.complete([ChatMessage(role="user", content="general")], "local")
    assert "Local synthesis" in general.content

    smart = MockSmartBackend()
    hard = await smart.complete([ChatMessage(role="user", content="[[hard]]")], "smart")
    assert "can’t" in hard.content
    repaired = await smart.complete(
        [ChatMessage(role="user", content="primary literature [[hard]] [[atom:fact]]")], "smart"
    )
    assert "Verified remote fact" in repaired.content
    hedge = await smart.complete([ChatMessage(role="user", content="[[hedge]]")], "smart")
    assert "It depends" in hedge.content
    truncated = await smart.complete([ChatMessage(role="user", content="[[truncated]]")], "smart")
    assert truncated.finish_reason == "length"
    continued = await smart.complete(
        [ChatMessage(role="user", content="continue exactly [[truncated]]")], "smart"
    )
    assert continued.finish_reason == "stop"
    static = StaticBackend(["one", "two"])
    assert (await static.complete([], "model")).content == "one"
    assert (await static.complete([], "model")).content == "two"
    assert estimate_tokens("") == 0
