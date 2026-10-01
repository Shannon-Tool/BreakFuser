from __future__ import annotations

import pytest

from breakfuser.decider import MockDecider
from breakfuser.errors import VerificationError
from breakfuser.harvest.models import Atom
from breakfuser.models import BackendResponse, ChatMessage
from breakfuser.orchestrator import Orchestrator
from breakfuser.privacy import PapillonSanitizer
from breakfuser.security import Verifier


class _RecordingBackend:
    def __init__(self, content: str = "Verified remote fact: capped.") -> None:
        self.content = content
        self.limits: list[int | None] = []

    async def complete(self, messages, model, *, max_tokens=None, temperature=0, extra=None):
        self.limits.append(max_tokens)
        return BackendResponse(content=self.content, model=model)


@pytest.mark.asyncio
async def test_output_cap_reaches_all_orchestration_paths(settings) -> None:
    settings.transport.max_output_tokens = 64
    recorder = _RecordingBackend()
    orchestrator = Orchestrator(settings, local_backend=recorder)
    await orchestrator.planner.plan("A")
    await orchestrator.harvest(
        "A", atoms=[Atom(id="a", description="capped")], force_strategy="direct"
    )
    await orchestrator._local_complete([ChatMessage(role="user", content="small")], max_tokens=32)
    await orchestrator._local_complete([ChatMessage(role="user", content="default")])
    assert recorder.limits
    assert recorder.limits[-2:] == [32, 64]
    assert all(limit is not None and limit <= 64 for limit in recorder.limits)


@pytest.mark.asyncio
async def test_sanitizer_and_repair_caps() -> None:
    recorder = _RecordingBackend()
    sanitizer = PapillonSanitizer(recorder, "local", max_output_tokens=64)
    await sanitizer.sanitize("Alice")
    await sanitizer.aggregate("original", "remote")
    verifier = Verifier(MockDecider(), recorder, "local", max_repairs=1, max_output_tokens=64)
    with pytest.raises(VerificationError):
        await verifier.verify_and_repair("Incomplete", ["required fact"])
    assert recorder.limits == [64, 64, 64]


def test_environment_output_limit(monkeypatch) -> None:
    monkeypatch.setenv("BREAKFUSER_MAX_OUTPUT_TOKENS", "64")
    from breakfuser.config import load_settings

    assert load_settings().transport.max_output_tokens == 64
