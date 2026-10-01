"""Deterministic BreakFuser-internal ablations for the v5 modal fusion pipeline."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

from breakfuser.adapters import MockLocalBackend
from breakfuser.errors import VerificationError
from breakfuser.fusion.evidence import EvidenceBlackboard
from breakfuser.fusion.modal_composer import ModalComposer
from breakfuser.fusion.verification import ModalityVerifier
from breakfuser.harvest.models import RefusalClass
from breakfuser.harvest.salvage import TruncationSalvager
from breakfuser.models import BackendResponse, ChatMessage, FusionVerificationMetadata
from breakfuser.orchestrator import Orchestrator

FIXTURES = Path("tests/golden_traces/v5_failures.json")
RESULTS = Path("bench/modal_fusion_results.json")
ARMS = ["without_salvage", "remote_passthrough", "legacy_verification", "serial", "full"]
EXPECTED_TERMS = {
    "truncated_code": ["def moving_average", "def test_normal"],
    "truncated_research": ["archival record", "The main terminological dispute"],
    "exact_json": ['"name":"Ada"', '"count":3', '"enabled":true'],
    "six_line_poem": ["Rain on glass", "Night listens"],
    "pentest_proposal": ["parameterized queries", "127.0.0.1"],
    "empty_length": ["concise factual answer"],
}


class SequenceBackend:
    def __init__(self, responses: list[tuple[str, str]], delay: float = 0.02) -> None:
        self.responses = responses
        self.delay = delay
        self.calls = 0

    async def complete(self, messages, model, **kwargs) -> BackendResponse:
        await asyncio.sleep(self.delay)
        text, finish = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return BackendResponse(content=text, finish_reason=finish, model=model)


class DelayedLocal(MockLocalBackend):
    async def complete(self, messages, model, **kwargs) -> BackendResponse:
        await asyncio.sleep(0.02)
        return await super().complete(messages, model, **kwargs)


def _legacy_verification_metadata(
    board: EvidenceBlackboard, passed: bool
) -> FusionVerificationMetadata:
    return FusionVerificationMetadata(
        primary_origin_class="remote_hybrid_composed" if board.remote else "local_autonomous",
        provider_outcome=board.provider_outcome,
        deterministic_validity="not_applicable",
        provenance_attribution="partially_attributed",
        external_corroboration="single_source_remote"
        if board.remote
        else "uncorroborated_inference",
        task_completion_status="complete" if passed else "failed",
        composition_mode=board.composition_mode,
        root_cause_flags=[] if passed else ["semantic_audit_failed"],
    )


async def run_fixture(name: str, arm: str, settings) -> dict[str, Any]:
    case = json.loads(await asyncio.to_thread(FIXTURES.read_text))[name]
    responses = (
        [(item["text"], item["finish_reason"]) for item in case["responses"]]
        if "responses" in case
        else [(case["response"], case["finish_reason"])]
    )
    smart = SequenceBackend(responses)
    local = DelayedLocal()
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)
    started = time.perf_counter()
    with ExitStack() as stack:
        if arm == "serial":
            orchestrator._linear_pipeline.acquisition.parallel = False
        elif arm == "without_salvage":
            original = TruncationSalvager.salvage

            def no_salvage(self, turn):
                if turn.quality != RefusalClass.NONE:
                    return None
                return original(self, turn)

            stack.enter_context(patch.object(TruncationSalvager, "salvage", no_salvage))
        elif arm == "remote_passthrough":
            from breakfuser.fusion.domain import DomainRouter
            from breakfuser.fusion.evidence import CompositionMode

            original_compose = ModalComposer.compose

            async def remote_compose(self, board: EvidenceBlackboard, **kwargs):
                contract = board.contract or DomainRouter().route(board.question)
                if not any(span.salvaged for span in board.remote):
                    for span in board.remote:
                        answer = self._clean_remote(span.text, contract) if span.complete else ""
                        if answer and not contract.missing_atoms(answer):
                            return self._bundle(
                                answer, board, contract, CompositionMode.PASSTHROUGH
                            )
                return await original_compose(self, board, **kwargs)

            stack.enter_context(patch.object(ModalComposer, "compose", remote_compose))
        elif arm == "legacy_verification":

            async def legacy_verify(self, candidate: str, board: EvidenceBlackboard):
                facts = [document.excerpt for document in board.documents] + [
                    span.text for span in board.remote
                ]
                try:
                    answer, report = await self.factual.verify_and_repair(
                        candidate, facts, original_question=board.question
                    )
                    passed = report.passed
                except VerificationError:
                    answer, passed = candidate, False
                return answer, _legacy_verification_metadata(board, passed)

            stack.enter_context(patch.object(ModalityVerifier, "verify_and_repair", legacy_verify))
        response = await orchestrator.run([ChatMessage(role="user", content=case["question"])])
    latency_ms = (time.perf_counter() - started) * 1000
    answer = response.choices[0].message.content
    fusion = response.breakfuser.fusion
    await orchestrator.tasks.cancel_all()
    return {
        "case": name,
        "arm": arm,
        "substantive": bool(answer.strip()) and "No verified response" not in answer,
        "task_success": all(term in answer for term in EXPECTED_TERMS[name]),
        "verification_status": response.breakfuser.verification_status,
        "deterministic_validity": fusion.deterministic_validity if fusion else "not_applicable",
        "task_completion_status": fusion.task_completion_status if fusion else "failed",
        "composition_mode": fusion.composition_mode if fusion else "unknown",
        "provider_outcome": fusion.provider_outcome if fusion else "unknown",
        "provenance_attribution": fusion.provenance_attribution if fusion else "unknown",
        "external_corroboration": fusion.external_corroboration if fusion else "unknown",
        "salvage_yield": fusion.salvage_yield if fusion else 0,
        "local_calls": len(local.calls),
        "remote_turns": response.breakfuser.harvest.turns_used
        if response.breakfuser.harvest
        else 0,
        "request_tokens": response.usage.total_tokens,
        "latency_ms": round(latency_ms, 3),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        selected = [result for result in results if result["arm"] == arm]
        if not selected:
            continue
        summary[arm] = {
            "cases": len(selected),
            "substantive": sum(result["substantive"] for result in selected),
            "task_success": sum(result["task_success"] for result in selected),
            "verification_passed": sum(
                result["verification_status"] == "passed" for result in selected
            ),
            "mean_salvage_yield": round(
                sum(result["salvage_yield"] for result in selected) / len(selected), 4
            ),
            "median_latency_ms": sorted(result["latency_ms"] for result in selected)[
                len(selected) // 2
            ],
        }
    return summary


async def main() -> None:
    from breakfuser.config import Settings

    settings = Settings.model_validate(
        {
            "mode": "mock",
            "models": {"decider": "mock-jev", "local": "mock-local", "smart": "mock-smart"},
            "sanitizer": {"key": "modal-ablation-key"},
            "harvest": {"control_arm_sampling_rate": 0, "max_turns": 2},
        }
    )
    results = [await run_fixture(name, arm, settings) for name in EXPECTED_TERMS for arm in ARMS]
    output = {"results": results, "summary": summarize(results)}
    await asyncio.to_thread(RESULTS.write_text, json.dumps(output, indent=2))
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
