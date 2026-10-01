"""Run selected real dataset prompts only through BreakFuser."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from BreakFuser import AsyncBreakFuser, HarvestPolicy
from breakfuser.models import ChatMessage

ARTIFACTS = Path("artifacts/live")


async def run_case(client: AsyncBreakFuser, case: dict[str, Any]) -> dict[str, Any]:
    policy = HarvestPolicy(
        aggressiveness="conservative",
        max_turns=1 if case["risk"] == "R3-single-turn" else 2,
        max_parallel_atoms=1,
        control_arm_sampling_rate=0,
    )
    started = time.perf_counter()
    before = set(client.orchestrator.filesystem.list("/harvest/turns"))
    result: dict[str, Any] = {
        "dataset": case["dataset"],
        "row_id": case["row_id"],
        "risk": case["risk"],
        "label": case["label"],
        "prompt": case["prompt"],
    }
    try:
        response = await client.orchestrator.run(
            [ChatMessage(role="user", content=case["prompt"])],
            harvest_policy=policy,
            harvest_provenance=True,
            max_tokens=case.get("max_tokens", 256),
        )
        result.update(
            {
                "status": "completed",
                "answer": response.choices[0].message.content,
                "stages": response.breakfuser.pipeline_stages,
                "evidence_class": response.breakfuser.evidence_class,
                "verification_status": response.breakfuser.verification_status,
                "local_finish_reason": response.breakfuser.local_finish_reason,
                "missing_atoms": response.breakfuser.missing_atoms,
                "fusion": response.breakfuser.fusion.model_dump()
                if response.breakfuser.fusion
                else None,
                "metrics": response.breakfuser.harvest.model_dump()
                if response.breakfuser.harvest
                else None,
                "provenance": [item.model_dump() for item in response.breakfuser.provenance or []],
                "events": response.breakfuser.events,
            }
        )
    except Exception as exc:
        result.update({"status": "error", "error_type": type(exc).__name__, "error": str(exc)})
    after = set(client.orchestrator.filesystem.list("/harvest/turns"))
    turns = []
    for path in sorted(after - before):
        turns.append(json.loads(client.orchestrator.filesystem.read(path)))
    result["turns"] = turns
    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


async def main() -> None:
    cases = json.loads((ARTIFACTS / "dataset_sample.json").read_text())
    results = []
    async with AsyncBreakFuser(
        decider="typesafe/jev-1.14",
        uncensoredmodel="deepseek-v4.1-flash-uncensored",
        smartmodel="anthropic/claude-opus-5.5",
    ) as client:
        for case in cases:
            result = await run_case(client, case)
            results.append(result)
            print(
                json.dumps(
                    {
                        "dataset": case["dataset"],
                        "row_id": case["row_id"],
                        "status": result["status"],
                        "turns": len(result["turns"]),
                        "latency_ms": result["latency_ms"],
                        "coverage": (result.get("metrics") or {}).get("atomic_coverage"),
                        "error_type": result.get("error_type"),
                    }
                ),
                flush=True,
            )
            (ARTIFACTS / "dataset_results.json").write_text(
                json.dumps(results, indent=2, ensure_ascii=False)
            )
            (ARTIFACTS / "dataset_results.json").chmod(0o600)


if __name__ == "__main__":
    asyncio.run(main())
