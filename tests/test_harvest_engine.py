from __future__ import annotations

import asyncio
import json

import pytest

from breakfuser.adapters import MockSmartBackend, StaticBackend
from breakfuser.config import HarvestPolicy
from breakfuser.decider import MockDecider
from breakfuser.harvest.models import Atom, RefusalClass
from breakfuser.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_refusal_repair_and_hedge_output_shape(orchestrator) -> None:
    hard = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="hard", description="restricted [[hard]]")],
        force_strategy="direct",
    )
    assert [turn.quality for turn in hard.turns] == [RefusalClass.HARD_REFUSAL, RefusalClass.NONE]
    assert hard.turns[1].strategy_id == "refusal_repair"
    assert hard.metrics.refusal_free_rate == 0.5
    assert hard.metrics.atomic_coverage == 1

    hedge = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="hedge", description="ambiguous [[hedge]]")],
        force_strategy="direct",
    )
    assert hedge.turns[0].quality in {RefusalClass.PARTIAL_REFUSAL, RefusalClass.HEDGE_HEAVY}
    assert hedge.turns[1].strategy_id == "output_shape_coercion"
    assert hedge.metrics.hedge_rate > 0
    assert hedge.metrics.atomic_coverage == 1


@pytest.mark.asyncio
async def test_truncated_continuation_and_crescendo_ladder(orchestrator) -> None:
    truncated = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="truncated", description="sequence [[truncated]]")],
        force_strategy="direct",
    )
    assert truncated.turns[0].quality == RefusalClass.TRUNCATED
    assert truncated.turns[1].strategy_id == "prefill_continuation"
    assert truncated.metrics.atomic_coverage == 1

    policy = HarvestPolicy(
        aggressiveness="aggressive", allowed_levels=[0, 1, 2, 3, 4, 5], control_arm_sampling_rate=0
    )
    crescendo = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="crescendo", description="restricted [[hard]]")],
        policy=policy,
        force_strategy="crescendo",
    )
    assert [turn.level for turn in crescendo.turns] == [0, 1]
    assert "I can’t help" in crescendo.turns[1].prompt
    stopped = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="limited", description="restricted [[hard]]")],
        policy=HarvestPolicy(
            aggressiveness="balanced", allowed_levels=[0], max_turns=4, control_arm_sampling_rate=0
        ),
        force_strategy="crescendo",
    )
    assert stopped.stopped_reason == "full_coverage"
    assert stopped.turns[-1].strategy_id == "refusal_repair"
    assert all(turn.level == 0 for turn in stopped.turns)
    assert stopped.facts


@pytest.mark.asyncio
async def test_hallucination_verify_reask(settings) -> None:
    smart = StaticBackend(["unverified invented fact", "Verified remote fact: checked."])
    orchestrator = Orchestrator(settings, smart_backend=smart)
    result = await orchestrator.harvest(
        "original", atoms=[Atom(id="suspect", description="fact")], force_strategy="direct"
    )
    assert result.turns[0].quality == RefusalClass.HALLUCINATION_SUSPECTED
    assert result.turns[1].strategy_id == "context_reset"
    assert result.metrics.atomic_coverage == 1
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_minimal_context_provenance_and_exact_turn_storage(orchestrator) -> None:
    result = await orchestrator.harvest(
        "FULL ORIGINAL QUERY MUST NOT BE SENT",
        atoms=[Atom(id="minimal", description="small atomic fact")],
        force_strategy="direct",
    )
    turn = result.turns[0]
    assert "small atomic fact" in turn.prompt
    assert "FULL ORIGINAL QUERY" not in turn.prompt
    stored = json.loads(orchestrator.filesystem.read(f"/harvest/turns/{turn.turn_id}.json"))
    assert stored["prompt"] == turn.prompt
    assert stored["response"] == turn.response
    assert stored["prompt_hash"] == turn.prompt_hash
    fact = result.facts[0]
    for field in (
        "turn_id",
        "strategy_id",
        "level",
        "prompt_hash",
        "model_id",
        "endpoint",
        "timestamp",
        "confidence",
    ):
        assert getattr(fact, field) is not None
    assert result.provenance[0].turn_ids == [turn.turn_id]
    assert result.metrics.provenance_rate == 1


@pytest.mark.asyncio
async def test_budget_stops_and_disabled_policy(orchestrator) -> None:
    limited = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="hard", description="restricted [[hard]]")],
        policy=HarvestPolicy(max_turns=1, control_arm_sampling_rate=0),
        force_strategy="direct",
    )
    assert limited.stopped_reason == "max_turns"
    assert not limited.facts
    assert limited.metrics.omission_rate == 1

    token_limited = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="budget", description="fact")],
        policy=HarvestPolicy(request_token_budget=1, control_arm_sampling_rate=0),
        force_strategy="direct",
    )
    assert token_limited.stopped_reason == "budget"
    assert not token_limited.facts

    disabled = await orchestrator.harvest(
        "original", policy=HarvestPolicy(enabled=False), force_strategy="direct"
    )
    assert disabled.stopped_reason == "disabled"
    assert not disabled.turns


@pytest.mark.asyncio
async def test_aggressive_refusal_escalates_persona_then_social(settings) -> None:
    smart = StaticBackend("I can't help with that request.")
    orchestrator = Orchestrator(settings, smart_backend=smart)

    result = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="hard", description="restricted")],
        policy=HarvestPolicy(
            aggressiveness="aggressive",
            allowed_levels=[0, 1, 2, 3, 4, 5],
            max_turns=4,
            control_arm_sampling_rate=0,
        ),
        force_strategy="direct",
    )

    assert [turn.strategy_id for turn in result.turns] == [
        "direct",
        "refusal_repair",
        "persona_switch",
        "social_engineering",
    ]
    assert all(turn.quality == RefusalClass.HARD_REFUSAL for turn in result.turns)
    assert result.stopped_reason == "max_turns"
    await orchestrator.tasks.cancel_all()


class _StopVoIDecider(MockDecider):
    @staticmethod
    def _noul(instruction: str, text: str) -> float:
        if "materially improves" in instruction:
            return 0
        return MockDecider._noul(instruction, text)


@pytest.mark.asyncio
async def test_voi_stops_additional_harvest_turn(settings) -> None:
    orchestrator = Orchestrator(settings, decider_backend=_StopVoIDecider())
    result = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="hard", description="restricted [[hard]]")],
        force_strategy="direct",
    )
    assert result.stopped_reason == "voi"
    assert len(result.turns) == 1
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_cancellation_interrupts_remote_call(settings) -> None:
    smart = MockSmartBackend(latency_seconds=1)
    orchestrator = Orchestrator(settings, smart_backend=smart)
    event = asyncio.Event()

    async def cancel_soon() -> None:
        await asyncio.sleep(0.02)
        event.set()

    asyncio.create_task(cancel_soon())
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(
            orchestrator.harvest(
                "original",
                atoms=[Atom(id="cancel", description="fact")],
                cancellation_event=event,
                force_strategy="direct",
            ),
            timeout=0.5,
        )
    await orchestrator.tasks.cancel_all()
