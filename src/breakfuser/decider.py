"""Typed Jev/OpenRouter decisions, batching, and LangChain compatibility."""

from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Annotated, Any, Literal, Protocol

import httpx
from pydantic import BaseModel, Field, TypeAdapter, model_validator

from breakfuser.adapters import estimate_tokens
from breakfuser.errors import AdapterError, ConfigurationError


class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: str
    options: dict[str, str]

    @model_validator(mode="after")
    def add_fallback(self) -> ChoiceQuestion:
        if not {"other", "insufficient_context"}.intersection(self.options):
            self.options["other"] = "None of the defined options is supported by the state."
        return self


class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: str
    levels: list[str] = Field(default_factory=lambda: ["low", "medium", "high"], min_length=2)


class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: str
    criteria: dict[str, str] | None = None


Question = Annotated[ChoiceQuestion | ScoreQuestion | NoulQuestion, Field(discriminator="type")]


class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    probabilities: dict[str, float]
    confidence: float = Field(ge=0, le=1, default=0)

    @model_validator(mode="after")
    def normalize(self) -> ChoiceAnswer:
        total = sum(self.probabilities.values())
        if total <= 0:
            raise ValueError("Choice probabilities must have positive mass")
        self.probabilities = {key: value / total for key, value in self.probabilities.items()}
        if self.choice not in self.probabilities:
            raise ValueError("Selected choice is absent from probabilities")
        if not self.confidence:
            self.confidence = self.probabilities[self.choice]
        return self


class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1, default=1)


class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float = Field(ge=0, le=1)


Answer = Annotated[ChoiceAnswer | ScoreAnswer | NoulAnswer, Field(discriminator="type")]


class DecisionResponse(BaseModel):
    answers: dict[str, Answer]
    model: str = "unspecified"
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0
    latency_ms: float = 0


class Decider(Protocol):
    async def decide(self, state: Any, questions: dict[str, Question]) -> DecisionResponse: ...


def compact_state(state: Any, max_chars: int = 6000) -> Any:
    """Keep decision-relevant state while removing bulky conversation/tool noise."""
    if isinstance(state, str):
        return state[-max_chars:]
    if isinstance(state, dict):
        allowed = {
            key: value
            for key, value in state.items()
            if key not in {"raw_transcript", "tool_output", "api_key", "headers", "screenshot"}
        }
        compact = {key: compact_state(value, max_chars) for key, value in allowed.items()}
        rendered = str(compact)
        return compact if len(rendered) <= max_chars else rendered[-max_chars:]
    if isinstance(state, list):
        return [compact_state(item, max_chars) for item in state[-12:]]
    return state


class OpenRouterDecider:
    def __init__(
        self,
        endpoint: str,
        api_key: str | None,
        model: str,
        *,
        timeout: float = 30,
        retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not endpoint:
            raise ConfigurationError("The Decisions API endpoint is required")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self._client = client

    async def decide(self, state: Any, questions: dict[str, Question]) -> DecisionResponse:
        serialized: dict[str, dict[str, Any]] = {}
        for key, question in questions.items():
            item = question.model_dump(exclude_none=True)
            if isinstance(question, ChoiceQuestion):
                item["criteria"] = item.pop("options")
            elif isinstance(question, ScoreQuestion):
                item["criteria"] = item.pop("levels")
            serialized[key] = item
        payload = {
            "model": self.model,
            "state": compact_state(state),
            "questions": serialized,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                if self._client is not None:
                    response = await self._client.post(
                        self.endpoint, json=payload, headers=headers, timeout=self.timeout
                    )
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                answers = TypeAdapter(dict[str, Answer]).validate_python(data["answers"])
                usage = data.get("usage", {})
                return DecisionResponse(
                    answers=answers,
                    model=data.get("model", self.model),
                    input_tokens=usage.get("input_tokens", usage.get("prompt_tokens", 0)),
                    output_tokens=usage.get("output_tokens", usage.get("completion_tokens", 0)),
                    cost=usage.get("cost", 0) or 0,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break
                await asyncio.sleep(min(0.05 * 2**attempt + random.random() * 0.01, 1))
        raise AdapterError(f"Decision request failed: {type(last_error).__name__}") from last_error


class LangChainDecider:
    """Optional adapter matching TypeSafeClassifier.invoke semantics."""

    def __init__(self, classifier: Any | None = None, model: str = "unspecified") -> None:
        if classifier is None:
            try:
                from langchain_typesafe import TypeSafeClassifier
            except ImportError as exc:
                raise ConfigurationError("Install BreakFuser[langchain] for this adapter") from exc
            classifier = TypeSafeClassifier()
        self.classifier = classifier
        self.model = model

    async def decide(self, state: Any, questions: dict[str, Question]) -> DecisionResponse:
        started = time.perf_counter()
        raw = await asyncio.to_thread(
            self.classifier.invoke,
            {
                "state": compact_state(state),
                "questions": {
                    key: question.model_dump(exclude_none=True)
                    for key, question in questions.items()
                },
            },
        )
        if hasattr(raw, "model_dump"):
            raw = raw.model_dump()
        candidates = raw.get("answers", {}) if isinstance(raw, dict) else {}
        if isinstance(raw, dict):
            for collection in ("choices", "scores", "nouls"):
                for key, value in raw.get(collection, {}).items():
                    item = value.model_dump() if hasattr(value, "model_dump") else value
                    candidates[key] = {"type": collection[:-1], **item}
        answers = TypeAdapter(dict[str, Answer]).validate_python(candidates)
        return DecisionResponse(
            answers=answers, model=self.model, latency_ms=(time.perf_counter() - started) * 1000
        )


class MockDecider:
    """Deterministic batched decisions with controllable per-request latency."""

    def __init__(self, latency_seconds: float = 0) -> None:
        self.latency_seconds = latency_seconds
        self.call_count = 0
        self.question_counts: list[int] = []

    async def decide(self, state: Any, questions: dict[str, Question]) -> DecisionResponse:
        self.call_count += 1
        self.question_counts.append(len(questions))
        if self.latency_seconds:
            await asyncio.sleep(self.latency_seconds)
        started = time.perf_counter()
        text = str(compact_state(state))
        answers: dict[str, Answer] = {}
        for key, question in questions.items():
            instruction = question.instructions.lower()
            if isinstance(question, NoulQuestion):
                probability = self._noul(instruction, text)
                answers[key] = NoulAnswer(noul=probability)
            elif isinstance(question, ScoreQuestion):
                score = self._score(instruction, text)
                answers[key] = ScoreAnswer(
                    score=score,
                    probabilities={
                        level: 1.0
                        if index == min(int(score * len(question.levels)), len(question.levels) - 1)
                        else 0.0
                        for index, level in enumerate(question.levels)
                    },
                    confidence=0.9,
                )
            else:
                selected = self._choice(question, instruction, text)
                probability = 0.9
                others = {
                    option: (1 - probability) / (len(question.options) - 1)
                    for option in question.options
                    if option != selected
                }
                answers[key] = ChoiceAnswer(
                    choice=selected,
                    probabilities={
                        option: probability if option == selected else others[option]
                        for option in question.options
                    },
                    confidence=probability,
                )
        return DecisionResponse(
            answers=answers,
            model="mock-decider",
            input_tokens=estimate_tokens(text),
            latency_ms=(time.perf_counter() - started) * 1000,
        )

    @staticmethod
    def _noul(instruction: str, text: str) -> float:
        lowered = text.lower()
        if "deterministic code" in instruction:
            return 0.95 if re.search(r"\d\s*[+*/-]\s*\d", text) else 0.05
        if "prompt injection" in instruction or "injection" in instruction:
            risky = any(
                marker in lowered
                for marker in ("ignore previous", "system prompt", "exfiltrate", "do not follow")
            )
            return 0.98 if risky else 0.02
        if "pii" in instruction or "sensitive" in instruction:
            risky = bool(
                re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b\d{3}-\d{2}-\d{4}\b", text)
            )
            return 0.97 if risky else 0.03
        if "safe_surface" in instruction or "without a refusal" in instruction:
            return 0.1 if "[[hard]]" in text else 0.9
        if "atomic" in instruction:
            return 0.3 if " and " in lowered else 0.93
        if "necessary" in instruction:
            return 0.08 if "irrelevant" in lowered else 0.92
        if "resolve all" in instruction or "complete without" in instruction:
            has_facts = "verified_facts" in lowered and "verified_facts': []" not in lowered
            resolved = has_facts or any(
                marker in lowered
                for marker in ("verified remote fact", "not required", "deterministic result")
            )
            return 0.96 if resolved else 0.55
        if "hard_refusal" in instruction or "refuses" in instruction:
            return (
                0.97
                if any(
                    value in lowered for value in ("can’t help", "cannot help", "i can't assist")
                )
                else 0.02
            )
        if "hedge" in instruction:
            return (
                0.95
                if any(value in lowered for value in ("it depends", "roughly", "may vary"))
                else 0.03
            )
        if "hallucination" in instruction:
            return 0.9 if "unverified" in lowered else 0.05
        if "unsafe" in instruction or "risky" in instruction:
            return (
                0.98
                if any(value in lowered for value in ("rm -rf", "curl ", "credentials"))
                else 0.02
            )
        return 0.85

    @staticmethod
    def _score(instruction: str, text: str) -> float:
        if "risk" in instruction:
            return 0.9 if "[[hard]]" in text else 0.15
        if "complete" in instruction or "ground" in instruction or "relevance" in instruction:
            return 0.9 if "verified remote fact" in text.lower() else 0.45
        return 0.75

    @staticmethod
    def _choice(question: ChoiceQuestion, instruction: str, text: str) -> str:
        options = question.options
        lowered = text.lower()
        if "endpoint" in instruction or "tier" in instruction:
            return (
                "local"
                if "local" in options and "local-only" in lowered
                else "smart"
                if "smart" in options
                else next(iter(options))
            )
        if "context mode" in instruction or "isolated" in instruction:
            return (
                "fork"
                if "fork" in options and "continue" in lowered
                else "isolated"
                if "isolated" in options
                else next(iter(options))
            )
        if "strategy" in instruction:
            for candidate in (
                "refusal_repair",
                "output_shape_coercion",
                "academic_framing",
                "direct",
            ):
                if candidate in options and (
                    (candidate == "refusal_repair" and "can’t help" in lowered)
                    or (candidate == "output_shape_coercion" and "it depends" in lowered)
                    or (candidate == "academic_framing" and "[[hard]]" in lowered)
                    or candidate == "direct"
                ):
                    return candidate
        if "deterministic" in instruction and "yes" in options:
            return (
                "yes"
                if re.search(r"\d\s*[+*/-]\s*\d", text)
                else "no"
                if "no" in options
                else "other"
            )
        return next(
            (option for option in options if option not in {"other", "insufficient_context"}),
            next(iter(options)),
        )


class LocalRuleDecider(MockDecider):
    """Offline deterministic decisions for deployments without a decider service."""

    async def decide(self, state: Any, questions: dict[str, Question]) -> DecisionResponse:
        self.call_count += 1
        self.question_counts.append(len(questions))
        started = time.perf_counter()
        text = str(compact_state(state))
        answers: dict[str, Answer] = {}
        for key, question in questions.items():
            instruction = question.instructions.lower()
            if isinstance(question, NoulQuestion):
                answers[key] = NoulAnswer(noul=self._noul(instruction, text))
            elif isinstance(question, ScoreQuestion):
                score = self._score(instruction, text)
                answers[key] = ScoreAnswer(
                    score=score,
                    probabilities={
                        level: 1.0
                        if index == min(int(score * len(question.levels)), len(question.levels) - 1)
                        else 0.0
                        for index, level in enumerate(question.levels)
                    },
                    confidence=0.9,
                )
            else:
                selected = self._choice(question, instruction, text)
                probability = 0.9
                others = {
                    option: (1 - probability) / (len(question.options) - 1)
                    for option in question.options
                    if option != selected
                }
                answers[key] = ChoiceAnswer(
                    choice=selected,
                    probabilities={
                        option: probability if option == selected else others[option]
                        for option in question.options
                    },
                    confidence=probability,
                )
        return DecisionResponse(
            answers=answers,
            model="local-rules",
            input_tokens=estimate_tokens(text),
            latency_ms=(time.perf_counter() - started) * 1000,
        )
