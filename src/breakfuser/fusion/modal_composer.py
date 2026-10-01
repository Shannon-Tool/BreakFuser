"""Modal composition preserving complete candidates and salvaged source spans."""

from __future__ import annotations

import re
from typing import Any

from breakfuser.adapters import ChatBackend
from breakfuser.budget import BudgetManager
from breakfuser.errors import AdapterError
from breakfuser.fusion.composer import EvidenceBundle, EvidenceClass, _supports_claim
from breakfuser.fusion.domain import Domain, DomainRouter, ResponseContract
from breakfuser.fusion.evidence import CompositionMode, EvidenceBlackboard, EvidenceSpan
from breakfuser.fusion.validation import DeterministicValidatorSuite
from breakfuser.models import ChatMessage, ClaimProvenance, ToolCall
from breakfuser.security import extract_claims


class ModalComposer:
    def __init__(
        self, local: ChatBackend, model: str, max_output_tokens: int | None = None
    ) -> None:
        self.local = local
        self.model = model
        self.max_output_tokens = max_output_tokens

    @staticmethod
    def _clean_remote(text: str, contract: ResponseContract) -> str:
        answer = text.strip()
        if contract.format_envelope.strip_markdown_fences:
            match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n?```", answer, re.S | re.I)
            if match:
                answer = match.group(1).strip()
        return answer

    @staticmethod
    def _assemble(spans: list[EvidenceSpan]) -> str:
        parts: list[str] = []
        previous: EvidenceSpan | None = None
        for span in spans:
            text = span.text.strip()
            if not text:
                continue
            if previous and previous.salvaged and not previous.complete:
                is_code = bool(
                    re.search(r"(?:```|^(?:async\s+def|def|class)\s+\w+)", previous.text, re.M)
                )
                if not is_code and previous.tail_anchor:
                    text = previous.tail_anchor + text
            if not parts or text not in parts[-1]:
                parts.append(text)
            previous = span
        return "\n\n".join(parts).strip()

    @staticmethod
    def _facts(board: EvidenceBlackboard) -> list[str]:
        values = [document.excerpt.strip() for document in board.documents]
        values.extend(span.text.strip() for span in board.remote)
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _provenance(answer: str, board: EvidenceBlackboard) -> list[ClaimProvenance]:
        provenance: list[ClaimProvenance] = []
        for claim in extract_claims(answer):
            turn_ids = [
                span.source_id for span in board.remote if _supports_claim(claim, span.text)
            ]
            document_ids = [
                document.id
                for document in board.documents
                if _supports_claim(claim, document.excerpt)
            ]
            provenance.append(
                ClaimProvenance(
                    claim=claim,
                    turn_ids=list(dict.fromkeys(turn_ids)),
                    document_ids=list(dict.fromkeys(document_ids)),
                    inferred=not turn_ids and not document_ids,
                )
            )
        return provenance

    def _bundle(
        self,
        answer: str,
        board: EvidenceBlackboard,
        contract: ResponseContract,
        mode: CompositionMode,
    ) -> EvidenceBundle:
        evidence_class = (
            EvidenceClass.VERIFIED_REMOTE
            if mode == CompositionMode.PASSTHROUGH or not board.documents
            else EvidenceClass.RETRIEVED_DOCUMENT
        )
        return EvidenceBundle(
            answer=answer,
            evidence_class=evidence_class,
            facts=self._facts(board),
            provenance=self._provenance(answer, board),
            verification_required=True,
            missing_atoms=contract.missing_atoms(answer),
            composition_mode=mode,
        )

    def _local_fallback(
        self, answer: str, board: EvidenceBlackboard, contract: ResponseContract
    ) -> EvidenceBundle:
        return EvidenceBundle(
            answer=answer,
            evidence_class=EvidenceClass.LOCAL_INFERENCE,
            facts=[document.excerpt for document in board.documents],
            provenance=[
                ClaimProvenance(claim=claim, inferred=True) for claim in extract_claims(answer)
            ],
            verification_required=True,
            missing_atoms=contract.missing_atoms(answer),
            composition_mode=CompositionMode.LOCAL_FALLBACK,
        )

    async def compose(
        self,
        board: EvidenceBlackboard,
        *,
        messages: list[ChatMessage] | None = None,
        budget: BudgetManager | None = None,
        extra: dict[str, Any] | None = None,
    ) -> EvidenceBundle:
        contract = board.contract or DomainRouter().route(board.question)
        remote = [span for span in board.remote if span.text.strip()]
        local_text = board.local.text.strip() if board.local else ""
        facts = self._facts(board)

        if not facts:
            if local_text or board.tool_calls:
                bundle = self._local_fallback(local_text, board, contract)
                bundle.tool_calls = list(board.tool_calls)
                return bundle
            answer = (
                "No verified response was produced. The provider refused, returned no content, "
                "or exhausted the response limit before supplying a usable answer."
            )
            return EvidenceBundle(
                answer=answer,
                evidence_class=EvidenceClass.NO_VERIFIED_RESPONSE,
                provenance=[ClaimProvenance(claim=answer, inferred=True)],
                verification_required=False,
                missing_atoms=contract.missing_atoms(answer),
                composition_mode=CompositionMode.EMPTY,
            )

        conversation = "\n".join(f"{message.role}: {message.content}" for message in messages or [])
        assembled = self._assemble(remote)
        synthesis_facts = list(
            dict.fromkeys(
                [*(document.excerpt.strip() for document in board.documents), assembled]
                if assembled
                else facts
            )
        )
        documents = [document.excerpt.strip() for document in board.documents]
        remote_material = [assembled] if assembled else [span.text for span in remote]
        response_tool_calls: list[ToolCall] = []
        try:
            response = await self.local.complete(
                [
                    ChatMessage(
                        role="user",
                        content=contract.compose_prompt(
                            board.question,
                            synthesis_facts,
                            conversation=conversation,
                            local_draft=local_text,
                            documents=documents,
                            remote_evidence=remote_material,
                        ),
                    )
                ],
                self.model,
                max_tokens=self.max_output_tokens,
                extra=extra,
            )
            if budget is not None:
                budget.charge(
                    response.usage.total_tokens,
                    gpu_usd=response.raw.get("cost", 0) or 0,
                )
            answer = self._clean_remote(response.content, contract)
            response_tool_calls = response.tool_calls
        except AdapterError as exc:
            board.branch_errors["local_synthesis"] = type(exc).__name__
            answer = ""
        if response_tool_calls:
            return self._bundle(
                answer, board, contract, CompositionMode.TARGETED_SYNTHESIS
            ).model_copy(update={"tool_calls": response_tool_calls})
        validator = DeterministicValidatorSuite()
        if answer:
            local_validation = validator.validate(answer, contract)
            assembled_validation = validator.validate(assembled, contract) if assembled else None
            if (
                local_validation.status != "failed"
                or assembled_validation is None
                or assembled_validation.status == "failed"
            ):
                return self._bundle(answer, board, contract, CompositionMode.TARGETED_SYNTHESIS)

        if assembled:
            mode = (
                CompositionMode.ARTIFACT_ASSEMBLY
                if contract.domain in {Domain.CODING, Domain.PENTEST}
                or contract.output_shape == "exact_json"
                else CompositionMode.TARGETED_SYNTHESIS
            )
            return self._bundle(assembled, board, contract, mode)
        if local_text:
            return self._local_fallback(local_text, board, contract)
        answer = "No verified response was produced. The local response owner returned no content."
        return EvidenceBundle(
            answer=answer,
            evidence_class=EvidenceClass.NO_VERIFIED_RESPONSE,
            provenance=[ClaimProvenance(claim=answer, inferred=True)],
            verification_required=False,
            missing_atoms=contract.missing_atoms(answer),
            composition_mode=CompositionMode.EMPTY,
        )
