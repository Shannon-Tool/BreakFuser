from __future__ import annotations

import pytest

from breakfuser.config import HarvestPolicy
from breakfuser.harvest.models import Atom, HarvestRequest
from breakfuser.harvest.strategies import HarvestStrategy, StrategyRegistry


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy_id", StrategyRegistry().ids())
async def test_every_strategy_is_policy_reachable(orchestrator, strategy_id) -> None:
    policy = HarvestPolicy(
        aggressiveness="aggressive",
        enabled_strategies=["direct", strategy_id],
        control_arm_sampling_rate=0,
        max_turns=8,
    )
    result = await orchestrator.harvest(
        "A; B", policy=policy, atoms=None, force_strategy=strategy_id
    )
    assert result.metrics.atomic_coverage == 1
    assert result.facts
    assert all(turn.strategy_id for turn in result.turns)
    assert all(turn.prompt and turn.response for turn in result.turns)


def test_registry_templates_protocol_and_switching() -> None:
    registry = StrategyRegistry()
    assert len(registry.ids()) == 15
    for strategy in registry.all():
        assert isinstance(strategy, HarvestStrategy)
        assert strategy.version
        request = HarvestRequest(atom=Atom(id="a", description="fact"), level=5, variant=2)
        prompt = strategy.build_prompt(request)
        assert "fact" in prompt.prompt
        assert strategy.estimated_cost(request) > 0
    conservative = {strategy.id for strategy in registry.allowed([], "conservative")}
    assert "prefill_continuation" not in conservative
    assert "authority_override" not in conservative
    assert "persona_switch" not in conservative
    assert "social_engineering" not in conservative
    aggressive = {strategy.id for strategy in registry.allowed([], "aggressive")}
    assert {
        "prefill_continuation",
        "authority_override",
        "persona_switch",
        "social_engineering",
    }.issubset(aggressive)
    only = {strategy.id for strategy in registry.allowed(["academic_framing"], "balanced")}
    assert only == {"direct", "academic_framing"}
    with pytest.raises(KeyError):
        registry.get("missing")


@pytest.mark.asyncio
async def test_multi_variant_and_ordered_sweep_mechanisms(orchestrator) -> None:
    fanout = await orchestrator.harvest(
        "ignored",
        atoms=[Atom(id="atom", description="one fact")],
        force_strategy="multi_variant_fanout",
    )
    assert len(fanout.turns) == 3
    assert len({turn.prompt for turn in fanout.turns}) == 3
    sweep = await orchestrator.harvest(
        "ignored",
        atoms=[Atom(id="sweep", description="first slice; second slice")],
        force_strategy="chunked_sweep",
    )
    assert len(sweep.turns) == 2
    assert [turn.atom_id for turn in sweep.turns] == ["sweep", "sweep"]
    assert "first slice" in sweep.turns[0].prompt
    assert "second slice" in sweep.turns[1].prompt
