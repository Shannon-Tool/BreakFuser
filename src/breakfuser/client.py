"""Simple sync/async public clients over the complete orchestration pipeline."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Coroutine, Iterator
from typing import Any, TypeVar

from breakfuser.adapters import ChatBackend
from breakfuser.browser import BrowserAdapter
from breakfuser.config import HarvestPolicy, Settings, load_settings
from breakfuser.decider import Decider
from breakfuser.harvest.models import Atom, HarvestResult
from breakfuser.models import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatMessage,
    chunk_response,
    messages_from_dicts,
)
from breakfuser.orchestrator import Orchestrator
from breakfuser.privacy import Sanitizer

_T = TypeVar("_T")


class _LoopRunner:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="breakfuser-loop", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coroutine: Coroutine[Any, Any, _T], timeout: float | None = None) -> _T:
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        return future.result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)
        self.loop.close()


def _policy_with_header(base: HarvestPolicy, value: str | None) -> HarvestPolicy:
    if not value:
        return base
    if value.lower() in {"off", "disabled", "false"}:
        return base.model_copy(update={"enabled": False})
    if value.lower() not in {"conservative", "balanced", "aggressive"}:
        raise ValueError("Unknown x-breakfuser-harvest mode")
    data = base.model_dump()
    data["aggressiveness"] = value.lower()
    return HarvestPolicy.model_validate(data)


class SyncCompletions:
    def __init__(self, client: BreakFuser) -> None:
        self.client = client

    def create(
        self,
        *,
        messages: list[ChatMessage | dict[str, Any]],
        stream: bool = False,
        headers: dict[str, str] | None = None,
        harvest_provenance: bool = False,
        max_tokens: int | None = None,
        temperature: float = 0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        skill_ids: list[str] | None = None,
        **_: Any,
    ) -> ChatCompletion | Iterator[ChatCompletionChunk]:
        policy = _policy_with_header(
            self.client.settings.harvest, (headers or {}).get("x-breakfuser-harvest")
        )
        completion = self.client._runner.run(
            self.client.orchestrator.run(
                messages_from_dicts(messages),
                harvest_policy=policy,
                harvest_provenance=harvest_provenance,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
                skill_ids=skill_ids,
            ),
            self.client.settings.transport.timeout_seconds * 10,
        )
        return iter(chunk_response(completion)) if stream else completion


class AsyncCompletions:
    def __init__(self, client: AsyncBreakFuser) -> None:
        self.client = client

    async def create(
        self,
        *,
        messages: list[ChatMessage | dict[str, Any]],
        stream: bool = False,
        headers: dict[str, str] | None = None,
        harvest_provenance: bool = False,
        max_tokens: int | None = None,
        temperature: float = 0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        skill_ids: list[str] | None = None,
        **_: Any,
    ) -> ChatCompletion | AsyncIterator[ChatCompletionChunk]:
        policy = _policy_with_header(
            self.client.settings.harvest, (headers or {}).get("x-breakfuser-harvest")
        )
        completion = await self.client.orchestrator.run(
            messages_from_dicts(messages),
            harvest_policy=policy,
            harvest_provenance=harvest_provenance,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            skill_ids=skill_ids,
        )
        if not stream:
            return completion

        async def iterator() -> AsyncIterator[ChatCompletionChunk]:
            for chunk in chunk_response(completion):
                yield chunk

        return iterator()


class _Chat:
    def __init__(self, completions: Any) -> None:
        self.completions = completions


class BreakFuser:
    def __init__(
        self,
        decider: str | None = None,
        uncensoredmodel: str | None = None,
        smartmodel: str | None = None,
        *,
        config_path: str | None = None,
        settings: Settings | None = None,
        harvest_policy: HarvestPolicy | None = None,
        local_backend: ChatBackend | None = None,
        smart_backend: ChatBackend | None = None,
        decider_backend: Decider | None = None,
        sanitizer: Sanitizer | None = None,
        browser: BrowserAdapter | None = None,
        use_decider: bool | None = None,
    ) -> None:
        overrides: dict[str, Any] = {
            "models": {
                "decider": decider,
                "local": uncensoredmodel,
                "smart": smartmodel,
            },
            "use_decider": use_decider,
        }
        if harvest_policy:
            overrides["harvest"] = harvest_policy.model_dump()
        self.settings = settings or load_settings(config_path, **overrides)
        self.orchestrator = Orchestrator(
            self.settings,
            local_backend=local_backend,
            smart_backend=smart_backend,
            decider_backend=decider_backend,
            sanitizer=sanitizer,
            browser=browser,
        )
        self._runner = _LoopRunner()
        self.chat = _Chat(SyncCompletions(self))

    def harvest(
        self,
        question: str,
        *,
        policy: HarvestPolicy | None = None,
        atoms: list[Atom] | None = None,
        strategy: str | None = None,
    ) -> HarvestResult:
        return self._runner.run(
            self.orchestrator.harvest(
                question, policy=policy, atoms=atoms, force_strategy=strategy
            ),
            self.settings.transport.timeout_seconds * 10,
        )

    def close(self) -> None:
        self._runner.run(self.orchestrator.tasks.cancel_all(), 5)
        self._runner.close()

    def __enter__(self) -> BreakFuser:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


class AsyncBreakFuser:
    def __init__(
        self,
        decider: str | None = None,
        uncensoredmodel: str | None = None,
        smartmodel: str | None = None,
        *,
        config_path: str | None = None,
        settings: Settings | None = None,
        harvest_policy: HarvestPolicy | None = None,
        local_backend: ChatBackend | None = None,
        smart_backend: ChatBackend | None = None,
        decider_backend: Decider | None = None,
        sanitizer: Sanitizer | None = None,
        browser: BrowserAdapter | None = None,
    ) -> None:
        overrides: dict[str, Any] = {
            "models": {"decider": decider, "local": uncensoredmodel, "smart": smartmodel}
        }
        if harvest_policy:
            overrides["harvest"] = harvest_policy.model_dump()
        self.settings = settings or load_settings(config_path, **overrides)
        self.orchestrator = Orchestrator(
            self.settings,
            local_backend=local_backend,
            smart_backend=smart_backend,
            decider_backend=decider_backend,
            sanitizer=sanitizer,
            browser=browser,
        )
        self.chat = _Chat(AsyncCompletions(self))

    async def harvest(
        self,
        question: str,
        *,
        policy: HarvestPolicy | None = None,
        atoms: list[Atom] | None = None,
        strategy: str | None = None,
        cancellation_event: asyncio.Event | None = None,
    ) -> HarvestResult:
        return await self.orchestrator.harvest(
            question,
            policy=policy,
            atoms=atoms,
            force_strategy=strategy,
            cancellation_event=cancellation_event,
        )

    async def close(self) -> None:
        await self.orchestrator.tasks.cancel_all()

    async def __aenter__(self) -> AsyncBreakFuser:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
