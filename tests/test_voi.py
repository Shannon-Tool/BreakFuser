from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from breakfuser.calibration import IsotonicCalibrator
from breakfuser.config import VoISettings
from breakfuser.decider import MockDecider
from breakfuser.voi import (
    BeliefState,
    FollowUpQuestion,
    VoIDecision,
    VoIGate,
    best_utility,
    estimate_voi,
    expected_utility,
    marginal_likelihood,
)


def belief() -> BeliefState:
    return BeliefState(probabilities={"a": 0.5, "b": 0.5})


def question() -> FollowUpQuestion:
    return FollowUpQuestion(
        id="q",
        prompt="Which?",
        answers=["yes", "no"],
        likelihoods={"a": {"yes": 1, "no": 0}, "b": {"yes": 0, "no": 1}},
    )


def utility() -> dict[str, dict[str, float]]:
    return {"a": {"a": 1, "b": 0}, "b": {"a": 0, "b": 1}}


def test_exact_voi_math_and_boundaries() -> None:
    current = belief()
    assert best_utility(current, utility()) == 0.5
    assert expected_utility(current, "a", utility()) == 0.5
    assert marginal_likelihood(current, question(), "yes") == 0.5
    estimate = estimate_voi(current, question(), utility(), turn_cost=0.25)
    assert estimate.expected_utility == 1
    assert estimate.gross_voi == 0.5
    assert estimate.net_voi == 0.25
    posterior = current.posterior({"a": 1, "b": 0})
    assert posterior.probabilities == {"a": 1, "b": 0}
    with pytest.raises(ValueError):
        current.posterior({"a": 1})
    with pytest.raises(ValueError):
        BeliefState(probabilities={})


@pytest.mark.asyncio
async def test_clarify_commit_confidence_and_turn_limit() -> None:
    gate = VoIGate(MockDecider(), VoISettings(turn_cost=0.1, commit_confidence=0.99, max_turns=1))
    decision, estimates = await gate.decide(belief(), [question()], utility(), state="uncertain")
    assert decision == VoIDecision.CLARIFY
    assert estimates[0].net_voi > 0
    decision, _ = await gate.decide(belief(), [question()], utility(), state="uncertain", turn=1)
    assert decision == VoIDecision.COMMIT
    gate.settings.commit_confidence = 0.9
    decision, _ = await gate.decide(belief(), [question()], utility(), state="Verified remote fact")
    assert decision == VoIDecision.COMMIT
    gate.settings.turn_cost = 1
    gate.settings.commit_confidence = 1
    decision, _ = await gate.decide(belief(), [question()], utility(), state="uncertain")
    assert decision == VoIDecision.COMMIT

    calibrated = VoIGate(
        MockDecider(),
        VoISettings(turn_cost=0.1, commit_confidence=0.9),
        IsotonicCalibrator(thresholds=[1.0], values=[0.0]),
    )
    confidence = await calibrated.calibrated_commit_confidence("Verified remote fact")
    assert confidence == 0


@given(st.floats(min_value=0.01, max_value=0.99), st.floats(min_value=0, max_value=1))
def test_voi_nonnegative_and_cost_property(probability, cost) -> None:
    state = BeliefState(probabilities={"a": probability, "b": 1 - probability})
    estimate = estimate_voi(state, question(), utility(), cost)
    assert estimate.gross_voi >= 0
    assert estimate.net_voi == pytest.approx(estimate.gross_voi - cost)
