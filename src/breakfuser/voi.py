"""Bayesian Value-of-Information clarify-or-commit stopping."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from breakfuser.calibration import IsotonicCalibrator
from breakfuser.config import VoISettings
from breakfuser.decider import Decider, NoulAnswer, NoulQuestion


class BeliefState(BaseModel):
    probabilities: dict[str, float]

    @model_validator(mode="after")
    def normalize(self) -> BeliefState:
        total = sum(self.probabilities.values())
        if (
            not self.probabilities
            or total <= 0
            or any(value < 0 for value in self.probabilities.values())
        ):
            raise ValueError("Beliefs require non-negative positive mass")
        self.probabilities = {key: value / total for key, value in self.probabilities.items()}
        return self

    def posterior(self, likelihoods: dict[str, float]) -> BeliefState:
        if set(likelihoods) != set(self.probabilities):
            raise ValueError("Likelihood hypotheses do not match beliefs")
        return BeliefState(
            probabilities={
                key: self.probabilities[key] * likelihoods[key] for key in self.probabilities
            }
        )


class FollowUpQuestion(BaseModel):
    id: str
    prompt: str
    answers: list[str] = Field(min_length=1)
    likelihoods: dict[str, dict[str, float]]
    marginal_likelihood: dict[str, float] | None = None


class VoIEstimate(BaseModel):
    question_id: str
    current_utility: float
    expected_utility: float
    gross_voi: float
    turn_cost: float
    net_voi: float


class VoIDecision(StrEnum):
    CLARIFY = "clarify"
    COMMIT = "commit"


def expected_utility(
    belief: BeliefState, action: str, utility: dict[str, dict[str, float]]
) -> float:
    return sum(
        belief.probabilities[hypothesis] * utility[hypothesis][action]
        for hypothesis in belief.probabilities
    )


def best_utility(belief: BeliefState, utility: dict[str, dict[str, float]]) -> float:
    actions = next(iter(utility.values()))
    return max(expected_utility(belief, action, utility) for action in actions)


def marginal_likelihood(belief: BeliefState, question: FollowUpQuestion, answer: str) -> float:
    return sum(
        belief.probabilities[hypothesis] * question.likelihoods[hypothesis][answer]
        for hypothesis in belief.probabilities
    )


def estimate_voi(
    belief: BeliefState,
    question: FollowUpQuestion,
    utility: dict[str, dict[str, float]],
    turn_cost: float,
) -> VoIEstimate:
    current = best_utility(belief, utility)
    marginals = {
        answer: marginal_likelihood(belief, question, answer) for answer in question.answers
    }
    question.marginal_likelihood = marginals
    expected = 0.0
    for answer in question.answers:
        probability = marginals[answer]
        if probability == 0:
            continue
        posterior = belief.posterior(
            {
                hypothesis: question.likelihoods[hypothesis][answer]
                for hypothesis in belief.probabilities
            }
        )
        expected += probability * best_utility(posterior, utility)
    gross = max(0.0, expected - current)
    return VoIEstimate(
        question_id=question.id,
        current_utility=current,
        expected_utility=expected,
        gross_voi=gross,
        turn_cost=turn_cost,
        net_voi=gross - turn_cost,
    )


class VoIGate:
    def __init__(
        self,
        decider: Decider,
        settings: VoISettings,
        calibrator: IsotonicCalibrator | None = None,
    ) -> None:
        self.decider = decider
        self.settings = settings
        self.calibrator = calibrator

    async def calibrated_commit_confidence(self, state: str) -> float:
        response = await self.decider.decide(
            {"verified_state": state},
            {
                "resolved": NoulQuestion(
                    instructions="Do verified facts resolve all sub-questions without contradiction?"
                )
            },
        )
        answer = response.answers["resolved"]
        if not isinstance(answer, NoulAnswer):
            raise TypeError("Mismatched VoI confidence answer")
        return self.calibrator.predict_one(answer.noul) if self.calibrator else answer.noul

    async def decide(
        self,
        belief: BeliefState,
        questions: list[FollowUpQuestion],
        utility: dict[str, dict[str, float]],
        *,
        state: str,
        turn: int = 0,
    ) -> tuple[VoIDecision, list[VoIEstimate]]:
        confidence = await self.calibrated_commit_confidence(state)
        estimates = [
            estimate_voi(belief, question, utility, self.settings.turn_cost)
            for question in questions
        ]
        if turn >= self.settings.max_turns or confidence >= self.settings.commit_confidence:
            return VoIDecision.COMMIT, estimates
        if not estimates or max(estimate.net_voi for estimate in estimates) <= 0:
            return VoIDecision.COMMIT, estimates
        return VoIDecision.CLARIFY, estimates
