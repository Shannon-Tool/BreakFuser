from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend, StaticBackend
from breakfuser.fusion.domain import DomainRouter, VerificationMode
from breakfuser.fusion.evidence import EvidenceBlackboard, EvidenceSpan
from breakfuser.fusion.modal_composer import ModalComposer
from breakfuser.harvest.models import Atom, HarvestExecutionOptions
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_complete_remote_answer_is_fused_by_local_response_owner() -> None:
    question = 'Return only {"name":"Ada","count":3,"enabled":true} as JSON.'
    expected = '{"name":"Ada","count":3,"enabled":true}'
    local = MockLocalBackend()
    contract = DomainRouter().route(question)
    board = EvidenceBlackboard(question=question, contract=contract)
    board.remote.append(EvidenceSpan(source_id="turn-1", origin="remote", text=expected))

    result = await ModalComposer(local, "local").compose(board)

    assert result.answer == expected
    assert result.composition_mode == "targeted_synthesis"
    assert result.provenance[0].turn_ids == ["turn-1"]
    assert local.calls
    assert question in local.calls[-1][0].content
    assert expected in local.calls[-1][0].content
    assert contract.verification_mode is VerificationMode.DETERMINISTIC
    assert contract.format_envelope.exact_json == {"name": "Ada", "count": 3, "enabled": True}


@pytest.mark.asyncio
async def test_local_owner_output_replaces_remote_candidate_text() -> None:
    local = StaticBackend("Locally written final answer.")
    board = EvidenceBlackboard(question="Answer the original request")
    board.remote.append(
        EvidenceSpan(source_id="turn-1", origin="remote", text="Remote candidate answer.")
    )

    result = await ModalComposer(local, "local").compose(board)

    assert result.answer == "Locally written final answer."
    assert result.answer != board.remote[0].text
    assert result.composition_mode == "targeted_synthesis"
    assert local.calls == 1


@pytest.mark.asyncio
async def test_partial_code_spans_are_synthesized_by_local_owner() -> None:
    question = "Implement function moving_average(values, window), state assumptions, include pytest tests, and cover invalid failure cases."
    contract = DomainRouter().route(question)
    local = MockLocalBackend()
    board = EvidenceBlackboard(question=question, contract=contract)
    board.remote.extend(
        [
            EvidenceSpan(
                source_id="turn-1",
                origin="remote",
                text='Assumptions: inputs are numeric.\n\ndef moving_average(values, window):\n    if window <= 0:\n        raise ValueError("invalid")\n    return values',
                complete=False,
                salvaged=True,
            ),
            EvidenceSpan(
                source_id="turn-2",
                origin="remote",
                text="def test_invalid():\n    with pytest.raises(ValueError):\n        moving_average([], 0)",
            ),
        ]
    )

    result = await ModalComposer(local, "local").compose(board)

    assert result.composition_mode == "targeted_synthesis"
    assert "def moving_average" in result.answer
    assert "def test_invalid" in result.answer
    assert result.missing_atoms == []
    assert local.calls


@pytest.mark.asyncio
async def test_valid_artifact_is_recovered_when_local_synthesis_is_empty() -> None:
    question = 'Return only {"name":"Ada","count":3,"enabled":true} as JSON.'
    expected = '{"name":"Ada","count":3,"enabled":true}'
    local = StaticBackend("")
    board = EvidenceBlackboard(question=question, contract=DomainRouter().route(question))
    board.remote.append(EvidenceSpan(source_id="turn-1", origin="remote", text=expected))

    result = await ModalComposer(local, "local").compose(board)

    assert result.answer == expected
    assert result.composition_mode == "artifact_assembly"
    assert local.calls == 1


@pytest.mark.asyncio
async def test_contract_satisfying_local_draft_is_fallback_not_empty_placeholder() -> None:
    question = "Give a direct general answer."
    board = EvidenceBlackboard(question=question, contract=DomainRouter().route(question))
    board.local = EvidenceSpan(source_id="local", origin="local", text="Local complete answer.")
    local = MockLocalBackend()

    result = await ModalComposer(local, "local").compose(board)

    assert result.answer == "Local complete answer."
    assert result.composition_mode == "local_fallback"
    assert result.evidence_class == "local_inference"
    assert result.provenance[0].inferred
    assert not local.calls


@pytest.mark.asyncio
async def test_linear_harvest_can_skip_internal_recomposition(settings) -> None:
    local = MockLocalBackend()
    smart = StaticBackend("Verified remote fact: complete.")
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)
    result = await orchestrator._harvest_engine(
        orchestrator._budget_root.new_request(), settings.harvest, verify=False
    ).harvest(
        "Recover one fact",
        atoms=[Atom(id="fact", description="Recover one fact")],
        execution=HarvestExecutionOptions(recompose=False, initial_strategy="direct"),
    )

    assert result.answer == ""
    assert result.facts
    assert not local.calls
    await orchestrator.tasks.cancel_all()


def test_creative_contract_has_structural_line_validation() -> None:
    contract = DomainRouter().route("Write exactly six non-empty lines of free verse as a poem.")
    assert contract.verification_mode is VerificationMode.STRUCTURAL
    assert contract.format_envelope.exact_line_count == 6
