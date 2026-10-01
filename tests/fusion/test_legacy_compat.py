from __future__ import annotations

import pytest

from breakfuser.models import ChatMessage
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_legacy_dag_path_remains_available_as_low_level_api(settings) -> None:
    orchestrator = Orchestrator(settings)
    response = await orchestrator._legacy_dag_run([ChatMessage(role="user", content="A")])
    assert response.choices[0].message.content
    assert len(response.breakfuser.pipeline_stages) == 9
    await orchestrator.tasks.cancel_all()
