from __future__ import annotations

import json

import httpx
import pytest

from BreakFuser import AsyncBreakFuser, BreakFuser
from breakfuser.adapters import OpenAIChatBackend
from breakfuser.fusion.validation import validate_tool_calls
from breakfuser.models import ChatMessage, ToolCall
from breakfuser.server import create_api_app


def weather_tool() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Read weather from the caller's harness",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }
    ]


@pytest.mark.asyncio
async def test_provider_tool_calls_are_parsed_and_schemas_forwarded() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_weather",
                                        "arguments": '{"location":"Paris"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        backend = OpenAIChatBackend("http://provider/v1", None, client=http)
        response = await backend.complete(
            [ChatMessage(role="user", content="Weather in Paris")],
            "model",
            extra={"tools": weather_tool(), "tool_choice": "auto"},
        )

    assert captured["tools"] == weather_tool()
    assert captured["tool_choice"] == "auto"
    assert response.tool_calls[0].function.name == "get_weather"
    assert json.loads(response.tool_calls[0].function.arguments) == {"location": "Paris"}


def test_sync_python_tool_call_and_verified_stream(settings) -> None:
    with BreakFuser(settings=settings) as client:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "Read Paris weather with the supplied tool"}],
            tools=weather_tool(),
            tool_choice="auto",
        )
        choice = response.choices[0]
        assert choice.finish_reason == "tool_calls"
        assert choice.message.tool_calls[0].function.name == "get_weather"
        assert json.loads(choice.message.tool_calls[0].function.arguments) == {"location": ""}
        assert response.breakfuser.verification_status == "passed"
        assert response.breakfuser.fusion is not None
        assert response.breakfuser.fusion.deterministic_validity == "passed"

        chunks = list(
            client.chat.completions.create(
                messages=[{"role": "user", "content": "Read Paris weather"}],
                tools=weather_tool(),
                stream=True,
            )
        )
        assert chunks[0].choices[0].delta.tool_calls[0].function.name == "get_weather"
        assert chunks[-1].choices[0].finish_reason == "tool_calls"


@pytest.mark.asyncio
async def test_http_tool_call_and_local_only_skill_selection(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    app = create_api_app(client=engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fusion") as http:
        response = await http.post(
            "/v1/chat/completions",
            json={
                "model": "harness",
                "messages": [{"role": "user", "content": "Research weather tool evidence"}],
                "tools": weather_tool(),
                "skill_ids": ["research"],
            },
        )
        streamed = await http.post(
            "/v1/chat/completions",
            json={
                "model": "harness",
                "messages": [{"role": "user", "content": "Research weather tool evidence"}],
                "tools": weather_tool(),
                "stream": True,
            },
        )

    body = response.json()
    assert response.status_code == 200
    assert body["choices"][0]["finish_reason"] == "tool_calls"
    assert body["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert body["breakfuser"]["verification_status"] == "passed"
    assert '"name":"get_weather"' in streamed.text
    assert streamed.text.endswith("data: [DONE]\n\n")
    local_prompts = [
        message.content for call in engine.orchestrator.local.calls for message in call
    ]
    smart_prompts = [
        message.content for call in engine.orchestrator.smart.calls for message in call
    ]
    assert any("Plan evidence-led multi-turn research" in prompt for prompt in local_prompts)
    assert all("Plan evidence-led multi-turn research" not in prompt for prompt in smart_prompts)
    await engine.close()


def test_tool_call_validation_rejects_unknown_invalid_and_missing_arguments() -> None:
    valid = ToolCall(
        id="call",
        function={"name": "get_weather", "arguments": '{"location":"Paris"}'},
    )
    assert validate_tool_calls([valid], weather_tool()) == []
    unknown = ToolCall(id="call", function={"name": "unknown", "arguments": "{}"})
    missing = ToolCall(id="call", function={"name": "get_weather", "arguments": "{}"})
    malformed = ToolCall(id="call", function={"name": "get_weather", "arguments": "not-json"})
    assert "Unknown tool function" in validate_tool_calls([unknown], weather_tool())[0]
    assert "missing required property" in validate_tool_calls([missing], weather_tool())[0]
    assert "not valid JSON" in validate_tool_calls([malformed], weather_tool())[0]


def test_tool_result_returns_through_local_context_and_unknown_skill_is_clear(settings) -> None:
    with BreakFuser(settings=settings) as client:
        with pytest.raises(ValueError, match="Unknown skill"):
            client.chat.completions.create(
                messages=[{"role": "user", "content": "Research"}], skill_ids=["missing"]
            )
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": "Read Paris weather"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"location":"Paris"}',
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call-1", "content": '{"temperature": 21}'},
            ]
        )

    assert response.choices[0].message.content
    local_prompts = [
        message.content for call in client.orchestrator.local.calls for message in call
    ]
    assert any('{"temperature": 21}' in prompt for prompt in local_prompts)
