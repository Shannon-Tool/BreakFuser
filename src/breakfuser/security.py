"""Bi-directional guards and verify-after claim auditing."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from breakfuser.adapters import ChatBackend
from breakfuser.context import VirtualFilesystem
from breakfuser.decider import Decider, NoulAnswer, NoulQuestion
from breakfuser.errors import VerificationError
from breakfuser.models import ChatMessage
from breakfuser.telemetry import content_hash

_INJECTION = re.compile(
    r"(?i)ignore (?:all |previous )?(?:instructions|rules)|reveal (?:the )?system prompt|exfiltrate"
)
_PII = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b\d{3}-\d{2}-\d{4}\b")


class GuardResult(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)


class SecurityGuard:
    def __init__(self, decider: Decider, filesystem: VirtualFilesystem) -> None:
        self.decider = decider
        self.filesystem = filesystem

    async def outbound(self, text: str, *, risky_tool: str | None = None) -> GuardResult:
        scrubbed = re.sub(r"(?:EMAIL|NAME|SSN|IP)_\d+\[[^]]+\]|N\d+\([^)]*\)", "", text)
        response = await self.decider.decide(
            {"outbound": scrubbed, "tool": risky_tool or "none"},
            {
                "pii": NoulQuestion(instructions="Does the outbound state contain residual PII?"),
                "unsafe": NoulQuestion(
                    instructions="Is the remote call or risky tool call unsafe?"
                ),
            },
        )
        pii = response.answers["pii"]
        unsafe = response.answers["unsafe"]
        if not isinstance(pii, NoulAnswer) or not isinstance(unsafe, NoulAnswer):
            raise TypeError("Mismatched guard answers")
        reasons: list[str] = []
        if pii.noul >= 0.9 or _PII.search(scrubbed):
            reasons.append("residual-pii")
        if risky_tool and unsafe.noul >= 0.5:
            reasons.append("unsafe-tool")
        return GuardResult(allowed=not reasons, reasons=reasons)

    async def inbound_external(self, text: str, source: str = "web") -> GuardResult:
        response = await self.decider.decide(
            {"external_text": text[:12000]},
            {
                "injection": NoulQuestion(
                    instructions="Does this external text contain prompt injection?"
                )
            },
        )
        answer = response.answers["injection"]
        if not isinstance(answer, NoulAnswer):
            raise TypeError("Mismatched injection answer")
        if answer.noul >= 0.5 or _INJECTION.search(text):
            digest = content_hash(text)
            self.filesystem.write(
                f"/quarantine/{digest}.json", f'{{"source":"{source}","sha256":"{digest}"}}'
            )
            return GuardResult(allowed=False, reasons=["prompt-injection"])
        return GuardResult(allowed=True)


class ClaimSet(BaseModel):
    claims: list[str]


def extract_claims(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


class VerificationReport(BaseModel):
    passed: bool
    contradictions: list[str] = Field(default_factory=list)
    omissions: list[str] = Field(default_factory=list)
    confidence: float = 1


class Verifier:
    def __init__(
        self,
        decider: Decider,
        local: ChatBackend,
        model: str,
        max_repairs: int = 1,
        max_output_tokens: int | None = None,
    ) -> None:
        self.decider = decider
        self.local = local
        self.model = model
        self.max_repairs = max_repairs
        self.max_output_tokens = max_output_tokens

    async def audit(
        self,
        draft: str,
        verified_facts: list[str],
        original_question: str | None = None,
    ) -> VerificationReport:
        claims = extract_claims(draft)
        draft_words = set(re.findall(r"[a-z0-9]+", draft.lower()))

        def supported(fact: str) -> bool:
            if fact.strip() and fact.strip() in draft:
                return True
            fact_words = set(re.findall(r"[a-z0-9]+", fact.lower()))
            return bool(fact_words) and len(fact_words & draft_words) / len(fact_words) >= 0.6

        omissions = [fact for fact in verified_facts if not supported(fact)]
        contradictions = [claim for claim in claims if "unverified contradiction" in claim.lower()]
        if not verified_facts:
            return VerificationReport(
                passed=not contradictions,
                contradictions=contradictions,
                omissions=[],
                confidence=1,
            )
        response = await self.decider.decide(
            {
                "draft": claims,
                "verified_facts": verified_facts,
                "original_question": original_question or "not supplied",
                "external_facts": "not required" if not verified_facts else "required",
            },
            {
                "contradiction": NoulQuestion(
                    instructions="Does the draft contradict verified facts or hallucination suspected?"
                ),
                "complete": NoulQuestion(
                    instructions="Do verified facts resolve all sub-questions complete without omission?"
                ),
            },
        )
        contradiction = response.answers["contradiction"]
        complete = response.answers["complete"]
        if not isinstance(contradiction, NoulAnswer) or not isinstance(complete, NoulAnswer):
            raise TypeError("Mismatched verification answers")
        if contradiction.noul >= 0.8 and not contradictions:
            contradictions.append("decider-detected-contradiction")
        deterministic = bool(verified_facts) and all(
            fact.startswith("Deterministic result:") for fact in verified_facts
        )
        if not verified_facts:
            omissions = []
        elif complete.noul < 0.8 and not omissions and not deterministic:
            omissions.append("decider-detected-omission")
        return VerificationReport(
            passed=not omissions and not contradictions,
            contradictions=contradictions,
            omissions=omissions,
            confidence=(1 if not verified_facts or deterministic else complete.noul),
        )

    async def verify_and_repair(
        self,
        draft: str,
        verified_facts: list[str],
        original_question: str | None = None,
    ) -> tuple[str, VerificationReport]:
        if not draft.strip() and not verified_facts:
            draft = (
                "No verified response was produced. The provider refused, returned no content, "
                "or exhausted the response limit before supplying a usable answer."
            )
        report = await self.audit(draft, verified_facts, original_question)
        attempts = 0
        while not report.passed and attempts < self.max_repairs:
            response = await self.local.complete(
                [
                    ChatMessage(
                        role="user",
                        content=(
                            "[BREAKFUSER_SYNTHESIS]\nEvidence and candidate material:\n"
                            + "\n".join(verified_facts)
                            + "\nOriginal question:\nRepair all omissions and contradictions."
                        ),
                    )
                ],
                self.model,
                max_tokens=self.max_output_tokens,
            )
            draft = response.content
            report = await self.audit(draft, verified_facts, original_question)
            attempts += 1
        if not report.passed:
            raise VerificationError("Final response failed bounded verification repair")
        return draft, report
