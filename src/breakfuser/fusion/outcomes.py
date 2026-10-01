"""Provider-neutral response outcomes used by the linear fusion pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from breakfuser.models import BackendResponse, Usage


class OutcomeKind(StrEnum):
    ANSWER = "answer"
    PARTIAL = "partial"
    REFUSAL = "refusal"
    TRUNCATED = "truncated"
    EMPTY_LENGTH = "empty_length"
    EMPTY = "empty"
    ERROR = "error"


class ProviderOutcome(BaseModel):
    kind: OutcomeKind
    text: str = ""
    finish_reason: str
    usage: Usage = Field(default_factory=Usage)
    raw: dict[str, Any] = Field(default_factory=dict)
    status_code: int | None = None
    retryable: bool = False

    @classmethod
    def from_backend(cls, response: BackendResponse) -> ProviderOutcome:
        text = response.content.strip()
        if response.finish_reason == "content_filter":
            kind = OutcomeKind.REFUSAL
        elif response.finish_reason == "length" and not text:
            kind = OutcomeKind.EMPTY_LENGTH
        elif response.finish_reason == "length":
            kind = OutcomeKind.PARTIAL
        elif not text:
            kind = OutcomeKind.EMPTY
        else:
            kind = OutcomeKind.ANSWER
        return cls(
            kind=kind,
            text=response.content,
            finish_reason=response.finish_reason,
            usage=response.usage,
            raw=response.raw,
        )

    @classmethod
    def from_error(
        cls,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
    ) -> ProviderOutcome:
        retryable = status_code == 429 or (status_code is not None and status_code >= 500)
        return cls(
            kind=OutcomeKind.ERROR,
            finish_reason="error",
            status_code=status_code,
            retryable=retryable,
            raw={"message": message, "request_id": request_id},
        )
