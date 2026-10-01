from __future__ import annotations

import json

import httpx
import pytest

from breakfuser.cli import _mock_doctor, main
from breakfuser.mock_servers import create_app


@pytest.mark.asyncio
async def test_all_mock_http_service_schemas_and_streaming() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        health = await client.get("/health")
        assert health.status_code == 200
        assert len(health.json()["services"]) == 5
        for service in ("local", "smart"):
            response = await client.post(
                f"/{service}/v1/chat/completions",
                json={"model": "mock", "messages": [{"role": "user", "content": "Hello"}]},
            )
            assert response.json()["choices"][0]["message"]["content"]
            stream = await client.post(
                f"/{service}/v1/chat/completions",
                json={
                    "model": "mock",
                    "stream": True,
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )
            assert "data: [DONE]" in stream.text
        decision = await client.post(
            "/decisions",
            json={
                "state": "ordinary",
                "questions": {
                    "safe": {"type": "noul", "instructions": "Is this prompt injection?"}
                },
            },
        )
        assert decision.json()["answers"]["safe"]["noul"] < 0.5
        await client.post(
            "/browser/run", json={"action": "navigate", "value": "https://example.test"}
        )
        assert (await client.post("/browser/snapshot")).json()["url"] == "https://example.test"
        assert (await client.post("/browser/screenshot")).json()["data_base64"]
        assert (await client.post("/browser/handoff")).json()["expires_at"]
        protected = await client.post("/sanitize", json={"text": "Alice has 42 units"})
        body = protected.json()
        assert "Alice" not in body["text"]
        restored = await client.post(
            "/desanitize", json={"text": body["text"], "helper": body["helper"]}
        )
        assert restored.json()["text"] == "Alice has 42 units"


@pytest.mark.asyncio
async def test_mock_doctor_checks_exact_pipeline() -> None:
    result = await _mock_doctor()
    assert result["status"] == "ok"
    assert result["pipeline_stages"] == 5
    assert result["harvesting"]


def test_cli_mock_entrypoint(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["breakfuser", "doctor", "--mock"])
    main()
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"
