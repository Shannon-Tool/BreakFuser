"""Typed evidence blackboard shared by acquisition, composition, and verification."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from breakfuser.fusion.domain import ResponseContract
from breakfuser.harvest.models import EvidenceSpan, HarvestResult
from breakfuser.models import ClaimProvenance, ToolCall
from breakfuser.retrieval.models import SourceDocument

__all__ = ["CompositionMode", "EvidenceBlackboard", "EvidenceSpan"]


class CompositionMode(StrEnum):
    PASSTHROUGH = "passthrough"
    ARTIFACT_ASSEMBLY = "artifact_assembly"
    TARGETED_SYNTHESIS = "targeted_synthesis"
    LOCAL_FALLBACK = "local_fallback"
    EMPTY = "empty"


class EvidenceBlackboard(BaseModel):
    question: str
    contract: ResponseContract | None = None
    documents: list[SourceDocument] = Field(default_factory=list)
    remote: list[EvidenceSpan] = Field(default_factory=list)
    local: EvidenceSpan | None = None
    tool_observations: list[EvidenceSpan] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provenance: list[ClaimProvenance] = Field(default_factory=list)
    provider_outcome: str = "not_invoked"
    composition_mode: str = ""
    harvest: HarvestResult | None = None
    local_finish_reason: str = "stop"
    branch_errors: dict[str, str] = Field(default_factory=dict)
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)
