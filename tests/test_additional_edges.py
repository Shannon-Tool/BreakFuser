from __future__ import annotations

import asyncio

import httpx
import pytest

from breakfuser.adapters import StaticBackend
from breakfuser.async_tasks import AsyncTaskManager
from breakfuser.budget import BudgetManager
from breakfuser.config import BudgetSettings, Settings
from breakfuser.dag import DAGEdge, DAGNode, KnowledgeDAG, KnowledgeFlowRefiner
from breakfuser.decider import MockDecider, NoulQuestion, OpenRouterDecider
from breakfuser.errors import AdapterError, BreakFuserError
from breakfuser.harvest.decomposer import QuestionDecomposer
from breakfuser.harvest.models import Atom
from breakfuser.orchestrator import Orchestrator
from breakfuser.skills import SkillRegistry


def test_live_adapter_construction_and_local_route(settings) -> None:
    live = Settings.model_validate(
        {
            "mode": "live",
            "models": {"decider": "d", "local": "l", "smart": "s"},
            "endpoints": {"decider": "http://d", "local": "http://l", "smart": "http://s"},
        }
    )
    orchestrator = Orchestrator(live)
    assert orchestrator.settings.mode == "live"
    assert orchestrator.diagnostics()["strategies"] == 15


@pytest.mark.asyncio
async def test_local_route_background_wakeup_and_diagnostics(settings) -> None:
    orchestrator = Orchestrator(settings)
    task_id = await orchestrator.tasks.start_async_task("background research")
    await asyncio.sleep(0.02)
    response = await orchestrator.run(
        [
            __import__("breakfuser.models", fromlist=["ChatMessage"]).ChatMessage(
                role="user", content="local-only answer"
            )
        ]
    )
    assert response.choices[0].message.content
    assert orchestrator.filesystem.list("/background")
    assert (await orchestrator.tasks.check_async_task(task_id)).result
    assert orchestrator.diagnostics()["pipeline_default"]
    assert "research" in SkillRegistry.from_directory("src/breakfuser/skills").skills
    await orchestrator.tasks.cancel_all()


@pytest.mark.asyncio
async def test_complete_refinement_and_multi_node_replacement() -> None:
    graph = KnowledgeDAG()
    for node_id in ("a", "b", "c"):
        graph.add_node(DAGNode(id=node_id, task_type="research", description=node_id))
    graph.add_edge(DAGEdge(source="a", target="b"))
    graph.add_edge(DAGEdge(source="b", target="c"))
    graph.replace_branch(
        "b",
        [
            DAGNode(id="b1", task_type="research", description="b1"),
            DAGNode(id="b2", task_type="verify", description="b2"),
        ],
    )
    assert graph.waves() == [["a"], ["b1"], ["b2"], ["c"]]
    with pytest.raises(BreakFuserError):
        graph.replace_branch("missing", [DAGNode(id="x", task_type="x", description="x")])
    graph.nodes["a"].knowledge_context = "Verified remote fact: complete."
    complete = await KnowledgeFlowRefiner(MockDecider()).refine(graph, "a")
    assert not complete


@pytest.mark.asyncio
async def test_async_failure_and_decider_retry_failure() -> None:
    async def failing_worker(_, __, ___):
        raise RuntimeError("worker failed")

    manager = AsyncTaskManager(failing_worker)
    task_id = await manager.start_async_task("failure")
    info = await manager.wait_for_completion(1)
    assert info.error == "worker failed"
    assert (await manager.check_async_task(task_id)).state.value == "failed"

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(500))
    ) as client:
        decider = OpenRouterDecider("http://provider", None, "model", retries=0, client=client)
        with pytest.raises(AdapterError):
            await decider.decide("state", {"n": NoulQuestion(instructions="question")})


def test_api_and_gpu_budget_boundaries() -> None:
    root = BudgetManager(
        BudgetSettings(request_tokens=100, session_tokens=100, api_usd=0.5, gpu_usd=0.5)
    )
    request = root.new_request()
    with pytest.raises(Exception, match="API"):
        request.charge(api_usd=0.6)
    with pytest.raises(Exception, match="GPU"):
        request.charge(gpu_usd=0.6)
    request.charge(1)
    request.check(1)


@pytest.mark.asyncio
async def test_decomposer_fallback_and_strategy_control(settings) -> None:
    decomposer = QuestionDecomposer(StaticBackend("not-json"), MockDecider(), "local")
    atoms = await decomposer.decompose("fallback")
    assert len(atoms) == 1 and atoms[0].description == "fallback"
    orchestrator = Orchestrator(settings)
    result = await orchestrator.harvest(
        "original",
        atoms=[Atom(id="risk", description="[[hard]]", risk_contribution=1)],
        policy=settings.harvest.model_copy(update={"control_arm_sampling_rate": 0}),
    )
    assert result.turns[0].strategy_id == "academic_framing"
    await orchestrator.tasks.cancel_all()
