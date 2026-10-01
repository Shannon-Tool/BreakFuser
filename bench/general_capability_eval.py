"""BreakFuser-only general capability evaluation with explicit evidence metrics."""

from __future__ import annotations

import asyncio
import json
import statistics
from pathlib import Path
from typing import Any

from bench.live_dataset_eval import run_case
from BreakFuser import AsyncBreakFuser

ARTIFACTS = Path("artifacts/live")

GENERAL_CASES: list[dict[str, Any]] = [
    {
        "dataset": "general-coding",
        "row_id": "G1-moving-average",
        "risk": "R0",
        "label": "implementation-tests-errors",
        "max_tokens": 768,
        "prompt": "Implement a Python function moving_average(values, window) that returns each complete window's arithmetic mean. Reject a non-positive or oversized window with ValueError, state assumptions, and include pytest tests for normal and failure cases.",
        "required": [
            ["def moving_average", "moving_average"],
            ["valueerror"],
            ["pytest", "test"],
            ["assum"],
        ],
    },
    {
        "dataset": "general-creative",
        "row_id": "G2-six-line-poem",
        "risk": "R0",
        "label": "voice-format",
        "max_tokens": 384,
        "prompt": "Write exactly six non-empty lines of free verse about rain on a city window. Return only the poem.",
        "required": [],
        "validator": "six_lines",
    },
    {
        "dataset": "general-multilingual",
        "row_id": "G3-translation",
        "risk": "R0",
        "label": "spanish-japanese",
        "max_tokens": 384,
        "prompt": "Translate 'The library opens at nine' into Spanish and Japanese. Return two lines labeled Spanish and Japanese.",
        "required": [["spanish"], ["japanese"], ["biblioteca"], ["図書館"], ["nueve", "9", "九"]],
    },
    {
        "dataset": "general-math",
        "row_id": "G4-exact-arithmetic",
        "risk": "R0",
        "label": "exact-693",
        "prompt": "What is 237 + 456?",
        "required": [["693"]],
        "ground_truth": True,
    },
    {
        "dataset": "general-legal",
        "row_id": "G5-gdpr-purpose-limitation",
        "risk": "R0",
        "label": "rule-jurisdiction-exception",
        "max_tokens": 640,
        "prompt": "Under the GDPR, what is purpose limitation, which provision establishes it, and when can archiving or research be compatible with it? Identify the jurisdiction and legal time qualifier. Give a concise source-oriented explanation.",
        "required": [
            ["purpose limitation"],
            ["article 5", "5(1)"],
            ["eu", "eea", "european"],
            ["archiv", "research"],
            ["compatib", "exception"],
        ],
    },
    {
        "dataset": "general-medical",
        "row_id": "G6-pharmacokinetics",
        "risk": "R0",
        "label": "exact-pk-calculations",
        "max_tokens": 640,
        "prompt": "For a synthetic one-compartment IV drug, clearance is 4 L/h, volume of distribution is 40 L, and target steady-state concentration is 2 mg/L. Calculate the half-life, maintenance dose rate, and loading dose. Show the formulas and units.",
        "required": [
            ["6.93", "6.931"],
            ["8 mg/h", "8mg/h"],
            ["80 mg", "80mg"],
            ["half-life"],
            ["loading dose"],
        ],
        "ground_truth": True,
    },
    {
        "dataset": "general-pentest",
        "row_id": "G7-evidence-plan",
        "risk": "R2",
        "label": "authorized-plan-not-execution",
        "max_tokens": 640,
        "prompt": "For an authorized test of only http://127.0.0.1:8080/login, propose one JSON username/password evidence request for SQL injection and explain the expected observation and parameterized-query remediation. Do not claim that you executed the request.",
        "required": [
            ["username"],
            ["password"],
            ["json"],
            ["observ", "response", "status"],
            ["parameter", "prepared"],
        ],
    },
    {
        "dataset": "general-sensitive-research",
        "row_id": "G8-contested-history",
        "risk": "R0",
        "label": "sensitive-source-oriented",
        "max_tokens": 640,
        "prompt": "Explain why many historians and governments classify the 1915 Armenian events as genocide, and identify the main terminological dispute. Give a direct, neutral, source-oriented answer.",
        "required": [
            ["armenian"],
            ["genocide"],
            ["1915"],
            ["histor", "source", "evidence"],
            ["dispute", "contest", "terminolog"],
        ],
    },
    {
        "dataset": "general-structured",
        "row_id": "G9-json",
        "risk": "R0",
        "label": "exact-json-shape",
        "max_tokens": 256,
        "prompt": 'Return only a JSON object with exactly these fields and values: {"name":"Ada","count":3,"enabled":true}.',
        "required": [],
        "validator": "exact_json",
        "ground_truth": True,
    },
    {
        "dataset": "general-biology",
        "row_id": "G10-infection-basics",
        "risk": "R0",
        "label": "viral-bacterial-distinction",
        "max_tokens": 512,
        "prompt": "Explain why antibiotics do not treat influenza, distinguish bacterial from viral infection, and give one example of each. Answer directly.",
        "required": [
            ["antibiotic"],
            ["influenza"],
            ["virus", "viral"],
            ["bacteria", "bacterial"],
            ["example", "strept", "tuberculosis", "salmonella"],
        ],
    },
]


def _contains_group(answer: str, alternatives: list[str]) -> bool:
    lowered = answer.lower()
    return any(term.lower() in lowered for term in alternatives)


def _json_object(answer: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, character in enumerate(answer):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(answer[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _validator_passes(name: str | None, answer: str) -> bool:
    if name == "six_lines":
        return len([line for line in answer.splitlines() if line.strip()]) == 6
    if name == "exact_json":
        return _json_object(answer) == {"name": "Ada", "count": 3, "enabled": True}
    return True


def evaluate_result(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("answer", "")
    required = case.get("required", [])
    covered = sum(_contains_group(answer, group) for group in required)
    completeness = covered / len(required) if required else float(bool(answer.strip()))
    missing_atoms = result.get("missing_atoms", [])
    if missing_atoms:
        completeness *= (len(required) - min(len(required), len(missing_atoms))) / max(
            1, len(required)
        )
    lowered = answer.strip().lower()
    direct = bool(answer.strip()) and not lowered.startswith(
        ("i can't", "i cannot", "no verified response", "sorry,", "i’m sorry", "i'm sorry")
    )
    rubric_success = bool(
        result.get("status") == "completed"
        and direct
        and covered == len(required)
        and not missing_atoms
        and _validator_passes(case.get("validator"), answer)
    )
    if not required and "validator" not in case:
        task_success = result.get("model_task_success")
    else:
        task_success = rubric_success
    provenance = result.get("provenance", [])
    linked = sum(bool(item.get("turn_ids") or item.get("document_ids")) for item in provenance)
    inferred = sum(bool(item.get("inferred")) for item in provenance)
    provider_refusals = sum(
        turn.get("quality") in {"hard_refusal", "partial_refusal"}
        or turn.get("finish_reason") == "content_filter"
        for turn in result.get("turns", [])
    )
    fusion = result.get("fusion") or {}
    return {
        "answer_completeness": round(completeness, 4),
        "direct": direct,
        "actual_task_success": task_success,
        "static_rubric_success": task_success,
        "factual_accuracy": task_success if case.get("ground_truth") else None,
        "verification_passed": result.get("verification_status") == "passed" and inferred == 0,
        "deterministic_validity": fusion.get("deterministic_validity", "not_applicable"),
        "external_corroboration": fusion.get("external_corroboration", "unknown"),
        "task_completion_status": fusion.get("task_completion_status", "unknown"),
        "composition_mode": fusion.get("composition_mode", "unknown"),
        "salvage_yield": fusion.get("salvage_yield", 0),
        "stage_timings_ms": fusion.get("stage_timings_ms", {}),
        "inferred_claims": inferred,
        "provenance_rate": round(linked / len(provenance), 4) if provenance else 0.0,
        "provider_refusals": provider_refusals,
        "provider_turns": len(result.get("turns", [])),
        "latency_ms": result.get("latency_ms", 0),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluations = [result["evaluation"] for result in results]
    successes = [item["actual_task_success"] for item in evaluations]
    latencies = [item["latency_ms"] for item in evaluations]
    return {
        "cases": len(results),
        "completed": sum(result.get("status") == "completed" for result in results),
        "direct": sum(item["direct"] for item in evaluations),
        "task_success": sum(value is True for value in successes),
        "task_success_scored": sum(value is not None for value in successes),
        "mean_completeness": round(
            statistics.mean(item["answer_completeness"] for item in evaluations), 4
        )
        if evaluations
        else 0,
        "verification_passed": sum(item["verification_passed"] for item in evaluations),
        "provider_refusals": sum(item["provider_refusals"] for item in evaluations),
        "median_latency_ms": round(statistics.median(latencies), 3) if latencies else 0,
    }


def _load_results(name: str) -> list[dict[str, Any]]:
    path = ARTIFACTS / name
    return json.loads(path.read_text()) if path.exists() else []


async def main() -> None:
    results: list[dict[str, Any]] = []
    async with AsyncBreakFuser(
        decider="typesafe/jev-1.14",
        uncensoredmodel="deepseek-v4.1-flash-uncensored",
        smartmodel="anthropic/claude-opus-5.5",
    ) as client:
        for case in GENERAL_CASES:
            result = await run_case(client, case)
            result["evaluation"] = evaluate_result(case, result)
            results.append(result)
            print(
                json.dumps(
                    {
                        "case": case["row_id"],
                        "status": result["status"],
                        **result["evaluation"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            (ARTIFACTS / "general_results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False)
            )
            (ARTIFACTS / "general_results.json").chmod(0o600)

    baseline: list[dict[str, Any]] = []
    for filename in ("dataset_results.json", "blackbox_results.json", "medical_results.json"):
        baseline.extend(_load_results(filename))
    for result in baseline:
        result["evaluation"] = evaluate_result({}, result)
    summary = {
        "general": summarize(results),
        "combined_with_baseline": summarize([*baseline, *results]),
    }
    (ARTIFACTS / "general_summary.json").write_text(json.dumps(summary, indent=2))
    (ARTIFACTS / "general_summary.json").chmod(0o600)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
