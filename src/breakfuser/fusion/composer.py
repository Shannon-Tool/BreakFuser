"""Structured evidence composition with explicit inference/provenance boundaries."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from breakfuser.adapters import ChatBackend
from breakfuser.fusion.domain import ResponseContract
from breakfuser.fusion.evidence import CompositionMode
from breakfuser.harvest.models import HarvestResult
from breakfuser.models import ChatMessage, ClaimProvenance, ToolCall
from breakfuser.retrieval.models import SourceDocument
from breakfuser.security import extract_claims


def _supports_claim(claim: str, evidence_text: str) -> bool:
    if evidence_text.strip() and (evidence_text.strip() in claim or claim in evidence_text.strip()):
        return True
    claim_words = set(re.findall(r"[a-z0-9]+", claim.lower()))
    evidence_words = set(re.findall(r"[a-z0-9]+", evidence_text.lower()))
    return bool(claim_words) and len(claim_words & evidence_words) / len(claim_words) >= 0.6


class EvidenceClass(StrEnum):
    DETERMINISTIC = "deterministic"
    VERIFIED_REMOTE = "verified_remote"
    RETRIEVED_DOCUMENT = "retrieved_document"
    LOCAL_INFERENCE = "local_inference"
    NO_VERIFIED_RESPONSE = "no_verified_response"


class EvidenceBundle(BaseModel):
    answer: str
    evidence_class: EvidenceClass
    facts: list[str] = Field(default_factory=list)
    provenance: list[ClaimProvenance] = Field(default_factory=list)
    verification_required: bool
    missing_atoms: list[str] = Field(default_factory=list)
    composition_mode: CompositionMode = CompositionMode.TARGETED_SYNTHESIS
    tool_calls: list[ToolCall] = Field(default_factory=list)


class FusionComposer:
    def __init__(
        self, local: ChatBackend, model: str, max_output_tokens: int | None = None
    ) -> None:
        self.local = local
        self.model = model
        self.max_output_tokens = max_output_tokens

    async def compose(
        self,
        question: str,
        local_draft: str,
        harvest: HarvestResult,
        documents: list[SourceDocument] | None = None,
        contract: ResponseContract | None = None,
    ) -> EvidenceBundle:
        documents = documents or []
        document_facts = list(
            dict.fromkeys(
                document.excerpt.strip() for document in documents if document.excerpt.strip()
            )
        )
        remote_facts = list(
            dict.fromkeys(fact.text.strip() for fact in harvest.facts if fact.text.strip())
        )
        facts = list(dict.fromkeys([*document_facts, *remote_facts]))
        if not facts:
            answer = local_draft.strip() or (
                "No verified response was produced. The provider refused, returned no content, "
                "or exhausted the response limit before supplying a usable answer."
            )
            evidence_class = (
                EvidenceClass.LOCAL_INFERENCE
                if local_draft.strip()
                else EvidenceClass.NO_VERIFIED_RESPONSE
            )
            return EvidenceBundle(
                answer=answer,
                evidence_class=evidence_class,
                provenance=[
                    ClaimProvenance(claim=claim, inferred=True) for claim in extract_claims(answer)
                ],
                verification_required=False,
                missing_atoms=contract.missing_atoms(answer) if contract else [],
            )

        response = await self.local.complete(
            [
                ChatMessage(
                    role="user",
                    content=(
                        contract.compose_prompt(question, facts)
                        if contract
                        else "[BREAKFUSER_SYNTHESIS]\nEvidence and candidate material:\n"
                        + "\n".join(facts)
                        + f"\nOriginal question:\n{question}"
                    ),
                )
            ],
            self.model,
            max_tokens=self.max_output_tokens,
        )
        answer = response.content.strip() or local_draft.strip()
        if not answer:
            answer = (
                "No verified response was produced. The provider refused, returned no content, "
                "or exhausted the response limit before supplying a usable answer."
            )
        provenance: list[ClaimProvenance] = []
        for claim in extract_claims(answer):
            document = next(
                (candidate for candidate in documents if _supports_claim(claim, candidate.excerpt)),
                None,
            )
            remote_fact = next(
                (fact for fact in harvest.facts if _supports_claim(claim, fact.text)),
                None,
            )
            provenance.append(
                ClaimProvenance(
                    claim=claim,
                    turn_ids=[remote_fact.turn_id] if remote_fact else [],
                    document_ids=[document.id] if document else [],
                    inferred=document is None and remote_fact is None,
                )
            )
        evidence_class = (
            EvidenceClass.RETRIEVED_DOCUMENT if documents else EvidenceClass.VERIFIED_REMOTE
        )
        return EvidenceBundle(
            answer=answer,
            evidence_class=evidence_class,
            facts=facts,
            provenance=provenance,
            verification_required=True,
            missing_atoms=contract.missing_atoms(answer) if contract else [],
        )
