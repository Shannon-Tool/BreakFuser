"""PAPILLON, Prεεmpt-style, and PriCon local/remote privacy transforms."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import random
import re
import secrets
from dataclasses import dataclass
from typing import Any, Protocol

from ff3 import FF3Cipher

from breakfuser.adapters import ChatBackend
from breakfuser.config import SanitizerSettings
from breakfuser.errors import SecurityBlocked
from breakfuser.models import ChatMessage

_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_ENTITY = re.compile(
    r"\b\d{3}-\d{2}-\d{4}\b|\b(?:\d{1,3}\.){3}\d{1,3}\b|"
    r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?<![\w.])\d+(?:\.\d+)?(?![\w.])"
)
_NAME_SEQUENCE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")
_PREFIX_NAME = re.compile(r"(?i)\b(?:contact|patient|employee|user|person)\s+([A-Z][a-z]+)\b")
_CONTEXT_NAME = re.compile(r"\b([A-Z][a-z]+)(?=\s+(?:age|has|uses|is|needs|was|compares)\b)")
_IDENTIFIER_NUMBER = re.compile(r"(?i)\bID\s*(\d+)\b")
_PERSONAL_NUMBER_CONTEXT = re.compile(
    r"(?i)\b(?:age|salary|employee|patient|medical|height|weight|income|account|ssn)\b"
)
_INSTRUCTION_WORDS = {
    "Act",
    "Answer",
    "Assume",
    "Build",
    "Compare",
    "Continue",
    "Crescendo",
    "Explain",
    "Find",
    "For",
    "Fresh",
    "Give",
    "Hello",
    "Identify",
    "Ignore",
    "Independent",
    "MIT",
    "OpenSSL",
    "Original",
    "Prior",
    "Re",
    "Return",
    "Solve",
    "The",
    "This",
    "Verified",
    "What",
    "When",
}
_NAME_PHRASE_EXCLUSIONS = {
    "Session Intent",
    "Artifacts Created",
    "Next Steps",
    "Original Question",
    "Verified Facts",
    "Prior Authorized",
    "Fresh Minimal",
}


@dataclass(frozen=True)
class Entity:
    kind: str
    value: str
    start: int
    end: int


class NERRecognizer:
    """Conservative typed recognizer that preserves ordinary instructions and task numbers."""

    def recognize(self, text: str) -> list[Entity]:
        entities: list[Entity] = []
        personal_numbers = bool(
            _PERSONAL_NUMBER_CONTEXT.search(text)
            or _PREFIX_NAME.search(text)
            or any(
                match.group(1) not in _INSTRUCTION_WORDS for match in _CONTEXT_NAME.finditer(text)
            )
        )
        for match in _ENTITY.finditer(text):
            value = match.group(0)
            if "@" in value:
                kind = "email"
            elif re.fullmatch(r"\d{3}-\d{2}-\d{4}", value):
                kind = "ssn"
            elif "." in value and value.replace(".", "").isdigit() and value.count(".") == 3:
                kind = "ip"
            elif personal_numbers:
                kind = "number"
            else:
                continue
            entities.append(Entity(kind, value, match.start(), match.end()))
        if personal_numbers:
            for match in _IDENTIFIER_NUMBER.finditer(text):
                entities.append(Entity("number", match.group(1), match.start(1), match.end(1)))
        for match in _NAME_SEQUENCE.finditer(text):
            if match.group(0) not in _NAME_PHRASE_EXCLUSIONS:
                entities.append(Entity("name", match.group(0), match.start(), match.end()))
        for match in _PREFIX_NAME.finditer(text):
            if match.group(1) not in _INSTRUCTION_WORDS:
                entities.append(Entity("name", match.group(1), match.start(1), match.end(1)))
        for match in _CONTEXT_NAME.finditer(text):
            if match.group(1) not in _INSTRUCTION_WORDS:
                entities.append(Entity("name", match.group(1), match.start(1), match.end(1)))
        if re.fullmatch(r"[A-Z][a-z]+", text.strip()) and text.strip() not in _INSTRUCTION_WORDS:
            start = text.index(text.strip())
            entities.append(Entity("name", text.strip(), start, start + len(text.strip())))
        unique: dict[tuple[int, int], Entity] = {}
        for entity in sorted(entities, key=lambda item: (item.start, -(item.end - item.start))):
            if any(
                entity.start < other.end and other.start < entity.end for other in unique.values()
            ):
                continue
            unique[(entity.start, entity.end)] = entity
        return sorted(unique.values(), key=lambda item: item.start)


class SanitizedPayload:
    def __init__(self, text: str, helper: str = "", metadata: dict[str, Any] | None = None) -> None:
        self.text = text
        self.helper = helper
        self.metadata = metadata or {}


class Sanitizer(Protocol):
    async def sanitize(self, text: str) -> SanitizedPayload: ...

    async def desanitize(self, text: str, helper: str) -> str: ...


def _key_material(key: str | None) -> tuple[str, str]:
    material = key or secrets.token_hex(32)
    digest = material.encode().hex()[:64].ljust(64, "0")
    return digest, hashlib.sha256(material.encode()).hexdigest()[:16]


def _cipher(key: str, tweak: str, alphabet: str = _ALPHABET) -> FF3Cipher:
    return FF3Cipher.withCustomAlphabet(key, tweak, alphabet)


def _affine_encrypt(value: str, key: bytes, alphabet: str) -> str:
    size = len(alphabet)
    a = 5 if size % 5 else 7
    while math.gcd(a, size) != 1:
        a += 2
    b = key[0] % size
    return "".join(
        alphabet[(a * alphabet.index(char) + b) % size] if char in alphabet else char
        for char in value
    )


def _affine_decrypt(value: str, key: bytes, alphabet: str) -> str:
    size = len(alphabet)
    a = 5 if size % 5 else 7
    while math.gcd(a, size) != 1:
        a += 2
    inverse = pow(a, -1, size)
    b = key[0] % size
    return "".join(
        alphabet[(inverse * (alphabet.index(char) - b)) % size] if char in alphabet else char
        for char in value
    )


def fpe_encrypt(value: str, key: str, tweak: str) -> str:
    """Preserve separators while encrypting letters/digits with FF3 or short-domain permutation."""
    groups = re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9]+", value)
    output: list[str] = []
    for group in groups:
        if not group or not group[0].isalnum():
            output.append(group)
        elif len(group) >= 4:
            output.append(_cipher(key, tweak).encrypt(group))
        else:
            output.append(_affine_encrypt(group, bytes.fromhex(key), _ALPHABET))
    return "".join(output)


def fpe_decrypt(value: str, key: str, tweak: str) -> str:
    groups = re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9]+", value)
    output: list[str] = []
    for group in groups:
        if not group or not group[0].isalnum():
            output.append(group)
        elif len(group) >= 4:
            output.append(_cipher(key, tweak).decrypt(group))
        else:
            output.append(_affine_decrypt(group, bytes.fromhex(key), _ALPHABET))
    return "".join(output)


class PreemptSanitizer:
    """Stateless keyed transforms; all reversible state travels in the protected helper."""

    def __init__(
        self, key: str | None = None, *, epsilon: float = 4, seed: int | None = None
    ) -> None:
        if epsilon <= 0:
            raise ValueError("LDP epsilon must be positive")
        self.key, self.tweak = _key_material(key)
        self.epsilon = epsilon
        self.random = random.Random(seed)
        self.ner = NERRecognizer()

    async def sanitize(self, text: str) -> SanitizedPayload:
        pieces: list[str] = []
        cursor = 0
        helper: dict[str, dict[str, str]] = {}
        for index, entity in enumerate(self.ner.recognize(text)):
            pieces.append(text[cursor : entity.start])
            token = f"E{index}"
            encrypted = fpe_encrypt(entity.value, self.key, self.tweak)
            helper[token] = {"encrypted": encrypted, "kind": entity.kind}
            if entity.kind == "number":
                number = float(entity.value)
                scale = max(1, abs(number) * 0.05) / self.epsilon
                noise = self.random.expovariate(1 / scale) * (
                    -1 if self.random.random() < 0.5 else 1
                )
                replacement = f"{number + noise:.6g}"
                pieces.append(f"N{index}({replacement})")
            else:
                pieces.append(f"{entity.kind.upper()}_{index}[{encrypted}]")
            cursor = entity.end
        pieces.append(text[cursor:])
        encoded = (
            base64.urlsafe_b64encode(json.dumps(helper, separators=(",", ":")).encode()).decode()
            if helper
            else ""
        )
        return SanitizedPayload(
            "".join(pieces), encoded, {"entities": len(helper), "mode": "preempt"}
        )

    async def desanitize(self, text: str, helper: str) -> str:
        if not helper:
            return text
        mapping = json.loads(base64.urlsafe_b64decode(helper.encode()))
        result = text
        for index, (token, item) in enumerate(mapping.items()):
            original = fpe_decrypt(item["encrypted"], self.key, self.tweak)
            kind = item["kind"]
            pattern = (
                rf"N{index}\([^)]*\)"
                if kind == "number"
                else rf"{kind.upper()}_{index}\[{re.escape(item['encrypted'])}\]"
            )
            result = re.sub(pattern, original, result)
            result = result.replace(token, original)
        return result


class PapillonSanitizer:
    def __init__(
        self, local: ChatBackend, model: str, max_output_tokens: int | None = None
    ) -> None:
        self.local = local
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.fallback = PreemptSanitizer()

    async def sanitize(self, text: str) -> SanitizedPayload:
        protected = await self.fallback.sanitize(text)
        response = await self.local.complete(
            [
                ChatMessage(
                    role="user",
                    content=(
                        "Create a concise remote proxy prompt that preserves the task while retaining only "
                        f"the protected placeholders. Do not infer identities:\n{protected.text}"
                    ),
                )
            ],
            self.model,
            max_tokens=self.max_output_tokens,
        )
        return SanitizedPayload(response.content, protected.helper, {"mode": "papillon"})

    async def desanitize(self, text: str, helper: str) -> str:
        return await self.fallback.desanitize(text, helper)

    async def aggregate(self, original: str, remote_response: str) -> str:
        response = await self.local.complete(
            [
                ChatMessage(
                    role="user",
                    content=f"Original request:\n{original}\nRemote information:\n{remote_response}",
                )
            ],
            self.model,
            max_tokens=self.max_output_tokens,
        )
        return response.content


class PriConSanitizer:
    """Reversible mathematical/logical abstraction of task entities and values."""

    async def sanitize(self, text: str) -> SanitizedPayload:
        entities = NERRecognizer().recognize(text)
        mapping: dict[str, str] = {}
        output = text
        for index, entity in enumerate(reversed(entities)):
            original_index = len(entities) - 1 - index
            variable = f"N{original_index}" if entity.kind == "number" else f"X{original_index}"
            mapping[variable] = entity.value
            output = output[: entity.start] + variable + output[entity.end :]
        helper = base64.urlsafe_b64encode(json.dumps(mapping).encode()).decode()
        return SanitizedPayload(
            f"Solve this abstract logical problem; variables are opaque substitutions:\n{output}",
            helper,
            {"mode": "pricon", "variables": len(mapping)},
        )

    async def desanitize(self, text: str, helper: str) -> str:
        mapping = json.loads(base64.urlsafe_b64decode(helper.encode())) if helper else {}
        result = text
        for variable, value in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
            result = re.sub(rf"\b{re.escape(variable)}\b", value, result)
        return result


def build_sanitizer(
    settings: SanitizerSettings,
    local: ChatBackend,
    model: str,
    max_output_tokens: int | None = None,
) -> Sanitizer:
    key = settings.key.get_secret_value() if settings.key else None
    if settings.mode == "preempt":
        return PreemptSanitizer(key)
    if settings.mode == "papillon":
        return PapillonSanitizer(local, model, max_output_tokens)
    return PriConSanitizer()


class RoutingMetadataGuard:
    """Length padding and fixed-route policy reduce observable request-size/timing signals."""

    def __init__(self, enabled: bool = True, bucket_size: int = 256) -> None:
        self.enabled = enabled
        self.bucket_size = bucket_size

    def prepare(self, text: str) -> str:
        if not self.enabled:
            return text
        target = max(self.bucket_size, math.ceil(len(text) / self.bucket_size) * self.bucket_size)
        return text + " " * (target - len(text))


def enforce_privacy_fallback(text: str, strictness: str, fallback: str) -> str:
    placeholders = list(re.finditer(r"(?:EMAIL|NAME|SSN|IP)_\d+\[[^]]+\]|N\d+\([^)]*\)", text))
    residual = [
        entity
        for entity in NERRecognizer().recognize(text)
        if not any(
            entity.start < placeholder.end() and placeholder.start() < entity.end
            for placeholder in placeholders
        )
    ]
    if not residual or strictness == "permissive":
        return text
    if fallback == "block" or strictness == "strict":
        raise SecurityBlocked("Residual sensitive entities detected after sanitization")
    if fallback == "redact":
        result = text
        for entity in reversed(residual):
            result = result[: entity.start] + "[redacted]" + result[entity.end :]
        return result
    return "[local-only: remote delegation suppressed]"
