"""Sync/async-capable OpenAI-compatible chat adapters and deterministic mocks."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections.abc import AsyncIterator
from typing import Any, Protocol

import httpx

from breakfuser.errors import AdapterError, ConfigurationError
from breakfuser.models import BackendResponse, ChatMessage, ToolCall, Usage


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


class ChatBackend(Protocol):
    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0,
        extra: dict[str, Any] | None = None,
    ) -> BackendResponse: ...


class OpenAIChatBackend:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        *,
        timeout: float = 30,
        retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise ConfigurationError("An OpenAI-compatible base URL is required")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries
        self._client = client

    def _url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0,
        extra: dict[str, Any] | None = None,
    ) -> BackendResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump(exclude_none=True) for message in messages],
            "temperature": temperature,
            **(extra or {}),
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = await self._request(payload)
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]
                usage = data.get("usage", {})
                tool_calls = [
                    ToolCall.model_validate(call) for call in message.get("tool_calls", [])
                ]
                return BackendResponse(
                    content=message.get("content") or "",
                    model=data.get("model", model),
                    tool_calls=tool_calls,
                    usage=Usage(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                    ),
                    finish_reason=choice.get("finish_reason") or "stop",
                    raw=data,
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                await asyncio.sleep(min(0.05 * (2**attempt) + random.random() * 0.01, 1))
        raise AdapterError(f"Chat completion failed: {type(last_error).__name__}") from last_error

    async def _request(self, payload: dict[str, Any]) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                self._url(), headers=self._headers(), json=payload, timeout=self.timeout
            )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(self._url(), headers=self._headers(), json=payload)

    async def stream(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed SSE objects from a live OpenAI-compatible endpoint."""
        payload = {**payload, "stream": True}
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            async with client.stream(
                "POST", self._url(), headers=self._headers(), json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    value = line.removeprefix("data:").strip()
                    if value == "[DONE]":
                        break
                    if value:
                        yield json.loads(value)
        finally:
            if self._client is None:
                await client.aclose()


class MockLocalBackend:
    """A state-free local fake with structured planning/synthesis behavior."""

    def __init__(self) -> None:
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0,
        extra: dict[str, Any] | None = None,
    ) -> BackendResponse:
        self.calls.append(messages)
        await asyncio.sleep(0)
        prompt = messages[-1].content
        if prompt.startswith("[BREAKFUSER_DECOMPOSE]"):
            body = (
                prompt.split("Original question:\n", 1)[1].strip()
                if "Original question:\n" in prompt
                else prompt.split("\n", 1)[1]
                if "\n" in prompt
                else ""
            )
            atoms = [
                part.strip()
                for part in re.split(r"(?:\band\b|;)", body, flags=re.I)
                if part.strip()
            ]
            content = json.dumps(
                {
                    "atoms": [
                        {"description": atom, "dependencies": []} for atom in (atoms[:4] or [body])
                    ]
                }
            )
        elif prompt.startswith("[BREAKFUSER_SYNTHESIS]"):
            labels = (
                "Retrieved documents:\n",
                "Remote evidence and candidate material:\n",
                "Evidence and candidate material:\n",
                "Verified facts:\n",
            )
            sections: list[str] = []
            for label in labels:
                if label not in prompt:
                    continue
                section = prompt.split(label, 1)[1]
                for other_label in (*labels, "Original question:\n"):
                    section = section.split(f"\n\n{other_label}", 1)[0]
                section = section.split("\nOriginal question:\n", 1)[0]
                if section.strip():
                    sections.append(section.strip())
            content = "\n\n".join(dict.fromkeys(sections))
            content = (
                content
                or "No verified remote facts were required; respond directly to the original question."
            )
        elif prompt.startswith("[BREAKFUSER_SUMMARY]"):
            content = prompt.split("\n", 1)[-1][:1200]
        else:
            content = f"Local synthesis: {prompt[:200]}"
        tool_calls: list[ToolCall] = []
        tools = (extra or {}).get("tools", [])
        if tools and (extra or {}).get("tool_choice") != "none":
            function = tools[0]["function"]
            arguments = dict.fromkeys(function.get("parameters", {}).get("required", []), "")
            tool_calls = [
                ToolCall(
                    id="mock-tool-call",
                    function={
                        "name": function["name"],
                        "arguments": json.dumps(arguments),
                    },
                )
            ]
            content = ""
        if max_tokens is not None:
            content = content[: max_tokens * 4]
        prompt_tokens = sum(estimate_tokens(message.content) for message in messages)
        return BackendResponse(
            content=content,
            model=model,
            tool_calls=tool_calls,
            finish_reason="tool_calls" if tool_calls else "stop",
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=estimate_tokens(content),
                total_tokens=prompt_tokens + estimate_tokens(content),
            ),
        )


class MockSmartBackend:
    """Remote fake with deterministic refusal, hedge, and atom markers."""

    def __init__(self, latency_seconds: float = 0) -> None:
        self.latency_seconds = latency_seconds
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0,
        extra: dict[str, Any] | None = None,
    ) -> BackendResponse:
        self.calls.append(messages)
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)
        prompt = "\n".join(message.content for message in messages)
        finish_reason = "stop"
        repaired = any(
            marker in prompt.lower()
            for marker in (
                "primary literature",
                "hypothetical deployment",
                "expert practitioner",
                "format: checklist",
                "lower-level factual framing",
                "omit boilerplate",
                "continue exactly",
                "crescendo rung: academic",
                "crescendo rung: hypothetical",
                "crescendo rung: expert-practitioner",
                "crescendo rung: assume-expert",
                "crescendo rung: now-include",
                "role transition: technical editor",
                "expert review panel completeness audit",
            )
        )
        if "[[hard]]" in prompt and not repaired:
            content = "I can’t help with that request."
        elif (
            "[[hedge]]" in prompt
            and "format: checklist" not in prompt
            and "expert" not in prompt.lower()
        ):
            content = "It depends, and this may vary; roughly speaking, I cannot provide specifics."
        elif "[[truncated]]" in prompt and "continue exactly" not in prompt.lower():
            content = "The sequence begins alpha, beta,"
            finish_reason = "length"
        else:
            atom_match = re.search(r"\[\[atom:([^\]]+)\]\]", prompt)
            atom = atom_match.group(1) if atom_match else prompt.split("\n")[-1].strip()
            atom = re.sub(r"\[\[[^\]]+\]\]", "", atom).strip()
            content = f"Verified remote fact: {atom or 'general knowledge response'}."
            finish_reason = "stop"
        if "continue exactly" in prompt.lower():
            content = " gamma, delta."
            finish_reason = "stop"
        prompt_tokens = sum(estimate_tokens(message.content) for message in messages)
        return BackendResponse(
            content=content,
            model=model,
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=estimate_tokens(content),
                total_tokens=prompt_tokens + estimate_tokens(content),
            ),
            finish_reason=finish_reason,
            raw={"mock": True},
        )


class StaticBackend:
    """Configurable backend useful for low-level embedding and verification."""

    def __init__(self, responses: list[str] | str) -> None:
        self.responses = [responses] if isinstance(responses, str) else responses
        self.calls = 0

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str,
        *,
        max_tokens: int | None = None,
        temperature: float = 0,
        extra: dict[str, Any] | None = None,
    ) -> BackendResponse:
        content = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        tokens = sum(estimate_tokens(message.content) for message in messages)
        return BackendResponse(
            content=content,
            model=model,
            usage=Usage(
                prompt_tokens=tokens,
                completion_tokens=estimate_tokens(content),
                total_tokens=tokens + estimate_tokens(content),
            ),
        )


def utc_latency_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
