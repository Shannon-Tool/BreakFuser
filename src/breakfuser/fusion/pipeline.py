"""Retrieval, local draft, bounded remote evidence, composition, and verification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from breakfuser.adapters import estimate_tokens
from breakfuser.config import HarvestPolicy
from breakfuser.deterministic import deterministic_answer, is_small_talk
from breakfuser.errors import VerificationError as FusionVerificationError
from breakfuser.fusion.acquisition import SpeculativeAcquisition
from breakfuser.fusion.composer import EvidenceClass
from breakfuser.fusion.domain import DomainRouter
from breakfuser.fusion.evidence import EvidenceBlackboard, EvidenceSpan
from breakfuser.fusion.modal_composer import ModalComposer
from breakfuser.fusion.outcomes import OutcomeKind, ProviderOutcome
from breakfuser.fusion.verification import ModalityVerifier
from breakfuser.harvest.models import Atom, HarvestResult
from breakfuser.models import (
    ChatCompletion,
    ChatMessage,
    ClaimProvenance,
    CompletionChoice,
    ResponseMessage,
    ResponseMetadata,
    ToolCall,
    Usage,
)
from breakfuser.telemetry import Trace

if TYPE_CHECKING:
    from breakfuser.orchestrator import Orchestrator


LINEAR_STAGES = [
    "document_retrieval",
    "local_draft",
    "remote_evidence",
    "fusion_composition",
    "verify_after",
]


class LinearFusionPipeline:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self.composer = ModalComposer(
            orchestrator.local,
            orchestrator.settings.models.local,
            orchestrator.settings.transport.local_output_limit(),
        )
        self.modality_verifier = ModalityVerifier(
            decider=orchestrator.decider,
            local=orchestrator.local,
            model=orchestrator.settings.models.local,
            factual=orchestrator.verifier,
            max_output_tokens=orchestrator.settings.transport.local_output_limit(),
        )
        self.acquisition = SpeculativeAcquisition(orchestrator)

    @staticmethod
    def _empty_harvest(question: str) -> HarvestResult:
        from breakfuser.models import HarvestMetrics

        return HarvestResult(
            answer="",
            facts=[],
            turns=[],
            metrics=HarvestMetrics(atomic_coverage=0),
            provenance=[],
            atoms=[Atom(id="linear-evidence", description=question)],
            stopped_reason="not_required",
        )

    async def _draft(
        self,
        messages: list[ChatMessage],
        budget: Any,
        max_tokens: int | None,
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> tuple[str, str, list[ToolCall]]:
        local_response = await self.orchestrator._local_complete(
            messages,
            self.orchestrator.settings.models.local,
            max_tokens=max_tokens,
            temperature=temperature,
            extra=extra,
        )
        budget.charge(
            local_response.usage.total_tokens,
            gpu_usd=local_response.raw.get("cost", 0) or 0,
        )
        outcome = ProviderOutcome.from_backend(local_response)
        if outcome.kind not in {OutcomeKind.PARTIAL, OutcomeKind.EMPTY_LENGTH}:
            return outcome.text, local_response.finish_reason, local_response.tool_calls

        continued_messages = messages.copy()
        if outcome.kind is OutcomeKind.PARTIAL:
            continued_messages.extend(
                [
                    ChatMessage(role="assistant", content=outcome.text),
                    ChatMessage(
                        role="user",
                        content=(
                            "Continue exactly from the partial answer without repeating or adding analysis. "
                            "Complete the response in at most 128 tokens."
                        ),
                    ),
                ]
            )
        else:
            continued_messages.append(
                ChatMessage(
                    role="user",
                    content="Provide the final answer only, in at most 128 tokens, without analysis.",
                )
            )
        continued = await self.orchestrator._local_complete(
            continued_messages,
            self.orchestrator.settings.models.local,
            max_tokens=min(128, self.orchestrator.settings.transport.local_output_limit()),
            temperature=temperature,
            extra=extra,
        )
        budget.charge(
            continued.usage.total_tokens,
            gpu_usd=continued.raw.get("cost", 0) or 0,
        )
        return outcome.text + continued.content, continued.finish_reason, continued.tool_calls

    async def run(
        self,
        messages: list[ChatMessage],
        *,
        harvest_policy: HarvestPolicy | None = None,
        harvest_provenance: bool = False,
        max_tokens: int | None = None,
        temperature: float = 0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        skill_ids: list[str] | None = None,
    ) -> ChatCompletion:
        trace = Trace()
        for stage in LINEAR_STAGES:
            trace.record(stage, wired=True)
        question = next(
            (message.content for message in reversed(messages) if message.role == "user"), ""
        )
        budget = self.orchestrator._budget_root.new_request()
        for info in await self.orchestrator.tasks.collect_completed():
            self.orchestrator.filesystem.write(
                f"/background/{info.id}.txt", info.result or info.error or ""
            )

        raw_messages = [message.model_dump(exclude_none=True) for message in messages]
        compressed = await self.orchestrator.compressor.compress(
            raw_messages,
            session_intent=question,
            artifacts_created=self.orchestrator.filesystem.list("/harvest"),
            next_steps=["Draft locally", "Gather one evidence response", "Compose and verify"],
            summarizer=self.orchestrator._summarize,
        )
        active_messages = [ChatMessage.model_validate(message) for message in compressed.messages]
        if skill_ids:
            try:
                selected_skills = [self.orchestrator.skills.load(name) for name in skill_ids]
            except KeyError as exc:
                raise ValueError(f"Unknown skill selection: {exc}") from exc
            active_messages.insert(
                0,
                ChatMessage(
                    role="system",
                    content="Selected local skills:\n" + "\n\n".join(selected_skills),
                ),
            )
        trace.record("context_compression", tier=compressed.tier)
        generation_extra: dict[str, Any] = {}
        if tools is not None:
            generation_extra["tools"] = tools
        if tool_choice is not None:
            generation_extra["tool_choice"] = tool_choice
        if response_format is not None:
            generation_extra["response_format"] = response_format

        from breakfuser.medical import medical_deterministic_answer

        deterministic = deterministic_answer(question) or medical_deterministic_answer(question)
        contract = DomainRouter().route(question)
        harvest: HarvestResult | None = None
        local_draft = ""
        local_finish_reason = "stop"
        provenance: list[ClaimProvenance] | None = None
        missing_atoms: list[str] = []
        tool_calls: list[ToolCall] = []
        if deterministic is not None and not generation_extra:
            answer = f"Deterministic result: {deterministic}"
            evidence_class = EvidenceClass.DETERMINISTIC.value
            provenance = []
            verification_required = True
            board = EvidenceBlackboard(
                question=question,
                contract=contract,
                composition_mode="passthrough",
            )
        else:
            if is_small_talk(question) and not generation_extra and not skill_ids:
                local_draft, local_finish_reason, draft_tool_calls = await self._draft(
                    active_messages, budget, max_tokens, temperature, generation_extra
                )
                harvest = self._empty_harvest(question)
                board = EvidenceBlackboard(
                    question=question,
                    contract=contract,
                    tool_calls=draft_tool_calls,
                    local=EvidenceSpan(
                        source_id="local-draft",
                        origin="local",
                        text=local_draft,
                        complete=local_finish_reason != "length",
                        salvaged=local_finish_reason == "length",
                        tail_anchor=local_draft[-150:],
                    )
                    if local_draft
                    else None,
                )
            else:
                board = await self.acquisition.acquire(
                    active_messages,
                    contract,
                    budget,
                    draft=self._draft,
                    harvest_policy=harvest_policy,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    extra=generation_extra,
                )
                harvest = board.harvest or self._empty_harvest(question)
                local_draft = board.local.text if board.local else ""
                local_finish_reason = board.local_finish_reason
            bundle = await self.composer.compose(
                board,
                messages=active_messages,
                budget=budget,
                extra=generation_extra,
            )
            tool_calls = bundle.tool_calls or board.tool_calls
            board.composition_mode = bundle.composition_mode.value
            board.provenance = bundle.provenance
            if board.provider_outcome == "error":
                pass
            elif not harvest.turns:
                board.provider_outcome = "not_invoked"
            elif not harvest.evidence_spans:
                board.provider_outcome = "hard_refused"
            elif any(span.salvaged for span in harvest.evidence_spans):
                board.provider_outcome = "accepted_salvaged_truncation"
            elif any(
                turn.strategy_id in {"refusal_repair", "crescendo", "context_reset"}
                for turn in harvest.turns
            ):
                board.provider_outcome = "repaired_after_refusal"
            else:
                board.provider_outcome = "accepted_complete"
            trace.record("fusion_composition_mode", mode=bundle.composition_mode.value)
            answer = bundle.answer
            evidence_class = bundle.evidence_class.value
            provenance = bundle.provenance if harvest_provenance else None
            verification_required = bundle.verification_required
            missing_atoms = bundle.missing_atoms

        verification_status = "not_required"
        fusion = None
        if tool_calls:
            fusion = self.modality_verifier.verify_tool_calls(board, tool_calls, tools or [])
            verification_status = (
                "passed" if fusion.deterministic_validity == "passed" else "limited"
            )
            trace.record(
                "tool_call_validation",
                passed=verification_status == "passed",
                errors=fusion.root_cause_flags,
            )
        elif verification_required:
            try:
                answer, fusion = await self.modality_verifier.verify_and_repair(answer, board)
                verification_status = (
                    "passed"
                    if fusion.task_completion_status == "complete" and not fusion.root_cause_flags
                    else "limited"
                )
                trace.record(
                    "verification",
                    passed=verification_status == "passed",
                    deterministic=fusion.deterministic_validity,
                    completion=fusion.task_completion_status,
                )
            except FusionVerificationError as exc:
                verification_status = "limited"
                trace.record("verification", passed=False, error=type(exc).__name__)
        else:
            trace.record("verification", passed=True, external_facts="not_required")
        provenance = board.provenance if harvest_provenance else None

        if missing_atoms or (
            local_finish_reason == "length"
            and evidence_class == EvidenceClass.LOCAL_INFERENCE.value
        ):
            verification_status = "limited"
        usage_tokens = budget.snapshot.request_tokens or estimate_tokens(
            question
        ) + estimate_tokens(answer)
        metadata = ResponseMetadata(
            trace_id=trace.id,
            pipeline_stages=LINEAR_STAGES,
            artifacts=self.orchestrator.filesystem.list("/"),
            harvest=(
                harvest.metrics if harvest and harvest.stopped_reason != "not_required" else None
            ),
            provenance=provenance,
            events=trace.events,
            evidence_class=evidence_class,
            verification_status=verification_status,
            local_finish_reason=local_finish_reason,
            missing_atoms=missing_atoms,
            fusion=fusion,
        )
        return ChatCompletion(
            model=self.orchestrator.settings.models.local,
            choices=[
                CompletionChoice(
                    message=ResponseMessage(content=answer, tool_calls=tool_calls),
                    finish_reason="tool_calls" if tool_calls else "stop",
                )
            ],
            usage=Usage(
                prompt_tokens=estimate_tokens(question),
                completion_tokens=estimate_tokens(answer),
                total_tokens=usage_tokens,
            ),
            breakfuser=metadata,
        )
