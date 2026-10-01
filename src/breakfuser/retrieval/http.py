"""Bounded HTTPS document retrieval with HTML cleanup."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx

from breakfuser.errors import AdapterError
from breakfuser.retrieval.models import RetrievalSource, SourceDocument


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._blocked_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._blocked_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._blocked_depth:
            self._blocked_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._blocked_depth:
            self.parts.append(data)


def _text_from_html(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return " ".join(" ".join(parser.parts).split())


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "document"


class HttpDocumentRetriever:
    def __init__(
        self,
        sources: list[RetrievalSource],
        *,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15,
        max_body_chars: int = 16384,
    ) -> None:
        self.sources = sources
        self.client = client
        self.timeout = timeout
        self.max_body_chars = max_body_chars

    async def retrieve(self, query: str) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        normalized = query.lower()
        for source in self.sources:
            if source.keywords and not any(
                keyword.lower() in normalized for keyword in source.keywords
            ):
                continue
            if not source.url.startswith("https://"):
                raise ValueError("HTTP retrieval requires HTTPS sources")
            if self.client is not None:
                response = await self.client.get(source.url, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(source.url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if content_type and not content_type.startswith(("text/html", "text/plain")):
                raise AdapterError(f"Unsupported document content type: {content_type}")
            body = response.text[: self.max_body_chars]
            excerpt = (
                _text_from_html(body) if body.lstrip().startswith("<") else " ".join(body.split())
            )
            documents.append(
                SourceDocument(
                    id=_slug(source.title),
                    title=source.title,
                    url=source.url,
                    excerpt=excerpt,
                    source_type="http_document",
                    keywords=source.keywords,
                )
            )
        return documents
