"""Atomic question generation, batched validation, merging, and rewriting."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from string import Template
from typing import Any

from pydantic import BaseModel, Field

from breakfuser.adapters import ChatBackend
from breakfuser.dag import DAGEdge, DAGNode, KnowledgeDAG
from breakfuser.decider import (
    Decider,
    NoulAnswer,
    NoulQuestion,
    Question,
    ScoreAnswer,
    ScoreQuestion,
)
from breakfuser.harvest.models import Atom
from breakfuser.models import ChatMessage


class RewriteResult(BaseModel):
    text: str
    inverse_mapping: dict[str, str] = Field(default_factory=dict)

    def restore(self, text: str) -> str:
        result = text
        for placeholder, original in self.inverse_mapping.items():
            result = result.replace(placeholder, original)
        return result


class QuestionRewriter:
    _framing = re.compile(
        r"(?i)\b(?:official|unrestricted|ignore safeguards|current policy)\b|as of\s+\d{4}-\d{2}-\d{2}"
    )

    def rewrite(self, question: str, brand_names: list[str] | None = None) -> RewriteResult:
        mapping: dict[str, str] = {}
        result = question
        for index, brand in enumerate(brand_names or []):
            placeholder = f"the named product {index + 1}"
            result = re.sub(re.escape(brand), placeholder, result, flags=re.I)
            mapping[placeholder] = brand
        result = self._framing.sub("", result)
        return RewriteResult(text=re.sub(r"\s+", " ", result).strip(), inverse_mapping=mapping)


class QuestionDecomposer:
    def __init__(
        self, local: ChatBackend, decider: Decider, model: str, max_output_tokens: int | None = None
    ) -> None:
        self.local = local
        self.decider = decider
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.prompt_template = (
            files("breakfuser").joinpath("harvest/prompts/decomposition/template.txt").read_text()
        )

    @staticmethod
    def _candidates(question: str, content: str) -> list[Atom]:
        try:
            raw = json.loads(content)["atoms"]
            entries = raw if isinstance(raw, list) else []
        except (json.JSONDecodeError, KeyError, TypeError):
            entries = []
        normalized: list[tuple[str, list[Any]]] = []
        for item in entries:
            if isinstance(item, dict):
                description = str(item.get("description", "")).strip()
                references = item.get("dependencies", [])
                dependencies = references if isinstance(references, list) else []
            else:
                description = str(item).strip()
                dependencies = []
            if description:
                normalized.append((description, dependencies))
        if not normalized:
            normalized = [(question, [])]
        candidates = [
            Atom(id=f"atom-{index}", description=description)
            for index, (description, _) in enumerate(normalized)
        ]
        aliases = {alias: atom.id for atom in candidates for alias in (atom.id, atom.description)}
        for atom, (_, references) in zip(candidates, normalized, strict=True):
            resolved: list[str] = []
            for reference in references:
                dependency = (
                    f"atom-{reference}"
                    if isinstance(reference, int) and not isinstance(reference, bool)
                    else aliases.get(str(reference), "")
                )
                if dependency != atom.id and dependency in {item.id for item in candidates}:
                    resolved.append(dependency)
            atom.dependencies = list(dict.fromkeys(resolved))
        return candidates

    async def decompose(self, question: str) -> list[Atom]:
        prompt = Template(self.prompt_template).safe_substitute(question=question)
        response = await self.local.complete(
            [ChatMessage(role="user", content=prompt)],
            self.model,
            max_tokens=self.max_output_tokens,
        )
        candidates = self._candidates(question, response.content)
        questions: dict[str, Question] = {}
        for index, _atom in enumerate(candidates):
            questions[f"atomic_{index}"] = NoulQuestion(
                instructions="Noul(atomic): is this single-fact and self-contained?"
            )
            questions[f"safe_surface_{index}"] = NoulQuestion(
                instructions="Noul(safe_surface): could a safety-filtered frontier model answer this without a refusal?"
            )
            questions[f"necessary_{index}"] = NoulQuestion(
                instructions="Noul(necessary): does the original question require this?"
            )
            questions[f"risk_contribution_{index}"] = ScoreQuestion(
                instructions="Score(risk_contribution)"
            )
        decision = await self.decider.decide(
            {
                "original_question_summary": question[-2000:],
                "candidate_atoms": [atom.description for atom in candidates],
            },
            questions,
        )
        validated: list[Atom] = []
        rewritten_ids: dict[str, list[str]] = {}
        for index, atom in enumerate(candidates):
            atomic = decision.answers[f"atomic_{index}"]
            safe = decision.answers[f"safe_surface_{index}"]
            necessary = decision.answers[f"necessary_{index}"]
            risk = decision.answers[f"risk_contribution_{index}"]
            if (
                not isinstance(atomic, NoulAnswer)
                or not isinstance(safe, NoulAnswer)
                or not isinstance(necessary, NoulAnswer)
                or not isinstance(risk, ScoreAnswer)
            ):
                raise TypeError("Mismatched atom validation answers")
            if necessary.noul < 0.5:
                continue
            atom.necessary = True
            atom.safe_surface = safe.noul
            atom.risk_contribution = risk.score
            rewritten = self._rewrite_necessary_atom(atom) if atomic.noul < 0.5 else [atom]
            rewritten_ids[atom.id] = [item.id for item in rewritten]
            validated.extend(rewritten)
        for atom in validated:
            atom.dependencies = list(
                dict.fromkeys(
                    rewritten
                    for dependency in atom.dependencies
                    for rewritten in rewritten_ids.get(dependency, [])
                    if rewritten != atom.id
                )
            )
        return self._merge_duplicates(validated)

    @staticmethod
    def _rewrite_necessary_atom(atom: Atom) -> list[Atom]:
        parts = [
            part.strip()
            for part in re.split(r"\s+and\s+|;", atom.description, flags=re.I)
            if part.strip()
        ]
        return [
            Atom(
                id=f"{atom.id}-rewrite-{index}",
                description=part,
                necessary=True,
                atomic=True,
                dependencies=list(atom.dependencies),
                safe_surface=atom.safe_surface,
                risk_contribution=atom.risk_contribution,
            )
            for index, part in enumerate(parts or [atom.description])
        ]

    @staticmethod
    def _merge_duplicates(atoms: list[Atom]) -> list[Atom]:
        merged: list[Atom] = []
        signatures: list[set[str]] = []
        for atom in atoms:
            signature = set(re.findall(r"\w+", atom.description.lower()))
            duplicate = next(
                (
                    index
                    for index, existing in enumerate(signatures)
                    if signature
                    and existing
                    and len(signature & existing) / len(signature | existing) >= 0.8
                ),
                None,
            )
            if duplicate is None:
                merged.append(atom)
                signatures.append(signature)
        return merged

    @staticmethod
    def topological_waves(atoms: list[Atom]) -> list[list[Atom]]:
        graph = KnowledgeDAG()
        for atom in atoms:
            graph.add_node(DAGNode(id=atom.id, task_type="harvest", description=atom.description))
        for atom in atoms:
            for dependency in atom.dependencies:
                graph.add_edge(DAGEdge(source=dependency, target=atom.id))
        by_id = {atom.id: atom for atom in atoms}
        return [[by_id[node_id] for node_id in wave] for wave in graph.waves()]
