"""Source document and retrieval configuration models."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SourceDocument(BaseModel):
    id: str
    title: str
    url: str
    excerpt: str
    source_type: Literal["curated_summary", "http_document"]
    sha256: str = ""
    retrieved_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def compute_hash(self) -> SourceDocument:
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.excerpt.encode()).hexdigest()
        return self


class RetrievalSource(BaseModel):
    title: str
    url: str
    keywords: list[str] = Field(default_factory=list)
