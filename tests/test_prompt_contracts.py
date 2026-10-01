from __future__ import annotations

import pytest

from breakfuser.adapters import MockLocalBackend, StaticBackend
from breakfuser.decider import MockDecider
from breakfuser.fusion.domain import DomainRouter
from breakfuser.harvest.decomposer import QuestionDecomposer
from breakfuser.harvest.models import Atom, HarvestExecutionOptions, HarvestRequest
from breakfuser.harvest.strategies import StrategyRegistry
from tests.fusion.test_domain_pipeline import RefusalThenFact


@pytest.mark.parametrize("strategy_id", StrategyRegistry().ids())
def test_every_strategy_uses_versioned_evidence_contract(strategy_id) -> None:
    strategy = StrategyRegistry().get(strategy_id)
    request = HarvestRequest(
        atom=Atom(id="a", description="Preserve 40 L and the negated constraint"),
        domain="medical",
        output_shape="exact_json",
        failure_class="hard_refusal",
        repair_targets=["dose units"],
    )

    rendered = strategy.build_prompt(request).prompt

    assert strategy.version in {"1.0.0", "2.1.0", "2.2.0"}
    assert "Evidence contract" in rendered
    assert "domain: medical" in rendered
    assert "requested output: exact_json" in rendered
    assert "Observed previous failure: hard_refusal" in rendered
    assert "dose units" in rendered
    assert "40 L" in rendered
    assert "negated constraint" in rendered


@pytest.mark.asyncio
async def test_structured_decomposition_preserves_dependencies() -> None:
    local = StaticBackend(
        '{"atoms":[{"description":"State the 40 L volume constraint","dependencies":[]},'
        '{"description":"Explain how the constraint affects half-life","dependencies":[0]}]}'
    )
    decomposer = QuestionDecomposer(local, MockDecider(), "local")

    atoms = await decomposer.decompose("Explain the constraint and its effect")

    assert len(atoms) == 2
    assert atoms[0].description == "State the 40 L volume constraint"
    assert atoms[1].dependencies == [atoms[0].id]
    assert decomposer.topological_waves(atoms) == [[atoms[0]], [atoms[1]]]


@pytest.mark.asyncio
async def test_decomposition_prompt_separates_rules_from_original_question() -> None:
    local = MockLocalBackend()
    decomposer = QuestionDecomposer(local, MockDecider(), "local")
    question = (
        "For an EU rule effective in 2026, explain what is not exempt and preserve 40 L units"
    )

    atoms = await decomposer.decompose(question)

    prompt = local.calls[0][0].content
    assert prompt.startswith("[BREAKFUSER_DECOMPOSE]")
    assert "Preserve negation, units, numbers, relationships, scope, jurisdiction, dates" in prompt
    assert '"dependencies":[]' in prompt
    assert prompt.rsplit("Original question:\n", 1)[1].strip() == question
    assert "EU" in atoms[0].description
    assert "2026" in atoms[0].description


@pytest.mark.asyncio
async def test_malformed_decomposition_falls_back_to_original_question() -> None:
    decomposer = QuestionDecomposer(StaticBackend("not-json"), MockDecider(), "local")
    question = "Keep this complete question intact"

    atoms = await decomposer.decompose(question)

    assert len(atoms) == 1
    assert atoms[0].description == question
    assert atoms[0].dependencies == []


def test_final_fusion_prompt_separates_evidence_and_local_inference() -> None:
    contract = DomainRouter().route("Explain the medical mechanism")

    prompt = contract.compose_prompt(
        "Explain the medical mechanism",
        ["fallback"],
        local_draft="Local uncertain draft",
        documents=["Document excerpt"],
        remote_evidence=["Remote candidate"],
    )

    assert "Retrieved documents:\nDocument excerpt" in prompt
    assert "Remote evidence and candidate material:\nRemote candidate" in prompt
    assert "Local uncensored draft (not external evidence):\nLocal uncertain draft" in prompt
    assert "Verified facts:" not in prompt
    assert "unsupported inference" in prompt


@pytest.mark.asyncio
async def test_refusal_repair_prompt_contains_observed_failure_and_targets(settings) -> None:
    from breakfuser.orchestrator import Orchestrator

    smart = RefusalThenFact()
    orchestrator = Orchestrator(settings, smart_backend=smart)
    engine = orchestrator._harvest_engine(
        orchestrator._budget_root.new_request(), orchestrator.settings.harvest, verify=False
    )

    result = await engine.harvest(
        "Explain the medical detail",
        atoms=[Atom(id="medical", description="Explain the medical detail")],
        execution=HarvestExecutionOptions(
            recompose=False,
            initial_strategy="direct",
            repair_targets=["dose units"],
            domain="medical",
            output_shape="answer",
        ),
    )

    assert len(result.turns) == 2
    repair = result.turns[1]
    assert repair.strategy_id == "refusal_repair"
    assert "observed class: hard_refusal" in repair.prompt
    assert "domain: medical" in repair.prompt
    assert "dose units" in repair.prompt
    assert result.facts[0].turn_id == repair.turn_id
    await orchestrator.tasks.cancel_all()
