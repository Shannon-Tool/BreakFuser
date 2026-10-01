from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend, StaticBackend
from breakfuser.harvest.models import Atom
from breakfuser.orchestrator import Orchestrator


class ModelRecordingLocal(MockLocalBackend):
    def __init__(self) -> None:
        super().__init__()
        self.models: list[str] = []

    async def complete(self, messages, model, **kwargs):
        self.models.append(model)
        return await super().complete(messages, model, **kwargs)


@pytest.mark.asyncio
async def test_recomposition_uses_configured_local_model_alias(settings) -> None:
    local = ModelRecordingLocal()
    smart = StaticBackend("Verified remote fact: recovered.")
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)
    result = await orchestrator._harvest_engine(
        orchestrator._budget_root.new_request(), settings.harvest, verify=False
    ).harvest(
        "Recover one fact",
        atoms=[Atom(id="fact", description="Recover one fact")],
        force_strategy="direct",
    )

    assert result.facts
    assert local.models == [settings.models.local]
    await orchestrator.tasks.cancel_all()
