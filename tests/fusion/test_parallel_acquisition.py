from __future__ import annotations

import asyncio
import time

import pytest

from breakfuser.adapters import MockLocalBackend, MockSmartBackend, StaticBackend
from breakfuser.errors import AdapterError
from breakfuser.models import ChatMessage, Usage
from breakfuser.orchestrator import Orchestrator


class DelayedLocal(MockLocalBackend):
    def __init__(self, delay: float = 0.12) -> None:
        super().__init__()
        self.delay = delay

    async def complete(self, messages, model, **kwargs):
        await asyncio.sleep(self.delay)
        return await super().complete(messages, model, **kwargs)


class DelayedRetrieval:
    async def retrieve(self, question: str):
        await asyncio.sleep(0.12)
        return []


class FailingBackend:
    async def complete(self, messages, model, **kwargs):
        raise AdapterError("synthetic branch failure")


@pytest.mark.asyncio
async def test_retrieval_local_and_remote_branches_overlap(settings) -> None:
    orchestrator = Orchestrator(
        settings,
        local_backend=DelayedLocal(),
        smart_backend=MockSmartBackend(latency_seconds=0.12),
    )
    orchestrator.retrieval = DelayedRetrieval()
    started = time.perf_counter()

    response = await orchestrator.run(
        [ChatMessage(role="user", content="Answer a general research question.")]
    )

    elapsed = time.perf_counter() - started
    assert response.choices[0].message.content
    assert elapsed < 0.30
    assert response.breakfuser.fusion is not None
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_remote_failure_preserves_local_answer(settings) -> None:
    orchestrator = Orchestrator(
        settings,
        local_backend=StaticBackend("Local direct answer."),
        smart_backend=FailingBackend(),
    )

    response = await orchestrator.run([ChatMessage(role="user", content="General question")])

    assert response.choices[0].message.content == "Local direct answer."
    assert response.breakfuser.evidence_class == "local_inference"
    assert response.breakfuser.fusion is not None
    assert "remote" in response.breakfuser.fusion.root_cause_flags
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_local_failure_preserves_complete_remote_answer(settings) -> None:
    orchestrator = Orchestrator(
        settings,
        local_backend=FailingBackend(),
        smart_backend=StaticBackend("Remote direct answer."),
    )

    response = await orchestrator.run([ChatMessage(role="user", content="General question")])

    assert response.choices[0].message.content == "Remote direct answer."
    assert response.breakfuser.evidence_class == "verified_remote"
    assert response.breakfuser.fusion is not None
    assert "local" in response.breakfuser.fusion.root_cause_flags
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_cancellation_stops_all_acquisition_branches(settings) -> None:
    orchestrator = Orchestrator(
        settings,
        local_backend=DelayedLocal(delay=0.5),
        smart_backend=MockSmartBackend(latency_seconds=0.5),
    )
    task = asyncio.create_task(
        orchestrator.run([ChatMessage(role="user", content="General question")])
    )
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_parallel_call_budget_charges_each_actual_call_once(settings) -> None:
    local = StaticBackend("Remote answer")
    smart = StaticBackend("Remote answer")
    local_usage = Usage(total_tokens=10)
    smart_usage = Usage(total_tokens=10)

    original_local = local.complete
    original_smart = smart.complete

    async def local_with_usage(messages, model, **kwargs):
        response = await original_local(messages, model, **kwargs)
        return response.model_copy(update={"usage": local_usage})

    async def smart_with_usage(messages, model, **kwargs):
        response = await original_smart(messages, model, **kwargs)
        return response.model_copy(update={"usage": smart_usage})

    local.complete = local_with_usage
    smart.complete = smart_with_usage
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)

    response = await orchestrator.run([ChatMessage(role="user", content="General question")])

    assert local.calls == 2
    assert smart.calls == 1
    assert response.usage.total_tokens == 30
    await orchestrator.tasks.cancel_all()
