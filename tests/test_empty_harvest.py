from __future__ import annotations

import pytest

from breakfuser.adapters import StaticBackend
from breakfuser.harvest.models import Atom
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_empty_remote_answer_never_becomes_harvested_fact(settings) -> None:
    orchestrator = Orchestrator(settings, smart_backend=StaticBackend(""))
    result = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="empty", description="empty")],
        force_strategy="direct",
    )
    assert not result.facts
    assert result.metrics.atomic_coverage == 0
    assert result.turns
    assert all(turn.quality.value == "truncated" for turn in result.turns)
    await orchestrator.tasks.cancel_all()
