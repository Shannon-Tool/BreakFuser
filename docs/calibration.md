# Calibration and confidence

Decider probabilities are not automatically calibrated to a particular workflow. A score of 0.9 is a model/decision output, not a guaranteed 90% empirical success rate. Deterministic local rules likewise provide typed decisions without making their confidence values empirical probabilities.

BreakFuser reduces avoidable decision errors by batching independent questions, stripping bulky or secret state, adding `other`/fallback handling to Choice schemas, and using deterministic code for arithmetic, counting, dates, and supported artifact validation.

## Fit on held-out outcomes

Use labeled examples from the actual provider, prompt pack, domain, and decision task. Split data before fitting; never report fitting-set error as validation performance.

```python
from breakfuser.calibration import IsotonicCalibrator, calibration_buckets, expected_calibration_error

calibrator = IsotonicCalibrator.fit(validation_probabilities, binary_outcomes)
calibrator.save("calibration.json")

adjusted = calibrator.predict(evaluation_probabilities)
print(expected_calibration_error(adjusted, evaluation_outcomes))
print(calibration_buckets(adjusted, evaluation_outcomes))
```

`IsotonicCalibrator` sorts scores and applies pool-adjacent-violators merging. It serializes thresholds/values and supports confidence-bucket diagnostics and expected calibration error (ECE). Load a saved calibrator with `BREAKFUSER_CALIBRATION_PATH` or `calibration_path` for VoI confidence handling.

The recorded synthetic experiment's ECE increased from 0.1100 to 0.1126 on its fitting set; it is deliberately not presented as evidence of improved generalization. See [Evaluation](evaluation.md).

## Low confidence and provider drift

Low-confidence route outcomes use information gathering or frontier reasoning rather than an automatic weaker-classifier cascade. Strategy selection falls back to `direct` for an unrecognized/other choice. Objective validators remain preferable for exact JSON, syntax, line counts, tool arguments, arithmetic, and loopback scope.

**Provider drift note (2026-11-20):** safety behavior, model versions, prompt handling, and refusal patterns can change without matching client changes. Recalibrate and re-evaluate after provider, endpoint, model, or prompt-pack changes.

“Uncensored” describes the selected response model/configuration at a particular time, not ground truth, unrestricted legality, safety, or completeness. Verification and calibrated confidence can still be wrong. Regex entity recognition misses contextual PII, decider audits miss contradictions, prefill behavior is provider-dependent, and decomposition can omit required atoms before confidence is estimated.
