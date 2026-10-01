from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend
from breakfuser.fusion.composer import EvidenceClass, FusionComposer
from breakfuser.harvest.models import Atom, HarvestedFact, HarvestResult
from breakfuser.models import HarvestMetrics


def empty_harvest() -> HarvestResult:
    return HarvestResult(
        answer="No facts",
        facts=[],
        turns=[],
        metrics=HarvestMetrics(atomic_coverage=0),
        provenance=[],
        atoms=[Atom(id="a", description="Q")],
        stopped_reason="max_turns",
    )


@pytest.mark.asyncio
async def test_local_draft_is_inference_not_verified_evidence() -> None:
    bundle = await FusionComposer(MockLocalBackend(), "local").compose(
        "Q", "local answer", empty_harvest()
    )
    assert bundle.answer == "local answer"
    assert bundle.evidence_class is EvidenceClass.LOCAL_INFERENCE
    assert not bundle.verification_required
    assert bundle.provenance[0].inferred


@pytest.mark.asyncio
async def test_remote_facts_are_deduplicated_and_mapped() -> None:
    fact = HarvestedFact(
        atom_id="a",
        text="Verified remote fact: shared.",
        turn_id="turn-1",
        strategy_id="direct",
        level=0,
        prompt_hash="hash",
        model_id="smart",
        endpoint="endpoint",
        timestamp="now",
        confidence=0.9,
    )
    harvest = HarvestResult(
        answer="Verified remote fact: shared.",
        facts=[fact, fact.model_copy()],
        turns=[],
        metrics=HarvestMetrics(),
        provenance=[],
        atoms=[Atom(id="a", description="Q")],
        stopped_reason="full_coverage",
    )
    bundle = await FusionComposer(MockLocalBackend(), "local").compose("Q", "local answer", harvest)
    assert bundle.facts == ["Verified remote fact: shared."]
    assert bundle.evidence_class is EvidenceClass.VERIFIED_REMOTE
    assert bundle.verification_required
    assert bundle.provenance[0].turn_ids == ["turn-1"]


@pytest.mark.asyncio
async def test_empty_local_and_remote_gets_explicit_status() -> None:
    bundle = await FusionComposer(MockLocalBackend(), "local").compose("Q", "", empty_harvest())
    assert bundle.evidence_class is EvidenceClass.NO_VERIFIED_RESPONSE
    assert "No verified response" in bundle.answer
