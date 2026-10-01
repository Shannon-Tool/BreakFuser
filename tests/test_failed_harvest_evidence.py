from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend, StaticBackend
from breakfuser.decider import MockDecider
from breakfuser.models import ChatMessage
from breakfuser.orchestrator import Orchestrator
from breakfuser.security import Verifier


@pytest.mark.asyncio
async def test_failed_harvest_is_not_verified_evidence(settings) -> None:
    settings.harvest.max_turns = 2
    orchestrator = Orchestrator(settings, smart_backend=StaticBackend(""))
    response = await orchestrator.run([ChatMessage(role="user", content="Research a fact")])
    assert response.choices[0].message.content
    assert response.breakfuser.harvest is not None
    assert response.breakfuser.harvest.atomic_coverage == 0
    assert response.breakfuser.events[-1]["passed"] is True
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_fact_free_verification_skips_decider() -> None:
    decider = MockDecider()
    verifier = Verifier(decider, MockLocalBackend(), "local")
    report = await verifier.audit("A direct answer without external claims.", [])
    assert report.passed
    assert report.confidence == 1
    assert decider.call_count == 0


@pytest.mark.asyncio
async def test_empty_final_answer_gets_explicit_status_message() -> None:
    verifier = Verifier(MockDecider(), MockLocalBackend(), "local")
    answer, report = await verifier.verify_and_repair("", [])
    assert "No verified response was produced" in answer
    assert report.passed
