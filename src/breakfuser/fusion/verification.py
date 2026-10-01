"""Modality-gated verification with externally anchored, monotonic repair."""

from __future__ import annotations

from typing import Any

from breakfuser.adapters import ChatBackend
from breakfuser.decider import Decider
from breakfuser.fusion.composer import _supports_claim
from breakfuser.fusion.domain import Domain, DomainRouter, ResponseContract, VerificationMode
from breakfuser.fusion.evidence import CompositionMode, EvidenceBlackboard
from breakfuser.fusion.validation import (
    DeterministicValidation,
    DeterministicValidatorSuite,
    validate_tool_calls,
)
from breakfuser.models import ChatMessage, ClaimProvenance, FusionVerificationMetadata, ToolCall
from breakfuser.security import Verifier, extract_claims


class ModalityVerifier:
    def __init__(
        self,
        *,
        decider: Decider,
        local: ChatBackend,
        model: str,
        factual: Verifier | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self.local = local
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.factual = factual or Verifier(
            decider, local, model, max_output_tokens=max_output_tokens
        )
        self.validators = DeterministicValidatorSuite()

    @staticmethod
    def _facts(board: EvidenceBlackboard) -> list[str]:
        values = [document.excerpt for document in board.documents]
        values.extend(span.text for span in board.remote)
        return list(dict.fromkeys(value for value in values if value.strip()))

    @staticmethod
    def _improved(
        original_missing: list[str],
        original_validation: DeterministicValidation,
        candidate_missing: list[str],
        candidate_validation: DeterministicValidation,
    ) -> bool:
        if original_validation.passed and not candidate_validation.passed:
            return False
        if len(candidate_missing) < len(original_missing):
            return True
        return (
            not original_validation.passed
            and candidate_validation.passed
            and len(candidate_missing) <= len(original_missing)
        )

    async def _repair(
        self,
        candidate: str,
        board: EvidenceBlackboard,
        contract: ResponseContract,
        errors: list[str],
    ) -> str:
        response = await self.local.complete(
            [
                ChatMessage(
                    role="user",
                    content=(
                        "[BREAKFUSER_SYNTHESIS]\nEvidence and candidate material:\n"
                        + "\n".join(self._facts(board))
                        + f"\nOriginal question:\n{board.question}"
                        + f"\nCandidate:\n{candidate}\nConcrete validation errors:\n"
                        + "\n".join(errors)
                        + "\nRepair only the identified omissions or validation errors."
                    ),
                )
            ],
            self.model,
            max_tokens=self.max_output_tokens,
        )
        return response.content.strip() or candidate

    def _metadata(
        self,
        candidate: str,
        board: EvidenceBlackboard,
        contract: ResponseContract,
        validation: DeterministicValidation,
        missing: list[str],
        flags: list[str],
    ) -> FusionVerificationMetadata:
        mode = board.composition_mode
        if contract.domain == Domain.DETERMINISTIC:
            origin = "deterministic_solver"
        elif mode == CompositionMode.PASSTHROUGH.value:
            origin = "remote_passthrough"
        elif board.remote:
            origin = "remote_hybrid_composed"
        elif board.documents:
            origin = "retrieved_document_grounded"
        elif candidate:
            origin = "local_autonomous"
        else:
            origin = "no_usable_output"

        if contract.verification_mode in {
            VerificationMode.DETERMINISTIC,
            VerificationMode.STRUCTURAL,
        }:
            attribution = "not_applicable"
        elif not board.provenance:
            attribution = "local_unattributed" if board.local else "partially_attributed"
        else:
            linked = sum(not item.inferred for item in board.provenance)
            ratio = linked / len(board.provenance)
            attribution = "fully_attributed" if ratio >= 0.95 else "partially_attributed"

        if contract.verification_mode in {
            VerificationMode.DETERMINISTIC,
            VerificationMode.STRUCTURAL,
        }:
            corroboration = "not_applicable"
        elif (
            board.tool_observations
            or any(item.turn_ids and item.document_ids for item in board.provenance)
            or any(item.document_ids for item in board.provenance)
        ):
            corroboration = "independently_corroborated"
        elif board.remote:
            corroboration = "single_source_remote"
        else:
            corroboration = "uncorroborated_inference"

        if (
            not validation.passed
            and validation.status == "failed"
            or "semantic_audit_failed" in flags
        ):
            completion = "failed"
        elif missing:
            completion = "limited_missing_atoms"
        elif (
            board.remote
            and all(not span.complete for span in board.remote)
            or board.local
            and not board.local.complete
            and not board.remote
        ):
            completion = "budget_bounded_partial"
        else:
            completion = "complete"
        provider_outcome = board.provider_outcome
        if provider_outcome == "not_invoked" and board.remote:
            provider_outcome = (
                "accepted_salvaged_truncation"
                if any(span.salvaged for span in board.remote)
                else "accepted_complete"
            )
        remote_characters = (
            sum(len(turn.desanitized_response) for turn in board.harvest.turns)
            if board.harvest
            else 0
        )
        salvaged_characters = sum(len(span.text) for span in board.remote if span.salvaged)
        return FusionVerificationMetadata(
            primary_origin_class=origin,
            provider_outcome=provider_outcome,
            deterministic_validity=validation.status,
            provenance_attribution=attribution,
            external_corroboration=corroboration,
            task_completion_status=completion,
            composition_mode=mode or "not_applicable",
            root_cause_flags=flags,
            salvage_yield=(salvaged_characters / remote_characters if remote_characters else 0),
            remote_characters=remote_characters,
            salvaged_characters=salvaged_characters,
            stage_timings_ms=board.stage_timings_ms,
        )

    def verify_tool_calls(
        self,
        board: EvidenceBlackboard,
        tool_calls: list[ToolCall],
        tools: list[dict[str, Any]],
    ) -> FusionVerificationMetadata:
        errors = validate_tool_calls(tool_calls, tools)
        validation = DeterministicValidation(status="failed" if errors else "passed", errors=errors)
        contract = board.contract or DomainRouter().route(board.question)
        return self._metadata("", board, contract, validation, [], [*board.branch_errors, *errors])

    async def verify_and_repair(
        self, candidate: str, board: EvidenceBlackboard
    ) -> tuple[str, FusionVerificationMetadata]:
        contract = board.contract or DomainRouter().route(board.question)
        validation = self.validators.validate(candidate, contract)
        missing = contract.missing_atoms(candidate)
        flags: list[str] = list(board.branch_errors)

        if validation.status == "failed":
            repaired = await self._repair(candidate, board, contract, validation.errors)
            repaired_validation = self.validators.validate(repaired, contract)
            repaired_missing = contract.missing_atoms(repaired)
            if self._improved(missing, validation, repaired_missing, repaired_validation):
                candidate, validation, missing = repaired, repaired_validation, repaired_missing
            else:
                flags.append("deterministic_validation_failed")
        elif contract.verification_mode == VerificationMode.FACTUAL:
            report = await self.factual.audit(
                candidate, self._facts(board), original_question=board.question
            )
            if not report.passed:
                repaired = await self._repair(
                    candidate,
                    board,
                    contract,
                    [*report.omissions, *report.contradictions],
                )
                repaired_report = await self.factual.audit(
                    repaired, self._facts(board), original_question=board.question
                )
                repaired_validation = self.validators.validate(repaired, contract)
                repaired_missing = contract.missing_atoms(repaired)
                if repaired_report.passed and self._improved(
                    missing, validation, repaired_missing, repaired_validation
                ):
                    candidate, validation, missing = repaired, repaired_validation, repaired_missing
                else:
                    flags.append("semantic_audit_failed")

        board.provenance = (
            []
            if contract.domain == Domain.DETERMINISTIC
            else [
                ClaimProvenance(
                    claim=claim,
                    turn_ids=[
                        span.source_id for span in board.remote if _supports_claim(claim, span.text)
                    ],
                    document_ids=[
                        document.id
                        for document in board.documents
                        if _supports_claim(claim, document.excerpt)
                    ],
                    inferred=not any(_supports_claim(claim, span.text) for span in board.remote)
                    and not any(
                        _supports_claim(claim, document.excerpt) for document in board.documents
                    ),
                )
                for claim in extract_claims(candidate)
            ]
        )
        return candidate, self._metadata(candidate, board, contract, validation, missing, flags)
