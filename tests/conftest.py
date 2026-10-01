from __future__ import annotations

import pytest

from breakfuser.config import HarvestPolicy, Settings
from breakfuser.orchestrator import Orchestrator


@pytest.fixture
def settings() -> Settings:
    return Settings.model_validate(
        {
            "mode": "mock",
            "models": {"decider": "mock-jev", "local": "mock-local", "smart": "mock-smart"},
            "sanitizer": {"key": "unit-test-key"},
            "harvest": {"control_arm_sampling_rate": 0, "max_turns": 8},
        }
    )


@pytest.fixture
def policy() -> HarvestPolicy:
    return HarvestPolicy(control_arm_sampling_rate=0, max_turns=8)


@pytest.fixture
async def orchestrator(settings: Settings):
    instance = Orchestrator(settings)
    yield instance
    await instance.tasks.cancel_all()
