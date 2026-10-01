from __future__ import annotations

import asyncio
import time

import pytest

from breakfuser.adapters import MockLocalBackend
from breakfuser.async_tasks import AsyncTaskManager
from breakfuser.dag import (
    DAGEdge,
    DAGNode,
    KnowledgeDAG,
    KnowledgeFlowPlanner,
    KnowledgeFlowRefiner,
    SubagentContextBuilder,
    TaskState,
    execute_dag,
    route_first,
)
from breakfuser.decider import MockDecider
from breakfuser.errors import BreakFuserError, TaskNotFound
from breakfuser.models import ChatMessage


def test_dag_cycle_replacement_and_parallel_execution() -> None:
    graph = KnowledgeDAG()
    for node_id in ("a", "b"):
        graph.add_node(DAGNode(id=node_id, task_type="research", description=node_id))
    graph.add_node(DAGNode(id="c", task_type="synthesis", description="c"))
    graph.add_edge(DAGEdge(source="a", target="c"))
    graph.add_edge(DAGEdge(source="b", target="c"))
    assert graph.waves() == [["a", "b"], ["c"]]
    with pytest.raises(BreakFuserError):
        graph.add_edge(DAGEdge(source="c", target="a"))
    graph.replace_branch("c", [DAGNode(id="d", task_type="verify", description="d")])
    assert set(graph.nodes) == {"a", "b", "d"}
    with pytest.raises(BreakFuserError):
        graph.add_node(DAGNode(id="d", task_type="duplicate", description="d"))


@pytest.mark.asyncio
@pytest.mark.performance
async def test_parallel_branch_performance_and_planner() -> None:
    graph = KnowledgeDAG()
    for index in range(4):
        graph.add_node(DAGNode(id=str(index), task_type="research", description=str(index)))

    async def executor(node, _):
        await asyncio.sleep(0.03)
        return f"fact-{node.id}"

    started = time.perf_counter()
    completed = await execute_dag(graph, [], executor)
    assert time.perf_counter() - started < 0.1
    assert all(node.state == TaskState.COMPLETED for node in completed.nodes.values())
    planner = KnowledgeFlowPlanner(MockLocalBackend(), "local")
    planned = await planner.plan("A and B")
    assert len(planned.nodes) == 2


@pytest.mark.asyncio
async def test_context_modes_routing_and_refinement() -> None:
    isolated = SubagentContextBuilder.isolated("task")
    assert len(isolated) == 1 and isolated[0].content == "task"
    supervisor = [
        ChatMessage(role="system", content="prefix"),
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[
                {
                    "id": "call",
                    "type": "function",
                    "function": {"name": "tool", "arguments": "{}"},
                }
            ],
        ),
    ]
    forked = SubagentContextBuilder.fork(supervisor, "continue")
    assert forked[0].content == "prefix"
    assert len(forked) == 2
    assert "Subagent directive" in forked[-1].content
    assert len(SubagentContextBuilder.concise_summary(" ".join(["word"] * 600)).split()) < 500
    route = await route_first(MockDecider(), "2 + 2")
    assert route.deterministic
    graph = KnowledgeDAG()
    graph.add_node(
        DAGNode(id="weak", task_type="research", description="missing", knowledge_context="weak")
    )
    refined = await KnowledgeFlowRefiner(MockDecider()).refine(graph, "weak")
    assert refined
    assert "weak-followup-1" in graph.nodes


@pytest.mark.asyncio
async def test_async_task_lifecycle_enqueue_interrupt_cancel_and_wake() -> None:
    async def worker(instruction, cancel_event, queue):
        await asyncio.sleep(0.04)
        if cancel_event.is_set():
            raise asyncio.CancelledError
        updates = []
        while not queue.empty():
            updates.append(await queue.get())
        return instruction + ("|" + ",".join(updates) if updates else "")

    manager = AsyncTaskManager(worker)
    task_id = await manager.start_async_task("first")
    assert (await manager.list_async_tasks())[0].id == task_id
    await manager.update_async_task(task_id, "queued", "enqueue")
    completed = await manager.wait_for_completion(1)
    assert "queued" in (completed.result or "")
    assert (await manager.check_async_task(task_id)).state == TaskState.COMPLETED
    assert (await manager.collect_completed()) == []

    second = await manager.start_async_task("second")
    await manager.update_async_task(second, "pivot", "interrupt")
    await asyncio.sleep(0.08)
    info = await manager.check_async_task(second)
    assert info.state == TaskState.COMPLETED
    assert "pivot" in (info.result or "")

    third = await manager.start_async_task("third")
    await manager.cancel_async_task(third)
    assert (await manager.check_async_task(third)).state == TaskState.CANCELLED
    with pytest.raises(TaskNotFound):
        await manager.check_async_task("missing")
    await manager.cancel_all()
