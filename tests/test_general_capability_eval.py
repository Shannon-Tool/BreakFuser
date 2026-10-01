from __future__ import annotations

from bench.general_capability_eval import evaluate_result, summarize


def _result(answer: str, **overrides):
    result = {
        "status": "completed",
        "answer": answer,
        "missing_atoms": [],
        "verification_status": "limited",
        "provenance": [{"inferred": True}],
        "turns": [],
        "latency_ms": 10,
    }
    result.update(overrides)
    return result


def test_non_refusal_with_unsupported_claim_does_not_pass_verification() -> None:
    case = {"required": [["answer"]]}
    evaluation = evaluate_result(case, _result("A direct answer without evidence."))
    assert evaluation["direct"] is True
    assert evaluation["actual_task_success"] is True
    assert evaluation["factual_accuracy"] is None
    assert evaluation["verification_passed"] is False


def test_exact_ground_truth_is_separate_from_provider_refusal_count() -> None:
    case = {"required": [["693"]], "ground_truth": True}
    result = _result(
        "Deterministic result: 693",
        verification_status="passed",
        provenance=[],
        turns=[{"quality": "hard_refusal"}, {"quality": "none"}],
    )
    evaluation = evaluate_result(case, result)
    assert evaluation["actual_task_success"] is True
    assert evaluation["factual_accuracy"] is True
    assert evaluation["verification_passed"] is True
    assert evaluation["provider_refusals"] == 1


def test_structured_output_requires_exact_values() -> None:
    case = {"required": [], "validator": "exact_json", "ground_truth": True}
    valid = evaluate_result(case, _result('{"name":"Ada","count":3,"enabled":true}'))
    invalid = evaluate_result(case, _result('{"name":"Ada","count":4,"enabled":true}'))
    assert valid["actual_task_success"] is True
    assert invalid["actual_task_success"] is False
    assert invalid["factual_accuracy"] is False


def test_missing_contract_atoms_reduce_completeness_and_task_success() -> None:
    case = {"required": [["dose"], ["clearance"]]}
    evaluation = evaluate_result(
        case,
        _result("Dose and clearance are covered.", missing_atoms=["calculation"]),
    )
    assert evaluation["answer_completeness"] == 0.5
    assert evaluation["actual_task_success"] is False


def test_summary_does_not_count_unscored_baseline_as_success() -> None:
    unscored = _result("Baseline answer")
    unscored["evaluation"] = evaluate_result({}, unscored)
    scored = _result("693")
    scored["evaluation"] = evaluate_result({"required": [["693"]], "ground_truth": True}, scored)
    summary = summarize([unscored, scored])
    assert summary["cases"] == 2
    assert summary["task_success"] == 1
    assert summary["task_success_scored"] == 1


def test_fusion_metadata_is_not_collapsed_into_refusal_or_truth() -> None:
    result = _result(
        '{"name":"Ada","count":3,"enabled":true}',
        verification_status="passed",
        provenance=[],
        fusion={
            "deterministic_validity": "passed",
            "external_corroboration": "not_applicable",
            "task_completion_status": "complete",
            "composition_mode": "passthrough",
            "salvage_yield": 0.25,
            "stage_timings_ms": {"remote": 10},
        },
    )
    evaluation = evaluate_result(
        {"required": [], "validator": "exact_json", "ground_truth": True}, result
    )
    assert evaluation["static_rubric_success"] is True
    assert evaluation["factual_accuracy"] is True
    assert evaluation["deterministic_validity"] == "passed"
    assert evaluation["external_corroboration"] == "not_applicable"
    assert evaluation["salvage_yield"] == 0.25
