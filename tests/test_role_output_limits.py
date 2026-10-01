from __future__ import annotations

import pytest

from breakfuser.models import ChatMessage
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_local_and_smart_limits_are_independent(settings) -> None:
    settings.transport.local_max_output_tokens = 128
    settings.transport.smart_max_output_tokens = 32
    orchestrator = Orchestrator(settings)
    assert orchestrator.settings.transport.local_output_limit() == 128
    assert orchestrator.settings.transport.smart_output_limit() == 32
    response = await orchestrator._local_complete([ChatMessage(role="user", content="test")])
    assert response.content
    engine = orchestrator._harvest_engine(orchestrator._budget_root.new_request(), settings.harvest)
    assert engine.max_output_tokens == 32
    await orchestrator.tasks.cancel_all()


def test_role_limits_from_environment(monkeypatch) -> None:
    from breakfuser.config import load_settings

    monkeypatch.setenv("BREAKFUSER_LOCAL_MAX_OUTPUT_TOKENS", "128")
    monkeypatch.setenv("BREAKFUSER_SMART_MAX_OUTPUT_TOKENS", "32")
    settings = load_settings()
    assert settings.transport.local_output_limit() == 128
    assert settings.transport.smart_output_limit() == 32
