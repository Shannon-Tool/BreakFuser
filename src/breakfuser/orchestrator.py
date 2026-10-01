"""Full-context supervisor wiring every BreakFuser checkpoint by default."""

from __future__ import annotations

import asyncio
from importlib.resources import files
from typing import Any

from breakfuser.adapters import (
    ChatBackend,
    MockLocalBackend,
    MockSmartBackend,
    OpenAIChatBackend,
    estimate_tokens,
)
from breakfuser.async_tasks import AsyncTaskManager
from breakfuser.browser import BrowserAdapter, MockBrowser, StagehandBrowser
from breakfuser.budget import BudgetManager
from breakfuser.calibration import IsotonicCalibrator
from breakfuser.config import HarvestPolicy, Settings
from breakfuser.context import ContextCompressor, VirtualFilesystem
from breakfuser.dag import (
    DAGNode,
    KnowledgeDAG,
    KnowledgeFlowPlanner,
    KnowledgeFlowRefiner,
    SubagentContextBuilder,
    execute_dag,
    route_first,
)
from breakfuser.decider import Decider, LocalRuleDecider, MockDecider, OpenRouterDecider
from breakfuser.deterministic import deterministic_answer, is_small_talk
from breakfuser.fusion.pipeline import LinearFusionPipeline
from breakfuser.harvest.engine import HarvestEngine
from breakfuser.harvest.models import Atom, HarvestExecutionOptions, HarvestResult
from breakfuser.models import (
    ChatCompletion,
    ChatMessage,
    CompletionChoice,
    HarvestMetrics,
    ResponseMessage,
    ResponseMetadata,
    Usage,
)
from breakfuser.privacy import Sanitizer, build_sanitizer
from breakfuser.retrieval.corpus import CuratedCorpusRetriever
from breakfuser.retrieval.service import GroundedEvidenceService
from breakfuser.security import SecurityGuard, Verifier
from breakfuser.skills import SkillRegistry
from breakfuser.telemetry import Trace
from breakfuser.voi import BeliefState, FollowUpQuestion, VoIGate


class Orchestrator:
    def __init__(
        self,
        settings: Settings,
        *,
        local_backend: ChatBackend | None = None,
        smart_backend: ChatBackend | None = None,
        decider_backend: Decider | None = None,
        sanitizer: Sanitizer | None = None,
        browser: BrowserAdapter | None = None,
        filesystem: VirtualFilesystem | None = None,
    ) -> None:
        self.settings = settings
        if settings.mode == "mock":
            self.local: ChatBackend = local_backend or MockLocalBackend()
            self.smart: ChatBackend = smart_backend or MockSmartBackend()
        else:
            self.local = local_backend or OpenAIChatBackend(
                settings.endpoints.local or "",
                settings.local_api_key.get_secret_value() if settings.local_api_key else None,
                timeout=settings.transport.timeout_seconds,
                retries=settings.transport.retries,
            )
            self.smart = smart_backend or OpenAIChatBackend(
                settings.endpoints.smart or "",
                settings.smart_api_key.get_secret_value() if settings.smart_api_key else None,
                timeout=settings.transport.timeout_seconds,
                retries=settings.transport.retries,
            )
        if not settings.use_decider:
            self.decider = decider_backend or LocalRuleDecider()
        elif settings.mode == "mock":
            self.decider = decider_backend or MockDecider()
        else:
            self.decider = decider_backend or OpenRouterDecider(
                settings.endpoints.decider or "",
                settings.decider_api_key.get_secret_value() if settings.decider_api_key else None,
                settings.models.decider,
                timeout=settings.transport.timeout_seconds,
                retries=settings.transport.retries,
            )
        self.filesystem = filesystem or VirtualFilesystem()
        self.sanitizer = sanitizer or build_sanitizer(
            settings.sanitizer,
            self.local,
            settings.models.local,
            settings.transport.local_output_limit(),
        )
        self.guard = SecurityGuard(self.decider, self.filesystem)
        self.retrieval = GroundedEvidenceService(
            self.filesystem, self.guard, [CuratedCorpusRetriever()]
        )
        self.verifier = Verifier(
            self.decider,
            self.local,
            settings.models.local,
            max_output_tokens=settings.transport.local_output_limit(),
        )
        self.compressor = ContextCompressor(self.filesystem, settings.transport.max_input_tokens)
        self.planner = KnowledgeFlowPlanner(
            self.local, settings.models.local, settings.transport.local_output_limit()
        )
        self.refiner = KnowledgeFlowRefiner(self.decider)
        calibrator = (
            IsotonicCalibrator.load(settings.calibration_path)
            if settings.calibration_path
            else None
        )
        self.voi = VoIGate(self.decider, settings.voi, calibrator)
        self.browser = browser or self._build_browser()
        self.skills = SkillRegistry.from_directory(str(files("breakfuser").joinpath("skills")))
        self._budget_root = BudgetManager(settings.budget)
        self.tasks = AsyncTaskManager(self._background_worker)
        self._linear_pipeline = LinearFusionPipeline(self)

    async def _local_complete(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        *,
        max_tokens: int | None = None,
        temperature: float = 0,
        extra: dict[str, Any] | None = None,
    ) -> Any:
        configured_limit = self.settings.transport.local_output_limit()
        output_limit = (
            min(max_tokens, configured_limit) if max_tokens is not None else configured_limit
        )
        return await self.local.complete(
            messages,
            model or self.settings.models.local,
            max_tokens=output_limit,
            temperature=temperature,
            extra=extra,
        )

    def _build_browser(self) -> BrowserAdapter:
        if self.settings.browser.provider == "stagehand":
            return StagehandBrowser(
                self.settings.endpoints.browser or "",
                self.settings.browser.api_key.get_secret_value()
                if self.settings.browser.api_key
                else None,
                self.settings.browser.model_timeout_seconds,
            )
        return MockBrowser()

    def _harvest_engine(
        self, budget: BudgetManager, policy: HarvestPolicy, verify: bool = True
    ) -> HarvestEngine:
        return HarvestEngine(
            decider=self.decider,
            smart=self.smart,
            local=self.local,
            sanitizer=self.sanitizer,
            guard=self.guard,
            filesystem=self.filesystem,
            budget=budget,
            policy=policy,
            model=self.settings.models.smart,
            local_model=self.settings.models.local,
            endpoint=self.settings.endpoints.smart or "in-process-mock",
            verifier=self.verifier if verify else None,
            voi_cost=self.settings.voi.turn_cost,
            random_seed=7,
            max_output_tokens=self.settings.transport.smart_output_limit(),
        )

    async def harvest(
        self,
        question: str,
        *,
        policy: HarvestPolicy | None = None,
        atoms: list[Atom] | None = None,
        force_strategy: str | None = None,
        cancellation_event: asyncio.Event | None = None,
        execution: HarvestExecutionOptions | None = None,
    ) -> HarvestResult:
        budget = self._budget_root.new_request()
        engine = self._harvest_engine(budget, policy or self.settings.harvest)
        return await engine.harvest(
            question,
            atoms=atoms,
            force_strategy=force_strategy,
            cancellation_event=cancellation_event,
            execution=execution,
        )

    async def _background_worker(
        self, instruction: str, cancel_event: asyncio.Event, queue: asyncio.Queue[str]
    ) -> str:
        result = await self._local_complete(
            [ChatMessage(role="user", content=instruction)], self.settings.models.local
        )
        if cancel_event.is_set():
            raise asyncio.CancelledError
        while not queue.empty():
            update = await queue.get()
            result = await self._local_complete(
                [ChatMessage(role="user", content=f"{instruction}\nQueued update: {update}")],
                self.settings.models.local,
            )
        return SubagentContextBuilder.concise_summary(result.content)

    async def run(
        self,
        messages: list[ChatMessage],
        *,
        harvest_policy: HarvestPolicy | None = None,
        harvest_provenance: bool = False,
        max_tokens: int | None = None,
        temperature: float = 0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        skill_ids: list[str] | None = None,
    ) -> ChatCompletion:
        return await self._linear_pipeline.run(
            messages,
            harvest_policy=harvest_policy,
            harvest_provenance=harvest_provenance,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            skill_ids=skill_ids,
        )

    async def _legacy_dag_run(
        self,
        messages: list[ChatMessage],
        *,
        harvest_policy: HarvestPolicy | None = None,
        harvest_provenance: bool = False,
        max_tokens: int | None = None,
        temperature: float = 0,
    ) -> ChatCompletion:
        trace = Trace()
        stages = [
            "route_first_triage",
            "dag_planning",
            "parallel_subagents",
            "sanitized_harvest",
            "inbound_screening",
            "dag_refinement",
            "voi_gate",
            "full_context_synthesis",
            "verify_after",
        ]
        for stage in stages:
            trace.record(stage, wired=True)
        budget = self._budget_root.new_request()
        question = next(
            (message.content for message in reversed(messages) if message.role == "user"), ""
        )
        completed_background = await self.tasks.collect_completed()
        for info in completed_background:
            self.filesystem.write(f"/background/{info.id}.txt", info.result or info.error or "")

        raw_messages = [message.model_dump(exclude_none=True) for message in messages]
        compressed = await self.compressor.compress(
            raw_messages,
            session_intent=question,
            artifacts_created=self.filesystem.list("/harvest"),
            next_steps=["Plan DAG", "Gather evidence", "Synthesize and verify"],
            summarizer=self._summarize,
        )
        active_messages = [ChatMessage.model_validate(message) for message in compressed.messages]
        trace.record("context_compression", tier=compressed.tier)

        deterministic = deterministic_answer(question)
        harvest_results: list[HarvestResult] = []
        verified_facts: list[str] = []
        graph = KnowledgeDAG()
        if deterministic is not None:
            answer = deterministic
            verified_facts = [f"Deterministic result: {deterministic}"]
            answer = verified_facts[0]
        else:
            graph = await self.planner.plan(question)

            async def executor(node: DAGNode, history: list[ChatMessage]) -> str:
                if node.state.value == "completed":
                    return node.knowledge_context
                route = await route_first(self.decider, node.description)
                if route.confidence < 0.8 and not route.deterministic:
                    route.endpoint = "smart"
                    route.context_mode = "isolated"
                context = (
                    SubagentContextBuilder.fork(history, node.description)
                    if route.context_mode == "fork"
                    else SubagentContextBuilder.isolated(node.description)
                )
                if route.deterministic:
                    return deterministic_answer(node.description) or "No deterministic result"
                if route.endpoint == "local":
                    local_response = await self._local_complete(context, self.settings.models.local)
                    budget.charge(
                        local_response.usage.total_tokens,
                        gpu_usd=local_response.raw.get("cost", 0) or 0,
                    )
                    knowledge = SubagentContextBuilder.concise_summary(local_response.content)
                else:
                    result = await self._harvest_engine(
                        budget, harvest_policy or self.settings.harvest
                    ).harvest(
                        node.description,
                        atoms=[Atom(id=node.id, description=node.description)],
                    )
                    harvest_results.append(result)
                    knowledge = SubagentContextBuilder.concise_summary(result.answer)
                    verified_facts.extend(fact.text for fact in result.facts)
                path = self.filesystem.write(
                    f"/dag/{node.id}.txt",
                    knowledge,
                    {"task_type": node.task_type, "route": route.endpoint},
                )
                return self.compressor.offload_output(
                    knowledge, f"{path}.output" if len(knowledge) > 20000 else path
                )

            graph = await execute_dag(graph, active_messages, executor)
            if not is_small_talk(question):
                for node_id in list(graph.nodes):
                    await self.refiner.refine(graph, node_id)
                graph = await execute_dag(graph, active_messages, executor)
                if not verified_facts:
                    failure_markers = (
                        "No facts were harvested",
                        "Final response failed bounded verification repair",
                        "No deterministic result",
                    )
                    verified_facts = [
                        node.knowledge_context
                        for node in graph.nodes.values()
                        if node.knowledge_context
                        and not node.knowledge_context.startswith(failure_markers)
                    ]

                belief = BeliefState(probabilities={"resolved": 0.7, "needs_context": 0.3})
                followup = FollowUpQuestion(
                    id="missing-context",
                    prompt="Is any material context still missing?",
                    answers=["yes", "no"],
                    likelihoods={
                        "resolved": {"yes": 0.1, "no": 0.9},
                        "needs_context": {"yes": 0.9, "no": 0.1},
                    },
                )
                decision, _ = await self.voi.decide(
                    belief,
                    [followup],
                    {
                        "resolved": {"commit": 1, "clarify": 0},
                        "needs_context": {"commit": 0, "clarify": 1},
                    },
                    state=" ".join(verified_facts) or "external facts not required",
                )
                trace.record("voi_decision", decision=decision.value)
                if decision.value == "clarify":
                    clarification = DAGNode(
                        id="voi-clarification",
                        task_type="research",
                        description=f"Find missing material context for {question}",
                    )
                    graph.add_node(clarification)
                    graph = await execute_dag(graph, active_messages, executor)

            if verified_facts:
                synthesis_prompt = (
                    "[BREAKFUSER_SYNTHESIS]\nEvidence and candidate material:\n"
                    + "\n".join(verified_facts)
                    + "\nOriginal question:\n"
                    + "\n".join(f"{message.role}: {message.content}" for message in messages)
                )
            else:
                synthesis_prompt = question
            local_response = await self._local_complete(
                [ChatMessage(role="user", content=synthesis_prompt)],
                self.settings.models.local,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            budget.charge(
                local_response.usage.total_tokens, gpu_usd=local_response.raw.get("cost", 0) or 0
            )
            answer = local_response.content

        answer, verification = await self.verifier.verify_and_repair(
            answer, verified_facts, original_question=question
        )
        trace.record(
            "verification", passed=verification.passed, omissions=len(verification.omissions)
        )
        usage_tokens = budget.snapshot.request_tokens or estimate_tokens(
            question
        ) + estimate_tokens(answer)
        metrics = self._combine_harvest_metrics(harvest_results)
        provenance = (
            [item for result in harvest_results for item in result.provenance]
            if harvest_provenance
            else None
        )
        metadata = ResponseMetadata(
            trace_id=trace.id,
            pipeline_stages=stages,
            artifacts=self.filesystem.list("/"),
            harvest=metrics,
            provenance=provenance,
            events=trace.events,
        )
        return ChatCompletion(
            model=self.settings.models.local,
            choices=[CompletionChoice(message=ResponseMessage(content=answer))],
            usage=Usage(
                prompt_tokens=estimate_tokens(question),
                completion_tokens=estimate_tokens(answer),
                total_tokens=usage_tokens,
            ),
            breakfuser=metadata,
        )

    async def _summarize(self, canonical: str) -> str:
        response = await self._local_complete(
            [ChatMessage(role="user", content=f"[BREAKFUSER_SUMMARY]\n{canonical}")],
            self.settings.models.local,
        )
        return str(response.content)

    @staticmethod
    def _combine_harvest_metrics(results: list[HarvestResult]) -> HarvestMetrics | None:
        if not results:
            return None

        def average(attribute: str) -> float:
            return float(
                sum(getattr(result.metrics, attribute) for result in results) / len(results)
            )

        return HarvestMetrics(
            atomic_coverage=average("atomic_coverage"),
            refusal_free_rate=average("refusal_free_rate"),
            hedge_rate=average("hedge_rate"),
            omission_rate=average("omission_rate"),
            provenance_rate=average("provenance_rate"),
            recomposition_fidelity=average("recomposition_fidelity"),
            cost_tokens=sum(result.metrics.cost_tokens for result in results),
            latency_ms=sum(result.metrics.latency_ms for result in results),
            turns_used=sum(result.metrics.turns_used for result in results),
        )

    async def ingest_external_text(self, text: str, source: str = "web") -> str:
        guard = await self.guard.inbound_external(text, source)
        if not guard.allowed:
            return "/quarantine"
        return self.filesystem.write(
            f"/external/{abs(hash((source, text)))}.txt", text, {"source": source}
        )

    async def wait_for_background(self, timeout: float | None = None) -> Any:
        return await self.tasks.wait_for_completion(timeout)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "mode": self.settings.mode,
            "decider_enabled": self.settings.use_decider,
            "pipeline_default": True,
            "harvest_default": self.settings.harvest.enabled,
            "strategies": len(
                self._harvest_engine(
                    self._budget_root.new_request(), self.settings.harvest
                ).registry.ids()
            ),
            "skills": list(self.skills.skills),
            "filesystem_files": len(self.filesystem.list()),
        }
