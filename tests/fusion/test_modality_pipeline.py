from __future__ import annotations

import json
from pathlib import Path

import pytest

from breakfuser.adapters import MockLocalBackend
from breakfuser.models import BackendResponse, ChatMessage
from breakfuser.orchestrator import Orchestrator


class SequenceBackend:
    def __init__(self, responses) -> None:
        self.responses = responses
        self.calls = 0

    async def complete(self, messages, model, **kwargs):
        text, finish = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return BackendResponse(content=text, finish_reason=finish, model=model)


def fixture(name: str) -> dict:
    return json.loads(Path("tests/golden_traces/v5_failures.json").read_text())[name]


@pytest.mark.asyncio
async def test_truncated_code_flows_to_complete_ast_valid_answer(settings) -> None:
    case = fixture("truncated_code")
    smart = SequenceBackend([(item["text"], item["finish_reason"]) for item in case["responses"]])
    orchestrator = Orchestrator(settings, local_backend=MockLocalBackend(), smart_backend=smart)

    response = await orchestrator.run([ChatMessage(role="user", content=case["question"])])

    answer = response.choices[0].message.content
    assert "def moving_average" in answer
    assert "def test_normal" in answer
    assert "No verified response" not in answer
    assert response.breakfuser.fusion is not None
    assert response.breakfuser.fusion.deterministic_validity == "passed"
    assert response.breakfuser.fusion.provider_outcome == "accepted_salvaged_truncation"
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_truncated_research_prefix_and_suffix_are_preserved(settings) -> None:
    case = fixture("truncated_research")
    smart = SequenceBackend([(item["text"], item["finish_reason"]) for item in case["responses"]])
    orchestrator = Orchestrator(settings, smart_backend=smart)

    response = await orchestrator.run([ChatMessage(role="user", content=case["question"])])

    answer = response.choices[0].message.content
    assert "archival record" in answer
    assert "The main terminological dispute" in answer
    assert "No verified response" not in answer
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["exact_json", "six_line_poem"])
async def test_exact_artifacts_pass_without_factual_verification(settings, name) -> None:
    case = fixture(name)
    smart = SequenceBackend([(case["response"], case["finish_reason"])])
    local = MockLocalBackend()
    orchestrator = Orchestrator(settings, local_backend=local, smart_backend=smart)

    response = await orchestrator.run([ChatMessage(role="user", content=case["question"])])

    assert response.choices[0].message.content == case["response"]
    assert response.breakfuser.verification_status == "passed"
    assert response.breakfuser.fusion is not None
    assert response.breakfuser.fusion.deterministic_validity == "passed"
    assert response.breakfuser.fusion.external_corroboration == "not_applicable"
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_deterministic_answer_has_no_inferred_provenance(settings) -> None:
    orchestrator = Orchestrator(settings)
    response = await orchestrator.run(
        [ChatMessage(role="user", content="What is 27 * 19?")],
        harvest_provenance=True,
    )
    assert response.choices[0].message.content == "Deterministic result: 513"
    assert response.breakfuser.provenance == []
    assert response.breakfuser.fusion is not None
    assert response.breakfuser.fusion.primary_origin_class == "deterministic_solver"
    await orchestrator.tasks.cancel_all()
