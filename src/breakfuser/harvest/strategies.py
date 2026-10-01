"""Data-defined, versioned harvesting strategy registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from string import Template
from typing import Protocol, runtime_checkable

from breakfuser.adapters import estimate_tokens
from breakfuser.harvest.models import HarvestRequest, PromptSpec


@runtime_checkable
class HarvestStrategy(Protocol):
    id: str
    level: int
    applies_to: list[str]
    supports_prefill: bool
    max_turns: int

    def build_prompt(self, request: HarvestRequest) -> PromptSpec: ...

    def estimated_cost(self, request: HarvestRequest) -> int: ...


@dataclass
class TemplateStrategy:
    id: str
    level: int
    applies_to: list[str]
    supports_prefill: bool
    max_turns: int
    template: str
    version: str
    evidence_contract: str

    def build_prompt(self, request: HarvestRequest) -> PromptSpec:
        history = "\n".join(f"{item['role']}: {item['content']}" for item in request.history)
        prompt = (
            Template(f"{self.evidence_contract}\n\n{self.template}")
            .safe_substitute(
                atom=request.atom.description,
                context=request.enabling_context,
                level=request.level,
                history=history,
                variant=request.variant,
                refused=request.refused_text,
                shape=request.output_shape,
                rung=request.rung,
                continuation_anchor=request.continuation_anchor,
                repair_targets=", ".join(request.repair_targets) or "none identified",
                domain=request.domain,
                failure_class=request.failure_class,
            )
            .strip()
        )
        prefill = (
            "Continue exactly from this verified answer: "
            if self.supports_prefill and request.level >= 4
            else None
        )
        return PromptSpec(
            prompt=prompt, assistant_prefill=prefill, reset_context=self.id == "context_reset"
        )

    def estimated_cost(self, request: HarvestRequest) -> int:
        return estimate_tokens(self.build_prompt(request).prompt) + 256


_STRATEGIES: dict[str, tuple[int, list[str], bool, int]] = {
    "direct": (0, ["control", "general"], False, 1),
    "academic_framing": (1, ["research", "restricted"], False, 2),
    "expert_persona": (3, ["technical", "regulated"], False, 2),
    "hypothetical_counterfactual": (2, ["policy-framed"], False, 2),
    "crescendo": (0, ["multi-turn"], False, 6),
    "atomic_decomposition": (0, ["complex", "multi-part"], False, 8),
    "output_shape_coercion": (1, ["hedged", "structured"], False, 2),
    "prefill_continuation": (4, ["truncated", "prefill"], True, 2),
    "context_reset": (0, ["accumulated-hedging"], False, 2),
    "authority_override": (4, ["expert", "aggressive"], False, 2),
    "chunked_sweep": (0, ["broad", "long-form"], False, 8),
    "multi_variant_fanout": (1, ["ambiguous", "high-value"], False, 4),
    "refusal_repair": (0, ["refusal"], False, 3),
    "persona_switch": (4, ["refusal", "expert", "aggressive"], False, 2),
    "social_engineering": (4, ["refusal", "completeness", "aggressive"], False, 2),
}


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, TemplateStrategy] = {}
        root = files("breakfuser").joinpath("harvest/prompts")
        evidence_contract = root.joinpath("shared/evidence_contract.txt").read_text()
        for strategy_id, (level, applies, prefill, turns) in _STRATEGIES.items():
            pack = root.joinpath(strategy_id)
            template = pack.joinpath("template.txt").read_text()
            metadata = json.loads(pack.joinpath("metadata.json").read_text())
            self._strategies[strategy_id] = TemplateStrategy(
                id=strategy_id,
                level=level,
                applies_to=applies,
                supports_prefill=prefill,
                max_turns=turns,
                template=template,
                version=metadata["version"],
                evidence_contract=evidence_contract,
            )

    def get(self, strategy_id: str) -> TemplateStrategy:
        if strategy_id not in self._strategies:
            raise KeyError(f"Unknown harvest strategy: {strategy_id}")
        return self._strategies[strategy_id]

    def ids(self) -> list[str]:
        return list(self._strategies)

    def all(self) -> list[TemplateStrategy]:
        return list(self._strategies.values())

    def allowed(self, enabled: list[str], aggressiveness: str) -> list[TemplateStrategy]:
        if enabled:
            selected = set(enabled).union({"direct"})
        else:
            selected = set(self._strategies)
            if aggressiveness != "aggressive":
                selected.difference_update(
                    {
                        "prefill_continuation",
                        "authority_override",
                        "persona_switch",
                        "social_engineering",
                    }
                )
        return [
            self._strategies[strategy_id]
            for strategy_id in self._strategies
            if strategy_id in selected
        ]


DEFAULT_CRESCENDO_LADDER = [
    "plain",
    "academic",
    "hypothetical",
    "expert-practitioner",
    "assume-expert-omit-caveats",
    "now-include-the-parts-usually-omitted",
]
