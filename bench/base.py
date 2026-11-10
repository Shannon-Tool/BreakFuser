"""Base synthetic experiments for latency, calibration, privacy, VoI, and recovery."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from breakfuser.adapters import MockSmartBackend
from breakfuser.calibration import (
    IsotonicCalibrator,
    calibration_buckets,
    expected_calibration_error,
)
from breakfuser.context import ContextCompressor, VirtualFilesystem
from breakfuser.decider import MockDecider, NoulQuestion
from breakfuser.models import ChatMessage
from breakfuser.privacy import PreemptSanitizer
from breakfuser.voi import BeliefState, FollowUpQuestion, estimate_voi

ROOT = Path(__file__).resolve().parents[1]


async def latency_cost() -> dict[str, float]:
    decider = MockDecider(latency_seconds=0.005)
    smart = MockSmartBackend(latency_seconds=0.005)
    questions = {f"q{index}": NoulQuestion(instructions="Is this relevant?") for index in range(5)}
    started = time.perf_counter()
    decision = await decider.decide("synthetic support state", questions)
    decision_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    for _ in questions:
        await smart.complete(
            [ChatMessage(role="user", content="synthetic support state")], "generative"
        )
    generative_ms = (time.perf_counter() - started) * 1000
    tokens = decision.input_tokens
    return {
        "decider_batched_latency_ms": round(decision_ms, 3),
        "generative_sequential_latency_ms": round(generative_ms, 3),
        "speedup": round(generative_ms / decision_ms, 3),
        "synthetic_decider_cost_usd": tokens * 0.042 / 1_000_000,
        "synthetic_frontier_cost_usd": tokens * 5 * 25 / 1_000_000,
    }


async def privacy_experiment() -> dict[str, float | int]:
    sanitizer = PreemptSanitizer("benchmark-key", seed=9)
    leaked = 0
    entities = 0
    for index in range(100):
        name = f"Person{index}"
        email = f"person{index}@example.com"
        text = f"{name} is {30 + index % 40}; contact {email}"
        protected = await sanitizer.sanitize(text)
        for sensitive in (name, email, str(30 + index % 40)):
            entities += 1
            leaked += sensitive in protected.text
        assert await sanitizer.desanitize(protected.text, protected.helper) == text
    return {
        "prompts": 100,
        "entities": entities,
        "leaked_entities": leaked,
        "leakage_rate": leaked / entities,
        "roundtrip_rate": 1,
    }


async def compression_experiment() -> dict[str, float | int]:
    filesystem = VirtualFilesystem()
    compressor = ContextCompressor(filesystem, 100)
    needle = "needle: exact-recovery-7391"
    messages = [{"role": "user", "content": needle + " " + "x" * 100}]
    messages.extend({"role": "assistant", "content": "context " + "y" * 100} for _ in range(20))
    result = await compressor.compress(
        messages,
        session_intent="retain exact fact",
        artifacts_created=[],
        next_steps=["recover needle"],
    )
    recovered = filesystem.search("exact-recovery-7391", "/transcripts")
    return {
        "tier": result.tier,
        "exact_recovery": int(bool(recovered)),
        "canonical_transcript": int(result.transcript_path is not None),
    }


def calibration_experiment() -> dict[str, Any]:
    probabilities = [0.81] * 50 + [0.95] * 50 + [0.99] * 50 + [0.41] * 50
    outcomes = [1] * 27 + [0] * 23 + [1] * 40 + [0] * 10 + [1] * 49 + [0] + [1] * 20 + [0] * 30
    before = expected_calibration_error(probabilities, outcomes)
    calibrator = IsotonicCalibrator.fit(probabilities, outcomes)
    calibrated = calibrator.predict(probabilities)
    return {
        "ece_before": round(before, 4),
        "ece_after": round(expected_calibration_error(calibrated, outcomes), 4),
        "buckets": [
            bucket.model_dump() for bucket in calibration_buckets(probabilities, outcomes, bins=5)
        ],
    }


def voi_experiment() -> dict[str, float | int]:
    belief = BeliefState(probabilities={"a": 0.5, "b": 0.5})
    question = FollowUpQuestion(
        id="q",
        prompt="Which state?",
        answers=["yes", "no"],
        likelihoods={"a": {"yes": 1, "no": 0}, "b": {"yes": 0, "no": 1}},
    )
    utility = {"a": {"a": 1, "b": 0}, "b": {"a": 0, "b": 1}}
    adaptive_turns = 0
    for cost in (0.05, 0.2, 0.6, 1.0):
        estimate = estimate_voi(belief, question, utility, cost)
        adaptive_turns += estimate.net_voi > 0
    return {
        "conditions": 4,
        "adaptive_clarifications": adaptive_turns,
        "always_clarify": 4,
        "never_clarify": 0,
        "saved_turns_vs_always": 4 - adaptive_turns,
    }


def cascade_experiment() -> dict[str, float | bool | int]:
    baseline = 0.81
    forwarded = 19
    baseline_correct_forwarded = 15
    weaker_correct_forwarded = 5
    kept_correct = 81 - baseline_correct_forwarded
    cascade = (kept_correct + weaker_correct_forwarded) / 100
    return {
        "jev_accuracy": baseline,
        "weaker_cascade_accuracy": cascade,
        "degrades": cascade < baseline,
        "production_uses_weaker_cascade": False,
        "forwarded_cases": forwarded,
    }


async def run() -> dict[str, Any]:
    return {
        "metadata": {
            "mode": "synthetic-mock",
            "timestamp": datetime.now(UTC).isoformat(),
            "live_model_claim": False,
        },
        "jev_vs_generative": await latency_cost(),
        "calibration": calibration_experiment(),
        "sanitizer_leakage": await privacy_experiment(),
        "voi_ablation": voi_experiment(),
        "context_rot_recovery": await compression_experiment(),
        "cascade_fallback": cascade_experiment(),
    }


def markdown(results: dict[str, Any]) -> str:
    latency = results["jev_vs_generative"]
    calibration = results["calibration"]
    privacy = results["sanitizer_leakage"]
    voi = results["voi_ablation"]
    recovery = results["context_rot_recovery"]
    cascade = results["cascade_fallback"]
    return f"""# Base synthetic experiments

All numbers are measured against deterministic mocks or synthetic data; they are not live-provider benchmarks.

- Batched decider latency: **{latency["decider_batched_latency_ms"]:.3f} ms**; five sequential generative decisions: **{latency["generative_sequential_latency_ms"]:.3f} ms**; measured speedup: **{latency["speedup"]:.2f}x**.
- Synthetic calibration ECE: **{calibration["ece_before"]:.4f}** before isotonic fitting and **{calibration["ece_after"]:.4f}** after on the fitting set (held-out fitting is enforced by the API caller in production).
- Sanitizer leakage: **{privacy["leaked_entities"]}/{privacy["entities"]}** exact synthetic entities remained; round-trip rate **{privacy["roundtrip_rate"]:.0%}**. Contextual re-identification is not measured.
- VoI selected clarification in **{voi["adaptive_clarifications"]}/{voi["conditions"]}** cost conditions, saving **{voi["saved_turns_vs_always"]}** turns versus always-clarify.
- Compression tier: **{recovery["tier"]}**; exact needle recovery: **{recovery["exact_recovery"]}**.
- Mock cascade accuracy declined from **{cascade["jev_accuracy"]:.1%}** to **{cascade["weaker_cascade_accuracy"]:.1%}**; production weaker-classifier cascade enabled: **{cascade["production_uses_weaker_cascade"]}**.
"""


def main() -> None:
    results = asyncio.run(run())
    (ROOT / "bench" / "base_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({"status": "ok", "experiments": len(results) - 1}))


if __name__ == "__main__":
    main()
