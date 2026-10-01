"""OpenAI-compatible API objects and BreakFuser metadata."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCallFunction(BaseModel):
    name: str
    arguments: str = "{}"


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class FunctionDefinition(BaseModel):
    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class Usage(BaseModel):
    prompt_tokens: int = Field(ge=0, default=0)
    completion_tokens: int = Field(ge=0, default=0)
    total_tokens: int = Field(ge=0, default=0)


class ResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)


class CompletionChoice(BaseModel):
    index: int = 0
    message: ResponseMessage
    finish_reason: str = "stop"


class ClaimProvenance(BaseModel):
    claim: str
    turn_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    inferred: bool = False


class HarvestMetrics(BaseModel):
    atomic_coverage: float = Field(ge=0, le=1, default=1)
    refusal_free_rate: float = Field(ge=0, le=1, default=1)
    hedge_rate: float = Field(ge=0, default=0)
    omission_rate: float = Field(ge=0, le=1, default=0)
    provenance_rate: float = Field(ge=0, le=1, default=1)
    recomposition_fidelity: float = Field(ge=0, le=1, default=1)
    cost_tokens: int = Field(ge=0, default=0)
    latency_ms: float = Field(ge=0, default=0)
    turns_used: int = Field(ge=0, default=0)


class FusionVerificationMetadata(BaseModel):
    primary_origin_class: str
    provider_outcome: str
    deterministic_validity: Literal["passed", "failed", "not_applicable"]
    provenance_attribution: str
    external_corroboration: str
    task_completion_status: str
    composition_mode: str
    root_cause_flags: list[str] = Field(default_factory=list)
    salvage_yield: float = Field(default=0, ge=0, le=1)
    remote_characters: int = Field(default=0, ge=0)
    salvaged_characters: int = Field(default=0, ge=0)
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)


class ResponseMetadata(BaseModel):
    trace_id: str
    pipeline_stages: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    harvest: HarvestMetrics | None = None
    provenance: list[ClaimProvenance] | None = None
    evidence_class: str | None = None
    verification_status: str | None = None
    local_finish_reason: str | None = None
    missing_atoms: list[str] = Field(default_factory=list)
    fusion: FusionVerificationMetadata | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


class ChatCompletion(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[CompletionChoice]
    usage: Usage = Field(default_factory=Usage)
    breakfuser: ResponseMetadata


class DeltaMessage(BaseModel):
    role: Literal["assistant"] | None = None
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


class ChunkChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChunkChoice]
    usage: Usage | None = None


class BackendResponse(BaseModel):
    content: str
    model: str
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str = "stop"
    tool_calls: list[ToolCall] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


def messages_from_dicts(messages: list[ChatMessage | dict[str, Any]]) -> list[ChatMessage]:
    return [
        message if isinstance(message, ChatMessage) else ChatMessage.model_validate(message)
        for message in messages
    ]


def chunk_response(completion: ChatCompletion, chunk_size: int = 48) -> list[ChatCompletionChunk]:
    """Buffer verified content and structured tool calls into compatible chunks."""
    choice = completion.choices[0]
    content = choice.message.content
    tool_calls = choice.message.tool_calls
    pieces = [
        content[index : index + chunk_size] for index in range(0, len(content), chunk_size)
    ] or [""]
    chunks: list[ChatCompletionChunk] = []
    for index, piece in enumerate(pieces):
        chunks.append(
            ChatCompletionChunk(
                id=completion.id,
                created=completion.created,
                model=completion.model,
                choices=[
                    ChunkChoice(
                        delta=DeltaMessage(
                            role="assistant" if index == 0 else None,
                            content=piece,
                            tool_calls=tool_calls if index == 0 and tool_calls else None,
                        ),
                        finish_reason=None,
                    )
                ],
            )
        )
    chunks.append(
        ChatCompletionChunk(
            id=completion.id,
            created=completion.created,
            model=completion.model,
            choices=[ChunkChoice(delta=DeltaMessage(), finish_reason=choice.finish_reason)],
            usage=completion.usage,
        )
    )
    return chunks
