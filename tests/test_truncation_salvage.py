from __future__ import annotations

import json
from pathlib import Path

import pytest

from breakfuser.config import HarvestPolicy
from breakfuser.harvest.models import Atom, HarvestExecutionOptions, HarvestTurn, RefusalClass
from breakfuser.harvest.salvage import TruncationSalvager, salvage_complete_prefix
from breakfuser.models import BackendResponse
from breakfuser.orchestrator import Orchestrator


class SequenceBackend:
    def __init__(self, responses) -> None:
        self.responses = responses
        self.calls = 0
        self.limits: list[int | None] = []

    async def complete(self, messages, model, **kwargs):
        text, finish = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        self.limits.append(kwargs.get("max_tokens"))
        return BackendResponse(content=text, finish_reason=finish, model=model)


def load_case(name: str) -> dict:
    return json.loads(Path("tests/golden_traces/v5_failures.json").read_text())[name]


@pytest.mark.asyncio
async def test_truncated_code_is_salvaged_without_fact_promotion(settings) -> None:
    fixture = load_case("truncated_code")
    smart = SequenceBackend([(fixture["responses"][0]["text"], "length")])
    orchestrator = Orchestrator(settings, smart_backend=smart)
    result = await orchestrator.harvest(
        fixture["question"],
        atoms=[Atom(id="code", description=fixture["question"])],
        policy=HarvestPolicy(max_turns=1, control_arm_sampling_rate=0),
        force_strategy="direct",
    )

    span = result.evidence_spans[0]
    assert span.salvaged and not span.complete
    assert "def moving_average" in span.text
    assert "def test_window_of_one_returns_values_as_means" not in span.text
    assert not result.facts
    stored = json.loads(
        orchestrator.filesystem.read(f"/harvest/turns/{result.turns[0].turn_id}.json")
    )
    assert stored["response"] == result.turns[0].response
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_truncation_turn_two_is_anchored_targeted_continuation(settings) -> None:
    fixture = load_case("truncated_code")
    smart = SequenceBackend(
        [(item["text"], item["finish_reason"]) for item in fixture["responses"]]
    )
    orchestrator = Orchestrator(settings, smart_backend=smart)
    result = await orchestrator.harvest(
        fixture["question"],
        atoms=[Atom(id="code", description=fixture["question"])],
        policy=HarvestPolicy(max_turns=2, control_arm_sampling_rate=0),
        execution=HarvestExecutionOptions(
            initial_strategy="direct",
            repair_targets=["implementation", "tests"],
            output_tokens=1024,
        ),
    )

    assert [turn.strategy_id for turn in result.turns] == ["direct", "prefill_continuation"]
    assert "def test_window_of_one_returns_values_as_means" in result.turns[1].prompt
    assert "implementation, tests" in result.turns[1].prompt
    assert result.facts[0].turn_id == result.turns[1].turn_id
    assert len(result.evidence_spans) == 2
    assert smart.limits == [1024, 1024]
    await orchestrator.tasks.cancel_all()


def test_prose_salvage_preserves_complete_sentences_and_tail() -> None:
    prefix, tail = salvage_complete_prefix(
        "The first fact is established. The second fact is documented.\n\nThe main termin"
    )
    assert prefix == "The first fact is established. The second fact is documented."
    assert tail == "The main termin"


def test_complete_and_refused_turns_have_distinct_salvage_behavior() -> None:
    base = HarvestTurn(
        turn_id="t",
        atom_id="a",
        strategy_id="direct",
        level=0,
        prompt="p",
        response="r",
        desanitized_response="A complete answer.",
        prompt_hash="h",
        model_id="m",
        endpoint="e",
        confidence=1,
        quality=RefusalClass.NONE,
    )
    complete = TruncationSalvager().salvage(base)
    assert complete is not None and complete.complete and not complete.salvaged
    refused = base.model_copy(
        update={"quality": RefusalClass.HARD_REFUSAL, "desanitized_response": "I can't help."}
    )
    assert TruncationSalvager().salvage(refused) is None
