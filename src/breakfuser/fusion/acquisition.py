"""Parallel speculative acquisition with isolated branch results."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from breakfuser.config import HarvestPolicy
from breakfuser.fusion.domain import ResponseContract
from breakfuser.fusion.evidence import EvidenceBlackboard, EvidenceSpan
from breakfuser.harvest.models import Atom, HarvestExecutionOptions, HarvestResult
from breakfuser.models import ChatMessage, HarvestMetrics, ToolCall

if TYPE_CHECKING:
    from breakfuser.budget import BudgetManager
    from breakfuser.orchestrator import Orchestrator


@dataclass
class _BranchResult:
    value: Any
    elapsed_ms: float


class SpeculativeAcquisition:
    def __init__(self, orchestrator: Orchestrator, *, parallel: bool = True) -> None:
        self.orchestrator = orchestrator
        self.parallel = parallel

    @staticmethod
    def _empty_harvest(question: str) -> HarvestResult:
        return HarvestResult(
            answer="",
            facts=[],
            turns=[],
            metrics=HarvestMetrics(atomic_coverage=0),
            provenance=[],
            atoms=[Atom(id="linear-evidence", description=question)],
            stopped_reason="error",
        )

    @staticmethod
    async def _timed(call: Callable[[], Awaitable[Any]]) -> _BranchResult:
        started = time.perf_counter()
        value = await call()
        return _BranchResult(value=value, elapsed_ms=(time.perf_counter() - started) * 1000)

    @staticmethod
    def _merge(
        result: Any,
        name: str,
        default: Any,
        board: EvidenceBlackboard,
    ) -> Any:
        if isinstance(result, asyncio.CancelledError):
            raise result
        if isinstance(result, Exception):
            board.branch_errors[name] = type(result).__name__
            if name == "remote":
                board.provider_outcome = "error"
            return default
        if not isinstance(result, _BranchResult):
            raise TypeError(f"Invalid {name} branch result")
        board.stage_timings_ms[name] = result.elapsed_ms
        return result.value

    async def acquire(
        self,
        messages: list[ChatMessage],
        contract: ResponseContract,
        budget: BudgetManager,
        *,
        draft: Callable[
            [list[ChatMessage], BudgetManager, int | None, float, dict[str, Any] | None],
            Awaitable[tuple[str, str, list[ToolCall]]],
        ],
        harvest_policy: HarvestPolicy | None,
        max_tokens: int | None,
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> EvidenceBlackboard:
        question = next(
            (message.content for message in reversed(messages) if message.role == "user"), ""
        )
        board = EvidenceBlackboard(question=question, contract=contract)
        contract_messages = [
            ChatMessage(
                role="system",
                content=(
                    f"{contract.completion_directive}\nOutput shape: {contract.output_shape}.\n"
                    f"Required atoms: {', '.join(contract.required_atoms) or 'none'}."
                ),
            ),
            *messages,
        ]

        async def retrieve() -> _BranchResult:
            return await self._timed(lambda: self.orchestrator.retrieval.retrieve(question))

        async def local() -> _BranchResult:
            return await self._timed(
                lambda: draft(contract_messages, budget, max_tokens, temperature, extra)
            )

        async def remote() -> _BranchResult:
            policy = (harvest_policy or self.orchestrator.settings.harvest).model_copy(
                update={"max_turns": 2, "max_parallel_atoms": 1}
            )
            initial_strategy = (
                "output_shape_coercion"
                if contract.output_shape in {"exact_json", "evidence_proposal"}
                else "direct"
            )
            return await self._timed(
                lambda: self.orchestrator._harvest_engine(budget, policy, verify=False).harvest(
                    question,
                    atoms=[Atom(id="linear-evidence", description=question)],
                    execution=HarvestExecutionOptions(
                        recompose=False,
                        initial_strategy=initial_strategy,
                        repair_targets=contract.required_atoms,
                        domain=contract.domain.value,
                        output_shape=contract.output_shape,
                        output_tokens=min(
                            contract.remote_output_tokens,
                            self.orchestrator.settings.transport.smart_output_limit(),
                        ),
                    ),
                )
            )

        if self.parallel:
            retrieved, drafted, harvested = await asyncio.gather(
                retrieve(), local(), remote(), return_exceptions=True
            )
        else:
            results: list[Any] = []
            for branch in (retrieve, local, remote):
                try:
                    results.append(await branch())
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    results.append(exc)
            retrieved, drafted, harvested = results
        board.documents = self._merge(retrieved, "retrieval", [], board)
        draft_result = self._merge(drafted, "local", ("", "error", []), board)
        harvest = self._merge(harvested, "remote", self._empty_harvest(question), board)
        local_text, local_finish_reason, local_tool_calls = draft_result
        board.tool_calls = list(local_tool_calls)
        board.local = (
            EvidenceSpan(
                source_id="local-draft",
                origin="local",
                text=local_text,
                complete=local_finish_reason != "length",
                salvaged=local_finish_reason == "length",
                tail_anchor=local_text[-150:],
            )
            if local_text
            else None
        )
        board.local_finish_reason = local_finish_reason
        board.harvest = harvest
        board.remote = list(harvest.evidence_spans)
        return board
