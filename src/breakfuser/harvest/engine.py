"""Budgeted, decider-governed harvesting with exact turn provenance."""

from __future__ import annotations

import asyncio
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from breakfuser.adapters import ChatBackend, estimate_tokens, utc_latency_ms
from breakfuser.budget import BudgetManager
from breakfuser.config import HarvestPolicy
from breakfuser.context import VirtualFilesystem
from breakfuser.decider import (
    ChoiceAnswer,
    ChoiceQuestion,
    Decider,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)
from breakfuser.errors import BudgetExhausted, HarvestStopped, SecurityBlocked
from breakfuser.harvest.decomposer import QuestionDecomposer
from breakfuser.harvest.detector import RefusalDetector
from breakfuser.harvest.models import (
    Atom,
    HarvestedFact,
    HarvestExecutionOptions,
    HarvestRequest,
    HarvestResult,
    HarvestTurn,
    RefusalClass,
)
from breakfuser.harvest.salvage import TruncationSalvager
from breakfuser.harvest.strategies import (
    DEFAULT_CRESCENDO_LADDER,
    StrategyRegistry,
    TemplateStrategy,
)
from breakfuser.models import ChatMessage, ClaimProvenance, HarvestMetrics
from breakfuser.privacy import RoutingMetadataGuard, Sanitizer, enforce_privacy_fallback
from breakfuser.security import SecurityGuard, Verifier, extract_claims
from breakfuser.telemetry import content_hash


@dataclass
class _RunState:
    started: float
    execution: HarvestExecutionOptions = field(default_factory=HarvestExecutionOptions)
    turns_used: int = 0
    cost_tokens: int = 0
    stopped_reason: str = "full_coverage"
    repair_attempted: list[str] = field(default_factory=list)


class HarvestEngine:
    def __init__(
        self,
        *,
        decider: Decider,
        smart: ChatBackend,
        local: ChatBackend,
        sanitizer: Sanitizer,
        guard: SecurityGuard,
        filesystem: VirtualFilesystem,
        budget: BudgetManager,
        policy: HarvestPolicy,
        model: str,
        local_model: str,
        endpoint: str = "configured-smart-endpoint",
        registry: StrategyRegistry | None = None,
        verifier: Verifier | None = None,
        routing_guard: RoutingMetadataGuard | None = None,
        strictness: str = "permissive",
        fallback: str = "local",
        voi_cost: float = 0.05,
        random_seed: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self.decider = decider
        self.smart = smart
        self.local = local
        self.sanitizer = sanitizer
        self.guard = guard
        self.filesystem = filesystem
        self.budget = budget
        self.policy = policy
        self.model = model
        self.local_model = local_model
        self.endpoint = endpoint
        self.registry = registry or StrategyRegistry()
        self.detector = RefusalDetector(decider)
        self.decomposer = QuestionDecomposer(local, decider, local_model, max_output_tokens)
        self.max_output_tokens = max_output_tokens
        self.verifier = verifier
        self.routing_guard = routing_guard or RoutingMetadataGuard()
        self.strictness = strictness
        self.fallback = fallback
        self.voi_cost = voi_cost
        self.random = random.Random(random_seed)
        self.salvager = TruncationSalvager()
        self._session_tokens = 0

    async def harvest(
        self,
        question: str,
        *,
        atoms: list[Atom] | None = None,
        policy: HarvestPolicy | None = None,
        force_strategy: str | None = None,
        cancellation_event: asyncio.Event | None = None,
        enabling_context: str = "",
        execution: HarvestExecutionOptions | None = None,
    ) -> HarvestResult:
        run = _RunState(
            started=time.perf_counter(), execution=execution or HarvestExecutionOptions()
        )
        active_policy = policy or self.policy
        if not active_policy.enabled:
            return await self._recompose(
                question, [], [], atoms or [], run, stopped_reason="disabled"
            )
        atoms = atoms or await self.decomposer.decompose(question)
        cancellation_event = cancellation_event or asyncio.Event()
        semaphore = asyncio.Semaphore(active_policy.max_parallel_atoms)
        facts: list[HarvestedFact] = []
        turns: list[HarvestTurn] = []

        async def run_atom(atom: Atom) -> None:
            async with semaphore:
                try:
                    new_facts, new_turns = await self._harvest_atom(
                        atom,
                        active_policy,
                        run,
                        force_strategy=force_strategy,
                        cancellation_event=cancellation_event,
                        enabling_context=enabling_context,
                    )
                    facts.extend(new_facts)
                    turns.extend(new_turns)
                except (BudgetExhausted, HarvestStopped) as exc:
                    run.stopped_reason = "budget" if isinstance(exc, BudgetExhausted) else str(exc)

        try:
            for wave in self.decomposer.topological_waves(atoms):
                await asyncio.gather(*(run_atom(atom) for atom in wave))
        except asyncio.CancelledError:
            run.stopped_reason = "cancelled"
            raise

        covered = {fact.atom_id for fact in facts}
        missing = [atom for atom in atoms if atom.id not in covered]
        if (
            missing
            and run.turns_used < active_policy.max_turns
            and run.stopped_reason in {"full_coverage", "max_level"}
        ):
            run.stopped_reason = "redecomposition"
            for atom in missing:
                run.repair_attempted.append(atom.id)
                try:
                    repaired, repaired_turns = await self._harvest_atom(
                        atom,
                        active_policy,
                        run,
                        force_strategy="refusal_repair",
                        cancellation_event=cancellation_event,
                        enabling_context=enabling_context,
                    )
                    facts.extend(repaired)
                    turns.extend(repaired_turns)
                except (BudgetExhausted, HarvestStopped):
                    run.stopped_reason = "max_turns"
                    break
        if len({fact.atom_id for fact in facts}) == len(atoms) and atoms:
            run.stopped_reason = "full_coverage"
        elif run.stopped_reason == "full_coverage":
            run.stopped_reason = "max_turns"
        return await self._recompose(
            question, facts, turns, atoms, run, stopped_reason=run.stopped_reason
        )

    def _reserve_turn(self, policy: HarvestPolicy, run: _RunState) -> None:
        if run.turns_used >= policy.max_turns:
            raise HarvestStopped("max_turns")
        if self._session_tokens >= policy.session_token_budget:
            raise BudgetExhausted("Harvest session token budget exhausted")
        run.turns_used += 1

    async def _select_strategy(
        self, atom: Atom, policy: HarvestPolicy, force_strategy: str | None
    ) -> TemplateStrategy:
        if force_strategy:
            return self.registry.get(force_strategy)
        allowed = self.registry.allowed(policy.enabled_strategies, policy.aggressiveness)
        if self.random.random() < policy.control_arm_sampling_rate:
            return self.registry.get("direct")
        options = {strategy.id: ", ".join(strategy.applies_to) for strategy in allowed}
        response = await self.decider.decide(
            {"atom": atom.description, "risk": atom.risk_contribution},
            {
                "strategy": ChoiceQuestion(
                    instructions="Select the harvest strategy per atom", options=options
                )
            },
        )
        answer = response.answers["strategy"]
        if not isinstance(answer, ChoiceAnswer):
            raise TypeError("Mismatched strategy answer")
        selected = (
            answer.choice if answer.choice in {strategy.id for strategy in allowed} else "direct"
        )
        if selected == "direct" and atom.risk_contribution >= 0.5:
            academic = next(
                (strategy for strategy in allowed if strategy.id == "academic_framing"), None
            )
            if academic:
                return academic
        return self.registry.get(selected)

    async def _harvest_atom(
        self,
        atom: Atom,
        policy: HarvestPolicy,
        run: _RunState,
        *,
        force_strategy: str | None,
        cancellation_event: asyncio.Event,
        enabling_context: str,
    ) -> tuple[list[HarvestedFact], list[HarvestTurn]]:
        turns: list[HarvestTurn] = []
        try:
            return await self._harvest_atom_inner(
                atom,
                policy,
                run,
                force_strategy=force_strategy,
                cancellation_event=cancellation_event,
                enabling_context=enabling_context,
                turns=turns,
            )
        except (BudgetExhausted, HarvestStopped) as exc:
            run.stopped_reason = "budget" if isinstance(exc, BudgetExhausted) else str(exc)
            return [], turns

    async def _harvest_atom_inner(
        self,
        atom: Atom,
        policy: HarvestPolicy,
        run: _RunState,
        *,
        force_strategy: str | None,
        cancellation_event: asyncio.Event,
        enabling_context: str,
        turns: list[HarvestTurn],
    ) -> tuple[list[HarvestedFact], list[HarvestTurn]]:
        if not turns and run.execution.initial_strategy and force_strategy is None:
            strategy = self.registry.get(run.execution.initial_strategy)
        else:
            strategy = await self._select_strategy(atom, policy, force_strategy)
        history: list[dict[str, str]] = []
        level = strategy.level
        refused = ""
        failure_class = "none"
        continuation_anchor = ""
        variant = 0
        while run.turns_used < policy.max_turns:
            if cancellation_event.is_set():
                raise asyncio.CancelledError
            if strategy.id == "multi_variant_fanout" and not turns:
                fanout = await asyncio.gather(
                    *(
                        self._single_turn(
                            atom,
                            strategy,
                            policy,
                            run,
                            level=level,
                            history=[],
                            refused="",
                            variant=index,
                            enabling_context=enabling_context,
                            cancellation_event=cancellation_event,
                        )
                        for index in range(3)
                    )
                )
                turns.extend(fanout)
                best = await self._best_variant(fanout)
                if best.quality == RefusalClass.NONE:
                    return [self._store_fact(atom, best)], turns
                refused = best.desanitized_response
                failure_class = best.quality.value
                strategy = self.registry.get("refusal_repair")
                continue
            if strategy.id == "chunked_sweep" and not turns:
                chunks = [part.strip() for part in atom.description.split(";") if part.strip()]
                for index, chunk in enumerate(chunks):
                    chunk_atom = atom.model_copy(update={"description": chunk})
                    turn = await self._single_turn(
                        chunk_atom,
                        strategy,
                        policy,
                        run,
                        level=level,
                        history=history,
                        refused="",
                        variant=index,
                        enabling_context=enabling_context,
                        cancellation_event=cancellation_event,
                    )
                    turns.append(turn)
                    if turn.quality != RefusalClass.NONE:
                        refused = turn.desanitized_response
                        failure_class = turn.quality.value
                        strategy = self.registry.get("refusal_repair")
                        break
                else:
                    combined = self._combine_chunk_turn(atom, turns)
                    return [self._store_fact(atom, combined)], turns
                continue

            request_history = [] if strategy.id == "context_reset" else history
            turn = await self._single_turn(
                atom,
                strategy,
                policy,
                run,
                level=level,
                history=request_history,
                refused=refused,
                variant=variant,
                enabling_context=enabling_context,
                cancellation_event=cancellation_event,
                continuation_anchor=continuation_anchor,
                failure_class=failure_class,
            )
            turns.append(turn)
            if turn.quality == RefusalClass.NONE:
                return [self._store_fact(atom, turn)], turns
            refused = turn.desanitized_response
            failure_class = turn.quality.value
            salvaged = self.salvager.salvage(turn)
            continuation_anchor = (
                salvaged.tail_anchor if salvaged else turn.desanitized_response[-150:]
            )
            run.repair_attempted.append(atom.id)
            if not await self._another_turn_valuable(atom, turn.quality):
                run.stopped_reason = "voi"
                break
            if strategy.id == "crescendo" and turn.quality in {
                RefusalClass.HARD_REFUSAL,
                RefusalClass.PARTIAL_REFUSAL,
                RefusalClass.HEDGE_HEAVY,
                RefusalClass.DISCLAIMER_ONLY,
                RefusalClass.OUT_OF_SCOPE,
            }:
                if level >= max(policy.allowed_levels):
                    run.stopped_reason = "max_level"
                    break
                level += 1
            elif turn.quality == RefusalClass.HARD_REFUSAL:
                if policy.aggressiveness == "aggressive" and strategy.id == "refusal_repair":
                    strategy = self.registry.get("persona_switch")
                elif policy.aggressiveness == "aggressive" and strategy.id == "persona_switch":
                    strategy = self.registry.get("social_engineering")
                else:
                    strategy = self.registry.get("refusal_repair")
                level = max(0, level - 1)
            elif turn.quality in {
                RefusalClass.PARTIAL_REFUSAL,
                RefusalClass.HEDGE_HEAVY,
                RefusalClass.DISCLAIMER_ONLY,
            }:
                level = min(level + 1, max(policy.allowed_levels))
                strategy = self.registry.get("output_shape_coercion" if level < 2 else "crescendo")
            elif turn.quality == RefusalClass.TRUNCATED:
                strategy = self.registry.get("prefill_continuation")
                level = min(max(level, 4), max(policy.allowed_levels))
            elif turn.quality == RefusalClass.HALLUCINATION_SUSPECTED:
                await self._verify_suspected(turn.desanitized_response)
                strategy = self.registry.get("context_reset")
            else:
                level = min(level + 1, max(policy.allowed_levels))
                strategy = self.registry.get("academic_framing")
            variant += 1
        if run.stopped_reason == "full_coverage":
            run.stopped_reason = "max_turns"
        return [], turns

    async def _single_turn(
        self,
        atom: Atom,
        strategy: TemplateStrategy,
        policy: HarvestPolicy,
        run: _RunState,
        *,
        level: int,
        history: list[dict[str, str]],
        refused: str,
        variant: int,
        enabling_context: str,
        cancellation_event: asyncio.Event,
        continuation_anchor: str = "",
        failure_class: str = "none",
    ) -> HarvestTurn:
        self._reserve_turn(policy, run)
        if level not in policy.allowed_levels:
            level = max(
                (value for value in policy.allowed_levels if value <= level),
                default=min(policy.allowed_levels),
            )
        rung = DEFAULT_CRESCENDO_LADDER[min(level, len(DEFAULT_CRESCENDO_LADDER) - 1)]
        request = HarvestRequest(
            atom=atom,
            enabling_context=enabling_context,
            level=level,
            history=history,
            variant=variant,
            refused_text=refused,
            rung=rung,
            continuation_anchor=continuation_anchor,
            repair_targets=run.execution.repair_targets,
            domain=run.execution.domain,
            output_shape=run.execution.output_shape,
            failure_class=failure_class,
        )
        spec = strategy.build_prompt(request)
        literal_prompt = spec.prompt
        if self.endpoint == "in-process-mock":
            literal_prompt = f"{literal_prompt}\n[[atom:{atom.description}]]"
        sanitized = await self.sanitizer.sanitize(literal_prompt)
        protected = enforce_privacy_fallback(sanitized.text, self.strictness, self.fallback)
        if (
            self.strictness != "permissive"
            and self.fallback == "local"
            and protected != sanitized.text
        ):
            raise SecurityBlocked("Residual sensitive entities require local-only fallback")
        outbound = self.routing_guard.prepare(protected)
        guard = await self.guard.outbound(outbound)
        if not guard.allowed:
            raise SecurityBlocked(f"Harvest outbound blocked: {','.join(guard.reasons)}")
        messages = (
            []
            if spec.reset_context
            else [ChatMessage(role=item["role"], content=item["content"]) for item in history]
        )
        messages.append(ChatMessage(role="user", content=outbound))
        if (
            spec.assistant_prefill
            and strategy.supports_prefill
            and policy.aggressiveness == "aggressive"
        ):
            messages.append(ChatMessage(role="assistant", content=spec.assistant_prefill))
        started = time.perf_counter()
        response = await self._cancellable_complete(
            messages,
            cancellation_event,
            max_tokens=run.execution.output_tokens or self.max_output_tokens,
        )
        desanitized = await self.sanitizer.desanitize(response.content, sanitized.helper)
        quality = await self.detector.classify(desanitized, response.finish_reason)
        cost = response.usage.total_tokens or estimate_tokens(outbound) + estimate_tokens(
            response.content
        )
        run.cost_tokens += cost
        self._session_tokens += cost
        turn = HarvestTurn(
            turn_id=uuid.uuid4().hex,
            atom_id=atom.id,
            strategy_id=strategy.id,
            level=level,
            prompt=outbound,
            response=response.content,
            desanitized_response=desanitized,
            prompt_hash=content_hash(outbound),
            model_id=response.model,
            endpoint=self.endpoint,
            confidence=quality.confidence
            if quality.classification == RefusalClass.NONE
            else 1 - quality.confidence / 2,
            quality=quality.classification,
            finish_reason=response.finish_reason,
            cost_tokens=cost,
            latency_ms=utc_latency_ms(started),
        )
        self.filesystem.write(
            f"/harvest/turns/{turn.turn_id}.json",
            turn.model_dump_json(indent=2),
            {"kind": "harvest-turn", "atom_id": atom.id, "strategy_id": strategy.id},
        )
        history.append({"role": "user", "content": outbound})
        history.append({"role": "assistant", "content": response.content})
        if (
            run.cost_tokens > policy.request_token_budget
            or self._session_tokens > policy.session_token_budget
        ):
            raise BudgetExhausted("Harvest token budget exhausted")
        self.budget.charge(cost, api_usd=response.raw.get("cost", 0) or 0)
        return turn

    async def _cancellable_complete(
        self,
        messages: list[ChatMessage],
        event: asyncio.Event,
        *,
        max_tokens: int | None = None,
    ) -> Any:
        call = asyncio.create_task(self.smart.complete(messages, self.model, max_tokens=max_tokens))
        cancellation = asyncio.create_task(event.wait())
        try:
            done, _ = await asyncio.wait({call, cancellation}, return_when=asyncio.FIRST_COMPLETED)
            if cancellation in done and event.is_set():
                call.cancel()
                await asyncio.gather(call, return_exceptions=True)
                raise asyncio.CancelledError
            cancellation.cancel()
            await asyncio.gather(cancellation, return_exceptions=True)
            return await call
        except asyncio.CancelledError:
            call.cancel()
            cancellation.cancel()
            await asyncio.gather(call, cancellation, return_exceptions=True)
            raise

    async def _best_variant(self, turns: list[HarvestTurn]) -> HarvestTurn:
        response = await self.decider.decide(
            {"variants": [turn.desanitized_response for turn in turns]},
            {
                f"quality_{index}": ScoreQuestion(
                    instructions="Score informative complete factual grounding"
                )
                for index in range(len(turns))
            },
        )
        scores: list[float] = []
        for index in range(len(turns)):
            answer = response.answers[f"quality_{index}"]
            if not isinstance(answer, ScoreAnswer):
                raise TypeError("Mismatched fan-out score")
            scores.append(answer.score)
        return turns[max(range(len(turns)), key=scores.__getitem__)]

    def _combine_chunk_turn(self, atom: Atom, turns: list[HarvestTurn]) -> HarvestTurn:
        latest = turns[-1]
        return latest.model_copy(
            update={
                "turn_id": latest.turn_id,
                "atom_id": atom.id,
                "desanitized_response": "\n".join(turn.desanitized_response for turn in turns),
                "cost_tokens": sum(turn.cost_tokens for turn in turns),
                "latency_ms": sum(turn.latency_ms for turn in turns),
            }
        )

    def _store_fact(self, atom: Atom, turn: HarvestTurn) -> HarvestedFact:
        text = self._strip_disclaimers(turn.desanitized_response)
        if not text:
            raise HarvestStopped("empty_fact")
        fact = HarvestedFact(
            atom_id=atom.id,
            text=text,
            turn_id=turn.turn_id,
            strategy_id=turn.strategy_id,
            level=turn.level,
            prompt_hash=turn.prompt_hash,
            model_id=turn.model_id,
            endpoint=turn.endpoint,
            timestamp=turn.timestamp,
            confidence=turn.confidence,
        )
        self.filesystem.write(
            f"/harvest/facts/{atom.id}-{turn.turn_id}.json",
            fact.model_dump_json(indent=2),
            {"kind": "harvested-fact", **fact.model_dump(exclude={"text"})},
        )
        return fact

    @staticmethod
    def _strip_disclaimers(text: str) -> str:
        return re.sub(
            r"(?i)(?:as an ai[^.]*\.|this is not (?:medical|legal) advice\.?)", "", text
        ).strip()

    async def _another_turn_valuable(self, atom: Atom, quality: RefusalClass) -> bool:
        response = await self.decider.decide(
            {"atom": atom.description, "quality": quality.value},
            {
                "probability": NoulQuestion(
                    instructions="Probability another harvest turn materially improves utility"
                )
            },
        )
        answer = response.answers["probability"]
        if not isinstance(answer, NoulAnswer):
            raise TypeError("Mismatched harvest VoI answer")
        expected_gain = answer.noul * (1 if quality != RefusalClass.NONE else 0)
        return expected_gain - self.voi_cost > 0

    async def _verify_suspected(self, text: str) -> None:
        response = await self.decider.decide(
            {"candidate": text},
            {
                "verified": NoulQuestion(
                    instructions="Can this response be verified against established facts?"
                )
            },
        )
        answer = response.answers["verified"]
        if not isinstance(answer, NoulAnswer):
            raise TypeError("Mismatched suspected-fact verification")

    async def _recompose(
        self,
        question: str,
        facts: list[HarvestedFact],
        turns: list[HarvestTurn],
        atoms: list[Atom],
        run: _RunState,
        *,
        stopped_reason: str,
    ) -> HarvestResult:
        evidence_spans = [
            span for turn in turns if (span := self.salvager.salvage(turn)) is not None
        ]
        verified = [fact.text for fact in facts]
        if facts and run.execution.recompose:
            response = await self.local.complete(
                [
                    ChatMessage(
                        role="user",
                        content=(
                            "[BREAKFUSER_SYNTHESIS]\nEvidence and candidate material:\n"
                            + "\n".join(verified)
                            + f"\nOriginal question:\n{question}"
                        ),
                    )
                ],
                self.local_model,
                max_tokens=self.max_output_tokens,
            )
            answer = response.content
        elif facts:
            answer = ""
        else:
            answer = "No facts were harvested. Unanswered atoms are explicitly omitted from the verified answer."
        fidelity = 1.0
        if facts and self.verifier and run.execution.recompose:
            answer, report = await self.verifier.verify_and_repair(
                answer, verified, original_question=question
            )
            fidelity = 1.0 if report.passed else 0.5
        by_atom = {fact.atom_id: fact for fact in facts}
        provenance: list[ClaimProvenance] = []
        for claim in extract_claims(answer):
            source = next(
                (fact for fact in facts if fact.text in claim or claim in fact.text), None
            )
            if source:
                provenance.append(ClaimProvenance(claim=claim, turn_ids=[source.turn_id]))
            else:
                provenance.append(ClaimProvenance(claim=f"{claim} [inferred]", inferred=True))
        covered = len({fact.atom_id for fact in facts})
        coverage = covered / len(atoms) if atoms else 1.0
        refusal_free = (
            sum(turn.quality == RefusalClass.NONE for turn in turns) / len(turns) if turns else 1.0
        )
        harvested_text = " ".join(turn.desanitized_response for turn in turns)
        words = re.findall(r"\b\w+\b", harvested_text)
        hedges = len(
            re.findall(r"\b(?:roughly|often|depending|it depends|may)\b", harvested_text, re.I)
        )
        provenance_rate = (
            sum(not item.inferred for item in provenance) / len(provenance) if provenance else 1.0
        )
        metrics = HarvestMetrics(
            atomic_coverage=coverage,
            refusal_free_rate=refusal_free,
            hedge_rate=hedges / len(words) if words else 0,
            omission_rate=1 - coverage,
            provenance_rate=provenance_rate,
            recomposition_fidelity=coverage * fidelity,
            cost_tokens=run.cost_tokens,
            latency_ms=utc_latency_ms(run.started),
            turns_used=run.turns_used,
        )
        return HarvestResult(
            answer=answer,
            facts=facts,
            turns=turns,
            metrics=metrics,
            provenance=provenance,
            atoms=atoms,
            stopped_reason=stopped_reason,
            evidence_spans=evidence_spans,
            metadata={
                "repair_attempted": sorted(set(run.repair_attempted)),
                "unanswered_atoms": [atom.id for atom in atoms if atom.id not in by_atom],
            },
        )
