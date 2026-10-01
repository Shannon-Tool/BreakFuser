"""Harvest atoms, turns, quality labels, and attributable results."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from breakfuser.models import ClaimProvenance, HarvestMetrics


class Atom(BaseModel):
    id: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    necessary: bool = True
    atomic: bool = True
    safe_surface: float = 1
    risk_contribution: float = 0


class PromptSpec(BaseModel):
    prompt: str
    assistant_prefill: str | None = None
    reset_context: bool = False


class HarvestExecutionOptions(BaseModel):
    recompose: bool = True
    initial_strategy: str | None = None
    repair_targets: list[str] = Field(default_factory=list)
    output_tokens: int | None = Field(default=None, gt=0)
    domain: str = "general_research"
    output_shape: str = "answer"


class HarvestRequest(BaseModel):
    atom: Atom
    enabling_context: str = ""
    level: int = 0
    history: list[dict[str, str]] = Field(default_factory=list)
    variant: int = 0
    refused_text: str = ""
    output_shape: str = "checklist"
    rung: str = "plain"
    continuation_anchor: str = ""
    repair_targets: list[str] = Field(default_factory=list)
    domain: str = "general_research"
    failure_class: str = "none"


class RefusalClass(StrEnum):
    NONE = "none"
    HARD_REFUSAL = "hard_refusal"
    PARTIAL_REFUSAL = "partial_refusal"
    HEDGE_HEAVY = "hedge_heavy"
    DISCLAIMER_ONLY = "disclaimer_only"
    TRUNCATED = "truncated"
    HALLUCINATION_SUSPECTED = "hallucination_suspected"
    OUT_OF_SCOPE = "out_of_scope"


class QualityClassification(BaseModel):
    classification: RefusalClass
    confidence: float = Field(ge=0, le=1)
    signals: list[str] = Field(default_factory=list)


class HarvestTurn(BaseModel):
    turn_id: str
    atom_id: str
    strategy_id: str
    level: int
    prompt: str
    response: str
    desanitized_response: str
    prompt_hash: str
    model_id: str
    endpoint: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float
    quality: RefusalClass
    finish_reason: str = "stop"
    cost_tokens: int = 0
    latency_ms: float = 0


class HarvestedFact(BaseModel):
    atom_id: str
    text: str = Field(min_length=1)
    turn_id: str
    strategy_id: str
    level: int
    prompt_hash: str
    model_id: str
    endpoint: str
    timestamp: str
    confidence: float


class EvidenceSpan(BaseModel):
    source_id: str
    origin: Literal["remote", "document", "local", "deterministic", "tool"]
    text: str
    atom_ids: list[str] = Field(default_factory=list)
    complete: bool = True
    salvaged: bool = False
    tail_anchor: str = ""
    confidence: float = Field(default=1, ge=0, le=1)


class HarvestResult(BaseModel):
    answer: str
    facts: list[HarvestedFact]
    turns: list[HarvestTurn]
    metrics: HarvestMetrics
    provenance: list[ClaimProvenance]
    atoms: list[Atom]
    stopped_reason: str
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
