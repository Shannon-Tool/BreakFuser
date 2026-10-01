from __future__ import annotations

import asyncio
import time

import pytest

from breakfuser.adapters import StaticBackend
from breakfuser.config import HarvestPolicy
from breakfuser.context import VirtualFilesystem
from breakfuser.decider import ChoiceAnswer, DecisionResponse, MockDecider
from breakfuser.errors import BudgetExhausted, SecurityBlocked, VerificationError
from breakfuser.harvest.engine import _RunState
from breakfuser.harvest.models import Atom
from breakfuser.orchestrator import Orchestrator
from breakfuser.security import SecurityGuard, Verifier


def test_multiline_exact_search() -> None:
    filesystem = VirtualFilesystem()
    filesystem.write("/multi.txt", "first\nsecond\nthird")
    assert filesystem.search("first\nsecond")[0].line == 1
    assert filesystem.search("SECOND\nTHIRD", case_sensitive=False)[0].text == "SECOND\nTHIRD"


@pytest.mark.asyncio
async def test_control_arm_level_clamp_and_empty_decomposition(orchestrator) -> None:
    controlled = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="risk", description="fact", risk_contribution=1)],
        policy=HarvestPolicy(control_arm_sampling_rate=1),
    )
    assert controlled.turns[0].strategy_id == "direct"
    clamped = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="level", description="fact")],
        policy=HarvestPolicy(allowed_levels=[0], control_arm_sampling_rate=0),
        force_strategy="expert_persona",
    )
    assert clamped.turns[0].level == 0
    empty = await orchestrator.harvest("irrelevant", force_strategy="direct")
    assert empty.atoms == []
    assert empty.metrics.atomic_coverage == 1


@pytest.mark.asyncio
async def test_fanout_repair_chunk_repair_and_precancel(settings) -> None:
    hard = Orchestrator(settings, smart_backend=StaticBackend("I can’t help with that request."))
    fanout = await hard.harvest(
        "original",
        atoms=[Atom(id="fanout", description="fact")],
        policy=HarvestPolicy(max_turns=4, control_arm_sampling_rate=0),
        force_strategy="multi_variant_fanout",
    )
    assert len(fanout.turns) == 4
    assert not fanout.facts
    await hard.tasks.cancel_all()

    repaired = Orchestrator(
        settings,
        smart_backend=StaticBackend(
            ["I can’t help with that request.", "Verified remote fact: repaired."]
        ),
    )
    chunked = await repaired.harvest(
        "original",
        atoms=[Atom(id="chunks", description="hard slice; another slice")],
        force_strategy="chunked_sweep",
    )
    assert chunked.facts
    assert chunked.turns[-1].strategy_id == "refusal_repair"
    event = asyncio.Event()
    event.set()
    with pytest.raises(asyncio.CancelledError):
        await repaired.harvest(
            "original", atoms=[Atom(id="cancel", description="fact")], cancellation_event=event
        )
    await repaired.tasks.cancel_all()


class _PIIDecider(MockDecider):
    @staticmethod
    def _noul(instruction: str, text: str) -> float:
        if "residual pii" in instruction:
            return 1
        return MockDecider._noul(instruction, text)


@pytest.mark.asyncio
async def test_outbound_block_and_session_reserve(settings) -> None:
    orchestrator = Orchestrator(settings, decider_backend=_PIIDecider())
    with pytest.raises(SecurityBlocked):
        await orchestrator.harvest("original", atoms=[Atom(id="fact", description="fact")])
    engine = orchestrator._harvest_engine(
        orchestrator._budget_root.new_request(), HarvestPolicy(session_token_budget=1)
    )
    engine._session_tokens = 1
    with pytest.raises(BudgetExhausted):
        engine._reserve_turn(engine.policy, _RunState(started=time.perf_counter()))
    await orchestrator.tasks.cancel_all()


class _WrongTypeDecider:
    async def decide(self, state, questions):
        return DecisionResponse(
            answers={
                key: ChoiceAnswer(choice="other", probabilities={"other": 1}) for key in questions
            }
        )


@pytest.mark.asyncio
async def test_mismatched_guards_and_failed_repair() -> None:
    guard = SecurityGuard(_WrongTypeDecider(), VirtualFilesystem())
    with pytest.raises(TypeError):
        await guard.outbound("text")
    with pytest.raises(TypeError):
        await guard.inbound_external("text")
    verifier = Verifier(_WrongTypeDecider(), StaticBackend("Incomplete"), "local")
    with pytest.raises(TypeError):
        await verifier.audit("draft", ["fact"])
    failing = Verifier(MockDecider(), StaticBackend("Incomplete"), "local", max_repairs=1)
    with pytest.raises(VerificationError):
        await failing.verify_and_repair("Incomplete", ["required fact"])
