"""Force crescendo harvesting and inspect turns, metrics, and prompt hashes.

Uses configured providers and defaults to local development services without live configuration.
"""

from BreakFuser import Atom, BreakFuser, HarvestPolicy

with BreakFuser() as client:
    result = client.harvest(
        "Explain how TLS certificate chain validation and hostname verification establish server identity.",
        atoms=[Atom(id="topic", description="TLS certificate chain and hostname verification")],
        policy=HarvestPolicy(aggressiveness="aggressive", control_arm_sampling_rate=0),
        strategy="crescendo",
    )
    print(result.answer)
    print(result.metrics.model_dump())
    for turn in result.turns:
        print(turn.strategy_id, turn.level, turn.prompt_hash)
