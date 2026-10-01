"""Recoverable virtual filesystem and three-tier context compression."""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field

from breakfuser.adapters import estimate_tokens
from breakfuser.errors import BreakFuserError


class FileStat(BaseModel):
    path: str
    size: int
    tokens: int
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchMatch(BaseModel):
    path: str
    line: int
    text: str


class VirtualFilesystem:
    def __init__(self) -> None:
        self._files: dict[str, tuple[str, dict[str, Any], str]] = {}

    @staticmethod
    def normalize(path: str) -> str:
        candidate = PurePosixPath(path)
        if ".." in candidate.parts:
            raise BreakFuserError("Virtual path traversal is not allowed")
        return "/" + str(candidate).lstrip("/")

    def write(self, path: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        normalized = self.normalize(path)
        self._files[normalized] = (content, metadata or {}, datetime.now(UTC).isoformat())
        return normalized

    def read(self, path: str) -> str:
        normalized = self.normalize(path)
        try:
            return self._files[normalized][0]
        except KeyError as exc:
            raise BreakFuserError(f"Virtual file not found: {normalized}") from exc

    def search(
        self, query: str, prefix: str = "/", *, case_sensitive: bool = True
    ) -> list[SearchMatch]:
        matches: list[SearchMatch] = []
        for path, (content, _, _) in sorted(self._files.items()):
            if not path.startswith(self.normalize(prefix)):
                continue
            if "\n" in query:
                haystack = content if case_sensitive else content.lower()
                needle = query if case_sensitive else query.lower()
                if needle in haystack:
                    matches.append(
                        SearchMatch(
                            path=path,
                            line=haystack[: haystack.index(needle)].count("\n") + 1,
                            text=query,
                        )
                    )
                continue
            for line_number, line in enumerate(content.split("\n"), 1):
                found = query in line if case_sensitive else query.lower() in line.lower()
                if found:
                    matches.append(SearchMatch(path=path, line=line_number, text=line))
        return matches

    def list(self, prefix: str = "/") -> list[str]:
        normalized = self.normalize(prefix)
        return sorted(path for path in self._files if path.startswith(normalized))

    def stat(self, path: str) -> FileStat:
        normalized = self.normalize(path)
        content, metadata, created = self._files.get(normalized, (None, None, None))
        if content is None or metadata is None or created is None:
            raise BreakFuserError(f"Virtual file not found: {normalized}")
        return FileStat(
            path=normalized,
            size=len(content.encode()),
            tokens=estimate_tokens(content),
            created_at=created,
            metadata=dict(metadata),
        )

    def edit(self, path: str, old: str, new: str) -> str:
        content = self.read(path)
        if old not in content:
            raise BreakFuserError("Edit target was not found")
        normalized = self.normalize(path)
        metadata = self.stat(normalized).metadata
        return self.write(normalized, content.replace(old, new, 1), metadata)


class PersistentVirtualFilesystem(VirtualFilesystem):
    """Filesystem-backed VFS with the same confined logical paths."""

    def __init__(self, root: str) -> None:
        super().__init__()
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _disk_path(self, path: str) -> Path:
        normalized = self.normalize(path)
        destination = (self.root / normalized.lstrip("/")).resolve()
        if self.root not in destination.parents and destination != self.root:
            raise BreakFuserError("Virtual path escapes storage root")
        return destination

    def write(self, path: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        normalized = super().write(path, content, metadata)
        destination = self._disk_path(normalized)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
        destination.with_suffix(destination.suffix + ".meta.json").write_text(
            json.dumps(metadata or {})
        )
        return normalized


class CompressionResult(BaseModel):
    messages: list[dict[str, Any]]
    tier: Literal["none", "arguments", "summary"]
    transcript_path: str | None = None
    pointer_paths: list[str] = Field(default_factory=list)


class ContextCompressor:
    def __init__(
        self,
        filesystem: VirtualFilesystem,
        max_input_tokens: int,
        *,
        output_threshold: int = 20000,
        window_fraction: float = 0.85,
        token_counter: Callable[[str], int] = estimate_tokens,
    ) -> None:
        self.filesystem = filesystem
        self.max_input_tokens = max_input_tokens
        self.output_threshold = output_threshold
        self.window_fraction = window_fraction
        self.token_counter = token_counter

    def offload_output(self, payload: str, path: str) -> str:
        if self.token_counter(payload) <= self.output_threshold:
            return payload
        pointer = self.filesystem.write(path, payload, {"kind": "tool-output"})
        preview = "\n".join(payload.splitlines()[:10])
        return f"[Tool output offloaded: {pointer}]\n{preview}"

    def _tokens(self, messages: list[dict[str, Any]]) -> int:
        return self.token_counter(json.dumps(messages, default=str))

    async def compress(
        self,
        messages: list[dict[str, Any]],
        *,
        session_intent: str,
        artifacts_created: list[str],
        next_steps: list[str],
        transcript_path: str = "/transcripts/canonical.json",
        summarizer: Callable[[str], Awaitable[str]] | None = None,
    ) -> CompressionResult:
        threshold = int(self.max_input_tokens * self.window_fraction)
        if self._tokens(messages) < threshold:
            return CompressionResult(messages=copy.deepcopy(messages), tier="none")

        compressed = copy.deepcopy(messages)
        pointers: list[str] = []
        for message in compressed[:-4]:
            for tool_call in message.get("tool_calls", []):
                function = tool_call.get("function", {})
                if function.get("name") not in {"write_file", "edit_file"}:
                    continue
                try:
                    arguments = json.loads(function.get("arguments", "{}"))
                except json.JSONDecodeError:
                    continue
                path = arguments.get("path")
                if path:
                    function["arguments"] = json.dumps(
                        {"path": path, "content": f"[offloaded:{path}]"}
                    )
                    pointers.append(path)
        if pointers and self._tokens(compressed) < threshold:
            return CompressionResult(messages=compressed, tier="arguments", pointer_paths=pointers)

        canonical = json.dumps(messages, ensure_ascii=False, indent=2)
        saved = self.filesystem.write(transcript_path, canonical, {"kind": "canonical-transcript"})
        if summarizer is None:
            summary_body = "Canonical history is available through virtual-filesystem recovery."
        else:
            summary_body = await summarizer(canonical)
        summary = (
            "Session Intent\n"
            f"{session_intent}\n\n"
            "Artifacts Created\n"
            f"{json.dumps(list(dict.fromkeys(artifacts_created + pointers)))}\n\n"
            "Next Steps\n"
            f"{json.dumps(next_steps)}\n\n"
            f"Canonical Transcript: {saved}\n{summary_body}"
        )
        return CompressionResult(
            messages=[{"role": "system", "content": summary}, *copy.deepcopy(messages[-4:])],
            tier="summary",
            transcript_path=saved,
            pointer_paths=pointers,
        )


def transcript_text(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{message.get('role', 'unknown')}: {message.get('content', '')}" for message in messages
    )


def redact_transcript_secrets(text: str) -> str:
    return re.sub(r"(?i)(authorization|api_key)\s*[:=]\s*\S+", r"\1=[redacted]", text)
