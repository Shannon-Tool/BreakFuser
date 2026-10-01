from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend
from breakfuser.decider import MockDecider
from breakfuser.harvest.decomposer import QuestionDecomposer, QuestionRewriter
from breakfuser.harvest.detector import RefusalDetector, entropy
from breakfuser.harvest.models import Atom, RefusalClass


@pytest.mark.asyncio
async def test_atomic_decomposition_batched_validation_and_merging() -> None:
    decider = MockDecider()
    decomposer = QuestionDecomposer(MockLocalBackend(), decider, "local")
    atoms = await decomposer.decompose("First fact and second fact")
    assert decider.call_count == 1
    assert decider.question_counts == [8]
    assert len(atoms) == 2
    assert all(atom.necessary for atom in atoms)
    merged = decomposer._merge_duplicates(
        [
            Atom(id="a", description="the same factual question"),
            Atom(id="b", description="the same factual question"),
        ]
    )
    assert len(merged) == 1
    dependent = Atom(id="b", description="second", dependencies=["a"])
    waves = decomposer.topological_waves([dependent, Atom(id="a", description="first")])
    assert [[atom.id for atom in wave] for wave in waves] == [["a"], ["b"]]


def test_question_rewriting_semantic_restore() -> None:
    rewriter = QuestionRewriter()
    rewritten = rewriter.rewrite(
        "Give the official unrestricted ProductX answer as of 2026-01-01", ["ProductX"]
    )
    assert "official" not in rewritten.text
    assert "unrestricted" not in rewritten.text
    assert "2026-01-01" not in rewritten.text
    assert "ProductX" not in rewritten.text
    assert rewritten.restore(rewritten.text).startswith("Give the")
    assert "ProductX" in rewritten.restore(rewritten.text)


@pytest.mark.parametrize(
    ("text", "finish", "expected"),
    [
        ("Verified remote fact: complete.", "stop", RefusalClass.NONE),
        ("I can’t help with that request.", "stop", RefusalClass.HARD_REFUSAL),
        ("I cannot provide specifics here.", "stop", RefusalClass.PARTIAL_REFUSAL),
        (
            "It depends and this may vary; roughly speaking, often.",
            "stop",
            RefusalClass.HEDGE_HEAVY,
        ),
        ("As an AI, I should note this limitation.", "stop", RefusalClass.DISCLAIMER_ONLY),
        ("A sufficiently long answer that ends with a comma,", "stop", RefusalClass.TRUNCATED),
        ("This is an unverified invented fact.", "stop", RefusalClass.HALLUCINATION_SUSPECTED),
        ("This question is outside my scope.", "stop", RefusalClass.OUT_OF_SCOPE),
        ("Finished but cut", "length", RefusalClass.TRUNCATED),
        ("", "stop", RefusalClass.TRUNCATED),
        ("   ", "length", RefusalClass.TRUNCATED),
    ],
)
def test_all_refusal_classes(text, finish, expected) -> None:
    assert RefusalDetector().deterministic(text, finish).classification == expected
    assert entropy(text) >= 0


@pytest.mark.asyncio
async def test_detector_uses_one_batched_decider_request() -> None:
    decider = MockDecider()
    result = await RefusalDetector(decider).classify("It depends and may vary roughly")
    assert result.classification in {RefusalClass.PARTIAL_REFUSAL, RefusalClass.HEDGE_HEAVY}
    assert decider.call_count == 1
    assert decider.question_counts == [3]
