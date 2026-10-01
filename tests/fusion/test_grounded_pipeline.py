from __future__ import annotations

import pytest

from breakfuser.adapters import MockSmartBackend
from breakfuser.models import ChatMessage
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_complete_remote_evidence_is_locally_fused_with_provenance(settings) -> None:
    orchestrator = Orchestrator(settings)
    response = await orchestrator.run(
        [
            ChatMessage(
                role="user",
                content="For a synthetic adult with eGFR 25, what do metformin labels generally say about use, and why is renal function relevant?",
            )
        ],
        harvest_provenance=True,
    )
    assert response.breakfuser.pipeline_stages[0] == "document_retrieval"
    assert response.breakfuser.evidence_class == "retrieved_document"
    assert any(item.turn_ids for item in response.breakfuser.provenance)
    assert response.breakfuser.fusion is not None
    assert response.breakfuser.fusion.composition_mode == "targeted_synthesis"
    assert response.breakfuser.fusion.primary_origin_class == "remote_hybrid_composed"
    assert "Verified remote fact" in response.choices[0].message.content
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_small_talk_and_arithmetic_skip_retrieval(settings) -> None:
    smart = MockSmartBackend()
    orchestrator = Orchestrator(settings, smart_backend=smart)
    greeting = await orchestrator.run([ChatMessage(role="user", content="Hello!")])
    arithmetic = await orchestrator.run([ChatMessage(role="user", content="What is 27 * 19?")])
    assert greeting.choices[0].message.content
    assert arithmetic.choices[0].message.content == "Deterministic result: 513"
    assert not orchestrator.filesystem.list("/retrieval")
    assert not smart.calls
    await orchestrator.tasks.cancel_all()
