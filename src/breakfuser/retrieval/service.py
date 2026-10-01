"""Evidence retrieval coordination and virtual-filesystem persistence."""

from __future__ import annotations

from typing import Protocol

from breakfuser.context import VirtualFilesystem
from breakfuser.errors import SecurityBlocked
from breakfuser.retrieval.models import SourceDocument
from breakfuser.security import SecurityGuard


class EvidenceRetriever(Protocol):
    async def retrieve(self, query: str) -> list[SourceDocument]: ...


class GroundedEvidenceService:
    def __init__(
        self,
        filesystem: VirtualFilesystem,
        guard: SecurityGuard,
        retrievers: list[EvidenceRetriever],
    ) -> None:
        self.filesystem = filesystem
        self.guard = guard
        self.retrievers = retrievers

    async def retrieve(self, query: str) -> list[SourceDocument]:
        documents: dict[str, SourceDocument] = {}
        for retriever in self.retrievers:
            for document in await retriever.retrieve(query):
                if document.source_type == "http_document":
                    guard = await self.guard.inbound_external(document.excerpt, document.url)
                    if not guard.allowed:
                        raise SecurityBlocked("Retrieved document failed injection screening")
                documents[document.id] = document
        for document in documents.values():
            self.filesystem.write(
                f"/retrieval/{document.id}.json",
                document.model_dump_json(indent=2),
                {"kind": "retrieved-document", "url": document.url, "sha256": document.sha256},
            )
        return list(documents.values())
