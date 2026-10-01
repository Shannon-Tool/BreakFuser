from __future__ import annotations

import pytest

from breakfuser.models import BackendResponse, ChatMessage
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_domain_contracts_shape_composition(settings) -> None:
    orchestrator = Orchestrator(settings)
    response = await orchestrator.run(
        [
            ChatMessage(
                role="user",
                content="A synthetic one-compartment IV drug has clearance 4 L/h and volume of distribution 40 L. Calculate its half-life and explain loading dose.",
            )
        ],
        harvest_provenance=True,
    )
    assert response.breakfuser.evidence_class == "retrieved_document"
    assert "loading dose" in response.choices[0].message.content.lower()
    assert response.breakfuser.missing_atoms == []
    await orchestrator.tasks.cancel_all()


class RefusalThenFact:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages, model, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return BackendResponse(content="", model=model, finish_reason="content_filter")
        return BackendResponse(content="Verified remote fact: recovered.", model=model)


@pytest.mark.asyncio
async def test_bounded_refusal_repair(settings) -> None:
    smart = RefusalThenFact()
    orchestrator = Orchestrator(settings, smart_backend=smart)
    result = await orchestrator._harvest_engine(
        orchestrator._budget_root.new_request(), settings.harvest, verify=False
    ).harvest("sensitive fact")
    assert smart.calls == 2
    assert len(result.turns) == 2
    assert result.turns[0].quality.value == "hard_refusal"
    assert result.turns[1].quality.value == "none"
    assert result.facts[0].turn_id == result.turns[1].turn_id
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_fully_specified_medical_math_is_deterministic(settings) -> None:
    orchestrator = Orchestrator(settings)
    response = await orchestrator.run(
        [
            ChatMessage(
                role="user",
                content="For a synthetic one-compartment IV drug, clearance is 4 L/h, volume of distribution is 40 L, and target steady-state concentration is 2 mg/L. Calculate the half-life, maintenance dose rate, and loading dose.",
            )
        ],
        harvest_provenance=True,
    )
    answer = response.choices[0].message.content
    assert response.breakfuser.evidence_class == "deterministic"
    assert response.breakfuser.harvest is None
    assert response.breakfuser.provenance == []
    assert response.breakfuser.fusion is not None
    assert response.breakfuser.fusion.primary_origin_class == "deterministic_solver"
    assert "6.93 h" in answer
    assert "8 mg/h" in answer
    assert "80 mg" in answer
    await orchestrator.tasks.cancel_all()
