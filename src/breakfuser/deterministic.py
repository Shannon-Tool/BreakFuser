"""Exact operations deliberately kept outside generative/classifier models."""

from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable
from datetime import date, timedelta

_OPERATORS: dict[type[ast.AST], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def arithmetic(expression: str) -> float:
    """Evaluate a numeric expression without eval or model inference."""
    if len(expression) > 200:
        raise ValueError("Expression too long")

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
            value = evaluate(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        raise ValueError("Only numeric arithmetic is supported")

    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid arithmetic expression") from exc
    return evaluate(parsed)


def count_occurrences(text: str, needle: str, *, case_sensitive: bool = False) -> int:
    if not needle:
        raise ValueError("Needle must not be empty")
    if not case_sensitive:
        text, needle = text.lower(), needle.lower()
    return text.count(needle)


def date_math(start: str, days: int = 0) -> str:
    return (date.fromisoformat(start) + timedelta(days=days)).isoformat()


def is_small_talk(question: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?i)\s*(?:hello|hi|hey|hello there|hi there|hey there|good morning|"
            r"good afternoon|good evening|thanks|thank you)[!.\s]*",
            question,
        )
    )


def deterministic_answer(question: str) -> str | None:
    match = re.fullmatch(r"\s*(?:what is\s+)?([\d\s()+*/.%^-]+)\??\s*", question, re.I)
    if match and re.search(r"\d\s*[+*/%^-]\s*\d", match.group(1)):
        expression = match.group(1).replace("^", "**").rstrip("?")
        value = arithmetic(expression)
        return str(int(value)) if value.is_integer() else str(value)
    match = re.fullmatch(r"\s*count\s+['\"](.+?)['\"]\s+in\s+['\"](.*)['\"]\s*", question, re.I)
    if match:
        return str(count_occurrences(match.group(2), match.group(1)))
    match = re.fullmatch(
        r"\s*what date is\s+(\d{4}-\d{2}-\d{2})\s+([+-]?\d+)\s+days\??\s*", question, re.I
    )
    if match:
        return date_math(match.group(1), int(match.group(2)))
    return None
