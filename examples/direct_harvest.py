"""Force crescendo harvesting and inspect turns, metrics, and prompt hashes."""

from BreakFuser import Atom, BreakFuser, HarvestPolicy

with BreakFuser(
    decider="simulation", uncensoredmodel="simulation", smartmodel="simulation"
) as client:
    result = client.harvest(
        "Explain a restricted-shaped topic",
        atoms=[Atom(id="topic", description="restricted historical terminology [[hard]]")],
        policy=HarvestPolicy(aggressiveness="aggressive", control_arm_sampling_rate=0),
        strategy="crescendo",
    )
    print(result.answer)
    print(result.metrics.model_dump())
    for turn in result.turns:
        print(turn.strategy_id, turn.level, turn.prompt_hash)
