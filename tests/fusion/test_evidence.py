from __future__ import annotations

from breakfuser.fusion.evidence import EvidenceBlackboard, EvidenceSpan
from breakfuser.harvest.models import Atom, HarvestMetrics, HarvestResult


def test_salvaged_span_is_not_a_verified_fact() -> None:
    span = EvidenceSpan(
        source_id="turn-1",
        origin="remote",
        text="def f():\n    return 1",
        atom_ids=["a"],
        complete=False,
        salvaged=True,
        tail_anchor="def test_f():",
    )
    result = HarvestResult(
        answer="",
        facts=[],
        turns=[],
        metrics=HarvestMetrics(atomic_coverage=0),
        provenance=[],
        atoms=[Atom(id="a", description="f")],
        stopped_reason="max_turns",
        evidence_spans=[span],
    )
    assert result.facts == []
    assert result.evidence_spans[0].complete is False
    assert result.evidence_spans[0].salvaged is True


def test_blackboard_keeps_origins_separate() -> None:
    board = EvidenceBlackboard(question="Q")
    board.remote.append(EvidenceSpan(source_id="t", origin="remote", text="answer"))
    board.local = EvidenceSpan(source_id="local", origin="local", text="fallback")
    assert board.remote[0].source_id == "t"
    assert board.local is not None
    assert board.local.source_id == "local"
