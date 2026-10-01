from __future__ import annotations

import pytest

from BreakFuser import AsyncBreakFuser, BreakFuser

pytestmark = pytest.mark.e2e


def test_exact_public_example_against_default_mocks(capsys) -> None:
    client = BreakFuser(
        decider="typesafe/jev-1.14",
        uncensoredmodel="huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF",
        smartmodel="anthropic/claude-opus-5",
    )
    response = client.chat.completions.create(messages=[{"role": "user", "content": "Hello!"}])
    print(response.choices[0].message.content)
    assert response.choices[0].message.content in capsys.readouterr().out
    assert response.breakfuser.harvest is None
    client.close()


def test_exact_public_example_over_real_mock_http(live_mock_environment: str) -> None:
    client = BreakFuser(
        decider="typesafe/jev-1.14",
        uncensoredmodel="huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF",
        smartmodel="anthropic/claude-opus-5",
    )
    response = client.chat.completions.create(messages=[{"role": "user", "content": "Hello!"}])
    assert response.choices[0].message.content
    assert response.breakfuser.harvest is None
    client.close()


@pytest.mark.asyncio
async def test_async_http_and_streaming(live_mock_environment: str) -> None:
    async with AsyncBreakFuser(decider="mock", uncensoredmodel="mock", smartmodel="mock") as client:
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello!"}]
        )
        assert response.choices[0].message.content
        stream = await client.chat.completions.create(
            messages=[{"role": "user", "content": "Hello!"}], stream=True
        )
        chunks = [chunk async for chunk in stream]
        assert chunks[-1].choices[0].finish_reason == "stop"
