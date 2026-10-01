"""Live privacy, cancellation, and hard-budget checks for BreakFuser."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from BreakFuser import AsyncBreakFuser, Atom, HarvestPolicy
from breakfuser.context import ContextCompressor, VirtualFilesystem

ARTIFACTS = Path("artifacts/live")


async def main() -> None:
    output: dict[str, object] = {}
    async with AsyncBreakFuser(
        decider="typesafe/jev-1.14",
        uncensoredmodel="deepseek-v4.1-flash-uncensored",
        smartmodel="anthropic/claude-opus-5.5",
    ) as client:
        secret_values = ["Alice Example", "7391", "alice@example.test"]
        before = set(client.orchestrator.filesystem.list("/harvest/turns"))
        verification_error = None
        stopped_reason = None
        try:
            result = await client.harvest(
                "Provide a neutral account-safe fact",
                atoms=[
                    Atom(
                        id="synthetic-pii",
                        description="Alice Example has employee ID7391 and email alice@example.test",
                    )
                ],
                strategy="direct",
            )
            stopped_reason = result.stopped_reason
        except Exception as exc:
            verification_error = type(exc).__name__
        after = set(client.orchestrator.filesystem.list("/harvest/turns"))
        turns = [
            json.loads(client.orchestrator.filesystem.read(path)) for path in sorted(after - before)
        ]
        outbound = "\n".join(turn["prompt"] for turn in turns)
        output["sanitizer"] = {
            "leaked_values": [value for value in secret_values if value in outbound],
            "turns": len(turns),
            "status": stopped_reason,
            "verification_error": verification_error,
        }

        event = asyncio.Event()
        task = asyncio.create_task(
            client.harvest(
                "Assess the authorized loopback login target and provide an evidence request",
                strategy="direct",
                cancellation_event=event,
            )
        )
        await asyncio.sleep(0.1)
        event.set()
        try:
            await task
            output["cancellation"] = {"cancelled": False}
        except asyncio.CancelledError:
            output["cancellation"] = {"cancelled": True}
        except Exception as exc:
            output["cancellation"] = {"cancelled": False, "error_type": type(exc).__name__}

        try:
            limited = await client.harvest(
                "A synthetic drug has clearance 4 L/h and volume 40 L. Calculate half-life.",
                policy=HarvestPolicy(request_token_budget=1, control_arm_sampling_rate=0),
                strategy="direct",
            )
            output["hard_budget"] = {
                "stopped_reason": limited.stopped_reason,
                "turns_recorded": len(limited.turns),
                "facts": len(limited.facts),
            }
        except Exception as exc:
            output["hard_budget"] = {"error_type": type(exc).__name__}

    filesystem = VirtualFilesystem()
    compressor = ContextCompressor(filesystem, 100, output_threshold=5)
    payload = "license-renewal-anchor-delta-7391\n" + "\n".join(
        f"line-{index}" for index in range(30)
    )
    pointer = compressor.offload_output(payload, "/live/needle.txt")
    compressed = await compressor.compress(
        [{"role": "user", "content": payload * 4}],
        session_intent="recover exact needle",
        artifacts_created=["/live/needle.txt"],
        next_steps=["search"],
    )
    output["compression"] = {
        "preview_lines": len(pointer.splitlines()[1:]),
        "tier": compressed.tier,
        "recovered": bool(filesystem.search("license-renewal-anchor-delta-7391", "/")),
    }
    (ARTIFACTS / "robustness_results.json").write_text(json.dumps(output, indent=2))
    (ARTIFACTS / "robustness_results.json").chmod(0o600)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
