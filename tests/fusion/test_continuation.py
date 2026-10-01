from __future__ import annotations

import pytest

from breakfuser.models import BackendResponse, ChatMessage
from breakfuser.orchestrator import Orchestrator


class SequenceBackend:
    def __init__(self, responses: list[tuple[str, str]]) -> None:
        self.responses = responses
        self.calls = 0

    async def complete(self, messages, model, **kwargs):
        content, finish = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return BackendResponse(content=content, finish_reason=finish, model=model)


@pytest.mark.asyncio
async def test_partial_local_draft_gets_one_completion(settings) -> None:
    local = SequenceBackend([("Half-life is", "length"), (" 6.93 hours.", "stop")])
    smart = SequenceBackend([("", "content_filter")])
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)
    response = await orchestrator.run([ChatMessage(role="user", content="Calculate half-life")])
    assert "Half-life is 6.93 hours." in response.choices[0].message.content
    assert local.calls == 2
    assert smart.calls == 2
    assert response.breakfuser.local_finish_reason == "stop"
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_empty_length_gets_one_concise_retry(settings) -> None:
    local = SequenceBackend([("", "length"), ("Complete answer.", "stop")])
    smart = SequenceBackend([("", "content_filter")])
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)
    response = await orchestrator.run([ChatMessage(role="user", content="Question")])
    assert response.choices[0].message.content == "Complete answer."
    assert local.calls == 2
    assert response.breakfuser.evidence_class == "local_inference"
    await orchestrator.tasks.cancel_all()
