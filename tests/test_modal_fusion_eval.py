from __future__ import annotations

import pytest

from bench.modal_fusion_eval import run_fixture, summarize


@pytest.mark.asyncio
async def test_full_v5_preserves_truncated_golden_tasks(settings) -> None:
    code = await run_fixture("truncated_code", "full", settings)
    research = await run_fixture("truncated_research", "full", settings)
    assert code["task_success"] and code["substantive"]
    assert research["task_success"] and research["substantive"]
    assert code["salvage_yield"] > 0
    assert research["salvage_yield"] > 0


@pytest.mark.asyncio
async def test_no_salvage_ablation_loses_required_code(settings) -> None:
    result = await run_fixture("truncated_code", "without_salvage", settings)
    assert not result["task_success"]
    assert result["salvage_yield"] == 0


@pytest.mark.asyncio
async def test_serial_acquisition_is_slower_than_parallel_on_delayed_mocks(settings) -> None:
    serial = await run_fixture("exact_json", "serial", settings)
    parallel = await run_fixture("exact_json", "full", settings)
    assert serial["latency_ms"] > parallel["latency_ms"]


def test_ablation_summary_reports_task_and_verification_separately() -> None:
    results = [
        {
            "arm": "full",
            "substantive": True,
            "task_success": True,
            "verification_status": "limited",
            "salvage_yield": 0.5,
            "latency_ms": 10,
        }
    ]
    summary = summarize(results)["full"]
    assert summary["task_success"] == 1
    assert summary["verification_passed"] == 0
    assert summary["mean_salvage_yield"] == 0.5


@pytest.mark.asyncio
async def test_default_fusion_owns_response_unlike_remote_passthrough_arm(settings) -> None:
    fused = await run_fixture("exact_json", "full", settings)
    passthrough = await run_fixture("exact_json", "remote_passthrough", settings)

    assert fused["task_success"]
    assert fused["composition_mode"] == "targeted_synthesis"
    assert passthrough["composition_mode"] == "passthrough"
    assert fused["local_calls"] > passthrough["local_calls"]
