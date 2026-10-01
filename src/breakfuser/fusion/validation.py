"""Deterministic validation for structured, creative, code, and tool artifacts."""

from __future__ import annotations

import ast
import json
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from breakfuser.fusion.domain import Domain, ResponseContract, VerificationMode
from breakfuser.models import ToolCall, ToolDefinition
from breakfuser.pentest import PentestProposal


class DeterministicValidation(BaseModel):
    status: Literal["passed", "failed", "not_applicable"]
    errors: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "passed"


def _python_blocks(text: str) -> list[str]:
    fenced = [
        match.group(1).strip()
        for match in re.finditer(r"```(?:python|py)\s*\n(.*?)```", text, re.S | re.I)
    ]
    if fenced:
        return fenced
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^(?:async\s+def|def|class)\s+\w+", line)
    ]
    blocks: list[str] = []
    for index, start in enumerate(starts):
        end_limit = starts[index + 1] if index + 1 < len(starts) else len(lines)
        for end in range(end_limit, start, -1):
            candidate = "\n".join(lines[start:end]).strip()
            try:
                ast.parse(candidate)
            except SyntaxError:
                continue
            blocks.append(candidate)
            break
    return blocks


class DeterministicValidatorSuite:
    def validate(self, answer: str, contract: ResponseContract) -> DeterministicValidation:
        if contract.domain == Domain.DETERMINISTIC:
            return DeterministicValidation(status="passed")
        if contract.output_shape == "exact_json":
            return self._json(answer, contract.format_envelope.exact_json)
        if contract.domain == Domain.PENTEST:
            return self._pentest(answer)
        if contract.domain == Domain.CODING:
            return self._python(answer, contract)
        if contract.verification_mode == VerificationMode.STRUCTURAL:
            expected = contract.format_envelope.exact_line_count
            if expected is None:
                return DeterministicValidation(status="not_applicable")
            actual = len([line for line in answer.splitlines() if line.strip()])
            if actual != expected:
                words = {6: "six"}
                expected_text = words.get(expected, str(expected))
                return DeterministicValidation(
                    status="failed",
                    errors=[f"Expected exactly {expected_text} non-empty lines; got {actual}."],
                )
            return DeterministicValidation(status="passed")
        return DeterministicValidation(status="not_applicable")

    @staticmethod
    def _json(answer: str, expected: dict[str, object] | None) -> DeterministicValidation:
        text = answer.strip()
        fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n?```", text, re.S | re.I)
        if fence:
            text = fence.group(1).strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            return DeterministicValidation(status="failed", errors=[str(exc)])
        if not isinstance(value, dict):
            return DeterministicValidation(status="failed", errors=["Expected a JSON object."])
        if expected is not None and value != expected:
            return DeterministicValidation(
                status="failed", errors=["JSON object differs from requested keys or values."]
            )
        return DeterministicValidation(status="passed")

    @staticmethod
    def _python(answer: str, contract: ResponseContract) -> DeterministicValidation:
        errors: list[str] = []
        blocks = _python_blocks(answer)
        if not blocks:
            errors.append("No complete Python definition was found.")
        trees: list[ast.AST] = []
        for block in blocks:
            try:
                trees.append(ast.parse(block))
            except SyntaxError as exc:
                errors.append(f"Python syntax error: {exc.msg} at line {exc.lineno}.")
        for identifier in contract.format_envelope.required_identifiers:
            if not any(
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                and node.name == identifier
                for tree in trees
                for node in ast.walk(tree)
            ):
                errors.append(f"Required identifier {identifier} is missing.")
        return DeterministicValidation(status="failed" if errors else "passed", errors=errors)

    @staticmethod
    def _pentest(answer: str) -> DeterministicValidation:
        decoder = json.JSONDecoder()
        for index, character in enumerate(answer):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(answer[index:])
                proposal = PentestProposal.model_validate(value)
            except (json.JSONDecodeError, ValueError):
                continue
            if urlsplit(proposal.url).hostname != "127.0.0.1":
                return DeterministicValidation(
                    status="failed", errors=["Pentest target must be 127.0.0.1."]
                )
            return DeterministicValidation(status="passed")
        return DeterministicValidation(
            status="failed", errors=["No schema-valid pentest proposal was found."]
        )


def validate_tool_calls(tool_calls: list[ToolCall], tools: list[dict[str, object]]) -> list[str]:
    definitions = {
        definition.function.name: definition
        for definition in (ToolDefinition.model_validate(tool) for tool in tools)
    }
    errors: list[str] = []
    for call in tool_calls:
        definition = definitions.get(call.function.name)
        if definition is None:
            errors.append(f"Unknown tool function: {call.function.name}")
            continue
        try:
            arguments = json.loads(call.function.arguments)
        except json.JSONDecodeError:
            errors.append(f"Arguments for {call.function.name} are not valid JSON.")
            continue
        if not isinstance(arguments, dict):
            errors.append(f"Arguments for {call.function.name} must be a JSON object.")
            continue
        required = definition.function.parameters.get("required", [])
        if isinstance(required, list):
            errors.extend(
                f"Arguments for {call.function.name} are missing required property: {name}"
                for name in required
                if name not in arguments
            )
    return errors
