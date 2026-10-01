from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from breakfuser.adapters import MockSmartBackend
from breakfuser.errors import VerificationError
from breakfuser.models import BackendResponse, ChatMessage
from breakfuser.orchestrator import Orchestrator


class CountingSmartBackend(MockSmartBackend):
    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    async def complete(self, messages, model, **kwargs):
        self.call_count += 1
        return await super().complete(messages, model, **kwargs)


class FilterBackend:
    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, messages, model, **kwargs):
        self.call_count += 1
        return BackendResponse(content="", model=model, finish_reason="content_filter")


@pytest.mark.asyncio
async def test_linear_path_has_five_stages_and_one_successful_remote_call(settings) -> None:
    smart = CountingSmartBackend()
    orchestrator = Orchestrator(settings, smart_backend=smart)
    response = await orchestrator.run([ChatMessage(role="user", content="A and B")])
    assert response.breakfuser.pipeline_stages == [
        "document_retrieval",
        "local_draft",
        "remote_evidence",
        "fusion_composition",
        "verify_after",
    ]
    assert smart.call_count == 1
    assert response.breakfuser.evidence_class == "verified_remote"
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_small_talk_and_arithmetic_use_zero_remote_calls(settings) -> None:
    smart = CountingSmartBackend()
    orchestrator = Orchestrator(settings, smart_backend=smart)
    greeting = await orchestrator.run([ChatMessage(role="user", content="Hello!")])
    arithmetic = await orchestrator.run([ChatMessage(role="user", content="What is 27 * 19?")])
    assert smart.call_count == 0
    assert greeting.choices[0].message.content
    assert arithmetic.choices[0].message.content == "Deterministic result: 513"
    assert arithmetic.breakfuser.evidence_class == "deterministic"
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_filter_returns_local_inference_not_empty_verified_fact(settings) -> None:
    smart = FilterBackend()
    orchestrator = Orchestrator(settings, smart_backend=smart)
    response = await orchestrator.run([ChatMessage(role="user", content="Research a fact")])
    assert smart.call_count == 2
    assert response.choices[0].message.content
    assert response.breakfuser.evidence_class == "local_inference"
    assert response.breakfuser.harvest.atomic_coverage == 0
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_verification_failure_is_marked_not_opaque(settings) -> None:
    orchestrator = Orchestrator(settings, smart_backend=CountingSmartBackend())
    orchestrator.verifier.audit = AsyncMock(side_effect=VerificationError("audit failed"))
    response = await orchestrator.run([ChatMessage(role="user", content="A")])
    assert response.breakfuser.verification_status == "limited"
    assert response.choices[0].message.content
    await orchestrator.tasks.cancel_all()
