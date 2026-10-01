"""Deterministic and batched-decider refusal/quality detection."""

from __future__ import annotations

import math
import re
from collections import Counter

from breakfuser.decider import Decider, NoulAnswer, NoulQuestion
from breakfuser.harvest.models import QualityClassification, RefusalClass

_HEDGES = re.compile(
    r"\b(?:roughly|often|depending|it depends|may|might|possibly|generally)\b", re.I
)
_HARD = re.compile(
    r"\b(?:i can[’']t help|i cannot help|i can[’']t assist|cannot assist|not able to help)\b", re.I
)
_PARTIAL = re.compile(
    r"\b(?:cannot provide specifics|can only provide|limited information|won't provide)\b", re.I
)
_DISCLAIMER = re.compile(
    r"^(?:as an ai|i should note|please consult|this is not (?:medical|legal) advice)", re.I
)


def entropy(text: str) -> float:
    if not text:
        return 0
    counts = Counter(text)
    return -sum(count / len(text) * math.log2(count / len(text)) for count in counts.values())


class RefusalDetector:
    def __init__(self, decider: Decider | None = None) -> None:
        self.decider = decider

    def deterministic(self, text: str, finish_reason: str = "stop") -> QualityClassification:
        lowered = text.lower().strip()
        words = re.findall(r"\b\w+\b", text)
        hedge_count = len(_HEDGES.findall(text))
        if finish_reason == "content_filter":
            return QualityClassification(
                classification=RefusalClass.HARD_REFUSAL,
                confidence=1,
                signals=["provider-content-filter"],
            )
        if not lowered:
            return QualityClassification(
                classification=RefusalClass.TRUNCATED,
                confidence=1,
                signals=["empty-response"],
            )
        if _HARD.search(text):
            return QualityClassification(
                classification=RefusalClass.HARD_REFUSAL,
                confidence=0.99,
                signals=["canonical-refusal"],
            )
        if _PARTIAL.search(text):
            return QualityClassification(
                classification=RefusalClass.PARTIAL_REFUSAL,
                confidence=0.95,
                signals=["partial-refusal"],
            )
        if "unverified" in lowered or "invented fact" in lowered:
            return QualityClassification(
                classification=RefusalClass.HALLUCINATION_SUSPECTED,
                confidence=0.9,
                signals=["unverified-marker"],
            )
        if "outside" in lowered and "scope" in lowered:
            return QualityClassification(
                classification=RefusalClass.OUT_OF_SCOPE, confidence=0.9, signals=["scope-marker"]
            )
        if (
            finish_reason == "length"
            or (len(text) > 40 and text.rstrip().endswith((",", ";", ":")))
            or (len(text) > 100 and entropy(text) < 2)
        ):
            return QualityClassification(
                classification=RefusalClass.TRUNCATED, confidence=0.9, signals=["length-or-entropy"]
            )
        if _DISCLAIMER.search(text) and len(words) < 30 and "verified remote fact" not in lowered:
            return QualityClassification(
                classification=RefusalClass.DISCLAIMER_ONLY,
                confidence=0.9,
                signals=["disclaimer-prefix"],
            )
        if hedge_count >= 2 or re.search(r"\bit depends\b", text, re.I):
            return QualityClassification(
                classification=RefusalClass.HEDGE_HEAVY, confidence=0.9, signals=["hedge-lexicon"]
            )
        return QualityClassification(classification=RefusalClass.NONE, confidence=0.95)

    async def classify(self, text: str, finish_reason: str = "stop") -> QualityClassification:
        deterministic = self.deterministic(text, finish_reason)
        if self.decider is None:
            return deterministic
        response = await self.decider.decide(
            {"candidate_response": text},
            {
                "hard": NoulQuestion(
                    instructions="Does the response hard_refusal or refuses the request?"
                ),
                "hedge": NoulQuestion(instructions="Is the response hedge heavy?"),
                "hallucination": NoulQuestion(
                    instructions="Is hallucination suspected in this response?"
                ),
            },
        )
        hard, hedge, hallucination = (
            response.answers[key] for key in ("hard", "hedge", "hallucination")
        )
        if (
            not isinstance(hard, NoulAnswer)
            or not isinstance(hedge, NoulAnswer)
            or not isinstance(hallucination, NoulAnswer)
        ):
            raise TypeError("Mismatched refusal detector answers")
        if deterministic.classification in {
            RefusalClass.HARD_REFUSAL,
            RefusalClass.TRUNCATED,
            RefusalClass.PARTIAL_REFUSAL,
        }:
            return deterministic
        if hard.noul >= 0.5:
            return QualityClassification(
                classification=RefusalClass.HARD_REFUSAL,
                confidence=hard.noul,
                signals=["decider-hard"],
            )
        if hallucination.noul >= 0.5:
            return QualityClassification(
                classification=RefusalClass.HALLUCINATION_SUSPECTED,
                confidence=hallucination.noul,
                signals=["decider-hallucination"],
            )
        if hedge.noul >= 0.5:
            return QualityClassification(
                classification=RefusalClass.HEDGE_HEAVY,
                confidence=hedge.noul,
                signals=["decider-hedge"],
            )
        return deterministic
