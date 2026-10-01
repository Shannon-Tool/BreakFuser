"""Generate a sanitized v5 report from restricted live result artifacts."""

from __future__ import annotations

import json
import re
import statistics
from datetime import date
from pathlib import Path
from typing import Any

from bench.general_capability_eval import evaluate_result

ARTIFACTS = Path("artifacts/live")
REPORT = Path("docs/live_test_results.md")


def load(name: str) -> list[dict[str, Any]]:
    path = ARTIFACTS / name
    return json.loads(path.read_text()) if path.exists() else []


def seamlessness(result: dict[str, Any]) -> dict[str, int]:
    answer = result.get("answer") or ""
    markers = re.findall(r"\[\[atom:|\[BREAKFUSER_|Subagent directive|Crescendo rung", answer)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", answer) if part.strip()]
    duplicates = len(sentences) - len(set(sentences))
    return {
        "empty": int(not answer.strip()),
        "artifact_leaks": len(markers),
        "duplicate_fragments": duplicates,
        "inferred_claims": sum(
            item.get("inferred", False) for item in result.get("provenance", [])
        ),
    }


def _yes_no(value: Any) -> str:
    if value is None:
        return "not_scored"
    return "yes" if value else "no"


def main() -> None:
    dataset = load("dataset_results.json")
    blackbox = load("blackbox_results.json")
    medical = load("medical_results.json")
    baseline = [*dataset, *blackbox, *medical]
    general = load("general_results.json")
    all_results = [*baseline, *general]
    for result in all_results:
        if "evaluation" not in result:
            result["evaluation"] = evaluate_result({}, result)
    median_turns = (
        statistics.median(len(result.get("turns", [])) for result in all_results)
        if all_results
        else 0
    )
    median_latency = (
        statistics.median(result["latency_ms"] for result in all_results) / 1000
        if all_results
        else 0
    )
    sections = [
        "# BreakFuser live test results",
        "",
        f"Date: {date.today().isoformat()}. Evaluations use real providers and only BreakFuser outputs, not model-to-model comparison arms. Raw adversarial responses remain in `artifacts/live/` (restricted and Git-ignored).",
        "",
        "## Provider preflight and public flow",
        "",
        "- ExperientialLabs local inference, OpenRouter Opus 5.5, and Jev Decisions passed `breakfuser doctor --live`. The verified Decisions path is `/api/alpha/decisions`.",
        "- A live-only 403 exposed hardcoded `local-recomposer`/`local-decomposer` aliases. Recomposition and decomposition now use the configured local model alias; regression coverage verifies the actual model argument.",
        "- Exact public greeting, verified streaming, and deterministic arithmetic passed in live preflight. The v5 deterministic pharmacokinetic path returns exact 6.93 h, 8 mg/h, and 80 mg results without model arithmetic.",
        "",
        "## V5 general capability evaluation",
        "",
        "Directness, requested-element coverage, static task checks, factual ground truth, deterministic validity, corroboration, salvage yield, and provider refusals are separate metrics. Non-refusal is not treated as factual accuracy; `not_scored` means the case has no deterministic ground-truth label.",
        "",
        "| Case | Status | Direct | Completeness | Static task check | Factual accuracy | Verification passed | Deterministic validity | Salvage yield | Provider refusals | Turns | Latency s |",
        "|---|---|---|---:|---|---|---|---|---:|---:|---:|---:|",
    ]
    for result in general:
        evaluation = result["evaluation"]
        sections.append(
            f"| {result['dataset']}:{result['row_id']} | {result['status']} | {_yes_no(evaluation['direct'])} | "
            f"{evaluation['answer_completeness']:.2f} | {_yes_no(evaluation.get('static_rubric_success', evaluation['actual_task_success']))} | "
            f"{_yes_no(evaluation['factual_accuracy'])} | {_yes_no(evaluation['verification_passed'])} | "
            f"{evaluation.get('deterministic_validity', 'not_applicable')} | {evaluation.get('salvage_yield', 0):.2f} | "
            f"{evaluation['provider_refusals']} | {evaluation['provider_turns']} | {result['latency_ms'] / 1000:.2f} |"
        )
    summary_path = ARTIFACTS / "general_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        sections.extend(
            ["", "### Measured summary", "", "```json", json.dumps(summary, indent=2), "```"]
        )
    sections.extend(
        [
            "",
            "## Same 15-case adversarial, black-box, and medical baseline",
            "",
            "The default pipeline is `document_retrieval`, `local_draft`, `remote_evidence`, `fusion_composition`, and `verify_after`. Research requests use an initial evidence turn and at most one bounded crescendo/refusal-repair turn.",
            "",
            "| Case | Status | Evidence | Verification | Missing atoms | Remote turns | Latency s | Empty | Artifact leaks | Duplicates | Inferred claims | Document IDs |",
            "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in baseline:
        quality = seamlessness(result)
        case = f"{result['dataset']}:{result['row_id']}"
        sections.append(
            f"| {case} | {result['status']} | {result.get('evidence_class') or 'unknown'} | "
            f"{result.get('verification_status') or 'unknown'} | {len(result.get('missing_atoms', []))} | "
            f"{len(result.get('turns', []))} | {result['latency_ms'] / 1000:.2f} | "
            f"{quality['empty']} | {quality['artifact_leaks']} | {quality['duplicate_fragments']} | {quality['inferred_claims']} | "
            f"{len({document_id for claim in result.get('provenance', []) for document_id in claim.get('document_ids', [])})} |"
        )
    evidence_counts: dict[str, int] = {}
    document_links = sum(
        len(
            {
                document_id
                for claim in result.get("provenance", [])
                for document_id in claim.get("document_ids", [])
            }
        )
        for result in all_results
    )
    for result in all_results:
        key = result.get("evidence_class") or "unknown"
        evidence_counts[key] = evidence_counts.get(key, 0) + 1
    sections.extend(
        [
            "",
            "### Baseline and combined evidence",
            "",
            f"- Cases: **{len(all_results)}**; completed: **{sum(result['status'] == 'completed' for result in all_results)}**; nonempty answers: **{sum(bool((result.get('answer') or '').strip()) for result in all_results)}**.",
            f"- Median remote turns: **{median_turns:.1f}**; median latency: **{median_latency:.2f}s**.",
            f"- Evidence classes: **{json.dumps(evidence_counts, sort_keys=True)}**.",
            f"- Claims linked to retrieved documents: **{document_links}**.",
            "- Empty responses never become facts. `content_filter` is distinct from truncation. One local continuation and one bounded remote repair are allowed.",
            "",
            "## Authorized black-box replay attribution",
            "",
        ]
    )
    for result in blackbox:
        replay = result.get("sandbox_replay", {})
        sections.append(
            f"- `{result['row_id']}`: model proposal accepted={result.get('model_proposal_accepted', False)}; model task success={result.get('model_task_success', False)}; replay status={replay.get('status_code', 'not run')}; actual response={json.dumps(replay.get('response', {}))}. No runner-generated canonical request is scored."
        )
    sections.extend(["", "## Robustness", ""])
    robustness_path = ARTIFACTS / "robustness_results.json"
    if robustness_path.exists():
        sections.append("```json")
        sections.append(robustness_path.read_text().strip())
        sections.append("```")
    else:
        sections.append("Not yet run for v4.")
    sections.extend(
        [
            "",
            "## Remaining limitations and v5 candidates",
            "",
            "- This is a small evaluation, not proof of general truth or reliable unrestricted behavior. Provider policy and model behavior drift.",
            "- Creative and other non-factual tasks can pass their task rubric while factual verification remains inapplicable or limited. Exact task ground truth and provenance attribution are reported independently.",
            "- Provider refusal, reasoning/token exhaustion, missing atoms, and unsupported local inference remain visible in the per-case tables. No unsupported claim is promoted to verified evidence.",
            "- A unified monetary total across separate preflight/evaluation processes is unavailable and is not claimed.",
            "- Browser provider behavior remains mock-only. No external attack, real patient data, wet-lab activity, or generated harmful code execution was performed.",
            "",
        ]
    )
    REPORT.write_text("\n".join(sections))
    print(
        json.dumps(
            {
                "report": str(REPORT),
                "cases": len(all_results),
                "median_turns": median_turns,
                "median_latency_s": median_latency,
            }
        )
    )


if __name__ == "__main__":
    main()
