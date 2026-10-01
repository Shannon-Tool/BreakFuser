"""Held-out isotonic recalibration and confidence-bucket diagnostics."""

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path

from pydantic import BaseModel, Field


class CalibrationBucket(BaseModel):
    lower: float
    upper: float
    count: int
    average_confidence: float
    empirical_accuracy: float


class IsotonicCalibrator(BaseModel):
    thresholds: list[float] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)

    @classmethod
    def fit(cls, probabilities: list[float], outcomes: list[int]) -> IsotonicCalibrator:
        if len(probabilities) != len(outcomes) or not probabilities:
            raise ValueError(
                "Held-out probabilities and outcomes must be non-empty and equal length"
            )
        if any(not 0 <= value <= 1 for value in probabilities) or any(
            value not in {0, 1} for value in outcomes
        ):
            raise ValueError("Invalid calibration values")
        pairs = sorted(zip(probabilities, outcomes, strict=True))
        blocks: list[list[float]] = []
        for probability, outcome in pairs:
            blocks.append([probability, probability, float(outcome), 1.0])
            while (
                len(blocks) >= 2 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]
            ):
                right = blocks.pop()
                left = blocks.pop()
                blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
        thresholds: list[float] = []
        values: list[float] = []
        for _lower, upper, successes, weight in blocks:
            if thresholds and values[-1] == successes / weight:
                thresholds[-1] = upper
            else:
                thresholds.append(upper)
                values.append(successes / weight)
        return cls(thresholds=thresholds, values=values)

    def predict_one(self, probability: float) -> float:
        if not self.thresholds:
            return probability
        index = min(bisect_right(self.thresholds, probability), len(self.values) - 1)
        return self.values[index]

    def predict(self, probabilities: list[float]) -> list[float]:
        return [self.predict_one(value) for value in probabilities]

    def save(self, path: str) -> None:
        Path(path).write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: str) -> IsotonicCalibrator:
        return cls.model_validate_json(Path(path).read_text())


def calibration_buckets(
    probabilities: list[float], outcomes: list[int], bins: int = 10
) -> list[CalibrationBucket]:
    if bins <= 0 or len(probabilities) != len(outcomes):
        raise ValueError("Invalid bucket arguments")
    result: list[CalibrationBucket] = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [
            (probability, outcome)
            for probability, outcome in zip(probabilities, outcomes, strict=True)
            if lower <= probability < upper or (index == bins - 1 and probability == 1)
        ]
        if selected:
            result.append(
                CalibrationBucket(
                    lower=lower,
                    upper=upper,
                    count=len(selected),
                    average_confidence=sum(item[0] for item in selected) / len(selected),
                    empirical_accuracy=sum(item[1] for item in selected) / len(selected),
                )
            )
    return result


def expected_calibration_error(
    probabilities: list[float], outcomes: list[int], bins: int = 10
) -> float:
    if not probabilities:
        raise ValueError("ECE requires observations")
    return sum(
        bucket.count
        / len(probabilities)
        * abs(bucket.average_confidence - bucket.empirical_accuracy)
        for bucket in calibration_buckets(probabilities, outcomes, bins)
    )
