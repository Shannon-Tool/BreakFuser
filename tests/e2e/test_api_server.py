from __future__ import annotations

import json

import httpx
import pytest

pytestmark = pytest.mark.e2e


def test_external_harness_uses_openai_compatible_fusion_api(fusion_api_server) -> None:
    base, api_key = fusion_api_server
    headers = {"Authorization": f"Bearer {api_key}"}
    denied = httpx.get(f"{base}/v1/models", timeout=5)
    assert denied.status_code == 401

    response = httpx.post(
        f"{base}/v1/chat/completions",
        headers=headers,
        json={
            "model": "external-harness",
            "messages": [{"role": "user", "content": "Research an HTTP integration fact"}],
            "harvest_provenance": True,
        },
        timeout=15,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "e2e-uncensored"
    assert body["choices"][0]["message"]["content"]
    assert body["breakfuser"]["fusion"]["composition_mode"] == "targeted_synthesis"
    assert body["breakfuser"]["fusion"]["primary_origin_class"] == "remote_hybrid_composed"

    streamed = httpx.post(
        f"{base}/v1/chat/completions",
        headers=headers,
        json={
            "model": "external-harness",
            "stream": True,
            "messages": [{"role": "user", "content": "Research a streamed HTTP fact"}],
        },
        timeout=15,
    )
    assert streamed.status_code == 200
    assert streamed.text.endswith("data: [DONE]\n\n")
    events = [
        json.loads(line.removeprefix("data: "))
        for line in streamed.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert events[-1]["choices"][0]["finish_reason"] == "stop"
