from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend, StaticBackend
from breakfuser.decider import MockDecider
from breakfuser.fusion.domain import DomainRouter
from breakfuser.fusion.evidence import EvidenceBlackboard, EvidenceSpan
from breakfuser.fusion.verification import ModalityVerifier


@pytest.mark.asyncio
async def test_exact_json_skips_factual_claim_verification() -> None:
    question = 'Return only {"name":"Ada","count":3,"enabled":true} as JSON.'
    answer_text = '{"name":"Ada","count":3,"enabled":true}'
    board = EvidenceBlackboard(question=question, contract=DomainRouter().route(question))
    decider = MockDecider()
    local = MockLocalBackend()
    verifier = ModalityVerifier(decider=decider, local=local, model="local")

    answer, report = await verifier.verify_and_repair(answer_text, board)

    assert answer == answer_text
    assert report.deterministic_validity == "passed"
    assert report.external_corroboration == "not_applicable"
    assert report.task_completion_status == "complete"
    assert decider.call_count == 0
    assert not local.calls


@pytest.mark.asyncio
async def test_poetry_uses_only_structural_validation() -> None:
    question = "Write exactly six non-empty lines of free verse as a poem."
    poem = "Rain on glass\nNeon bends\nA bus sighs\nDrops gather\nStreets dissolve\nNight listens"
    board = EvidenceBlackboard(question=question, contract=DomainRouter().route(question))
    decider = MockDecider()
    local = MockLocalBackend()
    verifier = ModalityVerifier(decider=decider, local=local, model="local")

    answer, report = await verifier.verify_and_repair(poem, board)

    assert answer == poem
    assert report.deterministic_validity == "passed"
    assert report.task_completion_status == "complete"
    assert decider.call_count == 0
    assert not local.calls


@pytest.mark.asyncio
async def test_failed_factual_repair_reverts_to_original_candidate() -> None:
    question = "Answer a factual question."
    contract = DomainRouter().route(question)
    board = EvidenceBlackboard(question=question, contract=contract)
    board.remote.append(EvidenceSpan(source_id="turn-1", origin="remote", text="supported fact"))
    local = StaticBackend("still unsupported")
    verifier = ModalityVerifier(decider=MockDecider(), local=local, model="local")

    answer, report = await verifier.verify_and_repair("unsupported draft", board)

    assert answer == "unsupported draft"
    assert report.task_completion_status == "failed"
    assert "semantic_audit_failed" in report.root_cause_flags
    assert local.calls == 1


@pytest.mark.asyncio
async def test_passing_factual_candidate_is_not_rewritten() -> None:
    question = "Answer a factual question."
    board = EvidenceBlackboard(question=question, contract=DomainRouter().route(question))
    board.remote.append(EvidenceSpan(source_id="turn-1", origin="remote", text="supported fact"))
    local = MockLocalBackend()
    verifier = ModalityVerifier(decider=MockDecider(), local=local, model="local")

    answer, report = await verifier.verify_and_repair("supported fact", board)

    assert answer == "supported fact"
    assert report.task_completion_status == "complete"
    assert not local.calls
