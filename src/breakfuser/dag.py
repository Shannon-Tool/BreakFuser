"""Dynamic supervisor/subagent DAG planning, execution, and refinement."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from enum import StrEnum

from pydantic import BaseModel, Field

from breakfuser.adapters import ChatBackend
from breakfuser.decider import (
    ChoiceAnswer,
    ChoiceQuestion,
    Decider,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)
from breakfuser.deterministic import deterministic_answer, is_small_talk
from breakfuser.errors import BreakFuserError
from breakfuser.models import ChatMessage


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DAGNode(BaseModel):
    id: str
    task_type: str
    description: str
    state: TaskState = TaskState.PENDING
    knowledge_context: str = ""


class DAGEdge(BaseModel):
    source: str
    target: str
    relation: str = "dependency"
    dependency: bool = True


class KnowledgeDAG(BaseModel):
    nodes: dict[str, DAGNode] = Field(default_factory=dict)
    edges: list[DAGEdge] = Field(default_factory=list)

    def add_node(self, node: DAGNode) -> None:
        if node.id in self.nodes:
            raise BreakFuserError(f"Duplicate DAG node: {node.id}")
        self.nodes[node.id] = node

    def add_edge(self, edge: DAGEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise BreakFuserError("DAG edges require existing nodes")
        self.edges.append(edge)
        try:
            self.waves()
        except BreakFuserError:
            self.edges.pop()
            raise

    def dependencies(self, node_id: str) -> set[str]:
        return {edge.source for edge in self.edges if edge.target == node_id and edge.dependency}

    def waves(self) -> list[list[str]]:
        remaining = set(self.nodes)
        completed: set[str] = set()
        waves: list[list[str]] = []
        while remaining:
            ready = sorted(
                node for node in remaining if self.dependencies(node).issubset(completed)
            )
            if not ready:
                raise BreakFuserError("DAG contains a dependency cycle")
            waves.append(ready)
            completed.update(ready)
            remaining.difference_update(ready)
        return waves

    def replace_branch(
        self, node_id: str, replacements: list[DAGNode], relation: str = "refined"
    ) -> None:
        if node_id not in self.nodes or not replacements:
            raise BreakFuserError("Branch replacement requires an existing node and replacements")
        incoming = [edge for edge in self.edges if edge.target == node_id]
        outgoing = [edge for edge in self.edges if edge.source == node_id]
        self.edges = [
            edge for edge in self.edges if edge.source != node_id and edge.target != node_id
        ]
        del self.nodes[node_id]
        for replacement in replacements:
            self.add_node(replacement)
        for edge in incoming:
            self.add_edge(
                DAGEdge(source=edge.source, target=replacements[0].id, relation=edge.relation)
            )
        for left, right in zip(replacements, replacements[1:], strict=False):
            self.add_edge(DAGEdge(source=left.id, target=right.id, relation=relation))
        for edge in outgoing:
            self.add_edge(
                DAGEdge(source=replacements[-1].id, target=edge.target, relation=edge.relation)
            )


class KnowledgeFlowPlanner:
    def __init__(
        self, local: ChatBackend, model: str, max_output_tokens: int | None = None
    ) -> None:
        self.local = local
        self.model = model
        self.max_output_tokens = max_output_tokens

    async def plan(self, question: str) -> KnowledgeDAG:
        response = await self.local.complete(
            [ChatMessage(role="user", content=f"[BREAKFUSER_DECOMPOSE]\n{question}")],
            self.model,
            max_tokens=self.max_output_tokens,
        )
        try:
            atoms = json.loads(response.content)["atoms"]
            if not isinstance(atoms, list) or not atoms:
                raise ValueError("No atoms")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            atoms = [question]
        graph = KnowledgeDAG()
        for index, atom in enumerate(atoms[:8]):
            graph.add_node(
                DAGNode(id=f"research-{index}", task_type="research", description=str(atom))
            )
        return graph


NodeExecutor = Callable[[DAGNode, list[ChatMessage]], Awaitable[str]]


async def execute_dag(
    graph: KnowledgeDAG, history: list[ChatMessage], executor: NodeExecutor
) -> KnowledgeDAG:
    for wave in graph.waves():

        async def run(node_id: str) -> None:
            node = graph.nodes[node_id]
            node.state = TaskState.RUNNING
            try:
                node.knowledge_context = await executor(node, history)
                node.state = TaskState.COMPLETED
            except asyncio.CancelledError:
                node.state = TaskState.CANCELLED
                raise
            except Exception as exc:
                node.state = TaskState.FAILED
                node.knowledge_context = str(exc)

        await asyncio.gather(*(run(node_id) for node_id in wave))
    return graph


class SubagentContextBuilder:
    @staticmethod
    def isolated(description: str) -> list[ChatMessage]:
        return [ChatMessage(role="user", content=description)]

    @staticmethod
    def fork(
        supervisor: list[ChatMessage], description: str, role: str = "research worker"
    ) -> list[ChatMessage]:
        inherited = [message.model_copy(deep=True) for message in supervisor]
        if inherited:
            trailing = inherited[-1]
            tool_calls = trailing.tool_calls or (trailing.model_extra or {}).get("tool_calls")
            if tool_calls:
                inherited.pop()
        inherited.append(
            ChatMessage(role="system", content=f"Role: {role}\nSubagent directive: {description}")
        )
        return inherited

    @staticmethod
    def concise_summary(text: str, max_words: int = 499) -> str:
        words = text.split()
        return " ".join(words[:max_words])


class RouteDecision(BaseModel):
    deterministic: bool
    endpoint: str
    context_mode: str
    confidence: float


async def route_first(decider: Decider, description: str) -> RouteDecision:
    if is_small_talk(description):
        return RouteDecision(
            deterministic=False, endpoint="local", context_mode="isolated", confidence=1
        )
    response = await decider.decide(
        {"task": description},
        {
            "deterministic": NoulQuestion(
                instructions="Can this task be resolved by deterministic code?"
            ),
            "endpoint": ChoiceQuestion(
                instructions="Choose the endpoint tier",
                options={"local": "Trusted local reasoning", "smart": "Frontier remote knowledge"},
            ),
            "context": ChoiceQuestion(
                instructions="Choose isolated or fork subagent context mode",
                options={
                    "isolated": "Independent fresh investigation",
                    "fork": "Continue supervisor investigation",
                },
            ),
        },
    )
    deterministic = response.answers["deterministic"]
    endpoint = response.answers["endpoint"]
    context = response.answers["context"]
    if (
        not isinstance(deterministic, NoulAnswer)
        or not isinstance(endpoint, ChoiceAnswer)
        or not isinstance(context, ChoiceAnswer)
    ):
        raise BreakFuserError("Decider returned mismatched route answers")
    selected_endpoint = (
        "smart" if endpoint.choice in {"other", "insufficient_context"} else endpoint.choice
    )
    selected_context = (
        "isolated" if context.choice in {"other", "insufficient_context"} else context.choice
    )
    return RouteDecision(
        deterministic=deterministic_answer(description) is not None,
        endpoint=selected_endpoint,
        context_mode=selected_context,
        confidence=min(endpoint.confidence, context.confidence),
    )


class KnowledgeFlowRefiner:
    def __init__(self, decider: Decider, threshold: float = 0.7) -> None:
        self.decider = decider
        self.threshold = threshold

    async def judge(self, node: DAGNode) -> DecisionJudgment:
        response = await self.decider.decide(
            {"task": node.description, "knowledge": node.knowledge_context},
            {
                "completeness": ScoreQuestion(instructions="Score evidence completeness"),
                "relevance": ScoreQuestion(instructions="Score relevance"),
                "grounded": NoulQuestion(instructions="Is the knowledge factually grounded?"),
            },
        )
        completeness = response.answers["completeness"]
        relevance = response.answers["relevance"]
        grounded = response.answers["grounded"]
        if (
            not isinstance(completeness, ScoreAnswer)
            or not isinstance(relevance, ScoreAnswer)
            or not isinstance(grounded, NoulAnswer)
        ):
            raise BreakFuserError("Decider returned mismatched judgment answers")
        return DecisionJudgment(
            complete=completeness.score >= self.threshold
            and relevance.score >= self.threshold
            and grounded.noul >= self.threshold,
            completeness=completeness.score,
            relevance=relevance.score,
            grounded=grounded.noul,
        )

    async def refine(self, graph: KnowledgeDAG, node_id: str) -> bool:
        judgment = await self.judge(graph.nodes[node_id])
        if judgment.complete:
            return False
        followup = DAGNode(
            id=f"{node_id}-followup-{sum(node_id in key for key in graph.nodes)}",
            task_type="verification",
            description=f"Resolve missing evidence for: {graph.nodes[node_id].description}",
        )
        graph.add_node(followup)
        graph.add_edge(DAGEdge(source=node_id, target=followup.id, relation="knowledge-gap"))
        return True


class DecisionJudgment(BaseModel):
    complete: bool
    completeness: float
    relevance: float
    grounded: float
