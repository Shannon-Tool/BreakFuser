"""Conservative recovery of useful content from length-truncated turns."""

from __future__ import annotations

import ast
import re

from breakfuser.harvest.models import EvidenceSpan, HarvestTurn, RefusalClass


def _prose_prefix(text: str) -> tuple[str, str]:
    boundaries = list(re.finditer(r"[.!?](?=\s|$)", text))
    if not boundaries:
        return "", text.strip()
    end = boundaries[-1].end()
    return text[:end].strip(), text[end:].strip()


def _valid_python_prefixes(text: str) -> list[str]:
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^(?:async\s+def|def|class)\s+\w+", line)
    ]
    blocks: list[str] = []
    for start in starts:
        # A later top-level definition belongs to a separate candidate block.
        end_limit = next((index for index in starts if index > start), len(lines))
        for end in range(end_limit, start, -1):
            candidate = "\n".join(lines[start:end]).strip()
            if not candidate:
                continue
            try:
                ast.parse(candidate)
            except SyntaxError:
                continue
            blocks.append(candidate)
            break
    return blocks


def salvage_complete_prefix(text: str) -> tuple[str, str]:
    """Return useful complete content and an untouched continuation anchor."""
    text = text.strip()
    if not text:
        return "", ""
    if not re.search(r"(?:```|^(?:async\s+def|def|class)\s+\w+)", text, re.M):
        return _prose_prefix(text)

    parts: list[str] = []
    first_code = re.search(r"(?:```|^(?:async\s+def|def|class)\s+\w+)", text, re.M)
    if first_code:
        prose, _ = _prose_prefix(text[: first_code.start()].strip())
        if prose:
            parts.append(prose)
    for match in re.finditer(r"```(?:python|py)?\s*\n(.*?)```", text, re.S | re.I):
        block = match.group(1).strip()
        try:
            ast.parse(block)
        except SyntaxError:
            continue
        parts.append(block)
    for block in _valid_python_prefixes(text):
        if all(block != existing for existing in parts):
            parts.append(block)
    return "\n\n".join(dict.fromkeys(parts)).strip(), text[-150:]


class TruncationSalvager:
    def salvage(self, turn: HarvestTurn) -> EvidenceSpan | None:
        text = turn.desanitized_response.strip()
        if not text or turn.quality in {
            RefusalClass.HARD_REFUSAL,
            RefusalClass.OUT_OF_SCOPE,
            RefusalClass.HALLUCINATION_SUSPECTED,
        }:
            return None
        if turn.quality == RefusalClass.NONE:
            return EvidenceSpan(
                source_id=turn.turn_id,
                origin="remote",
                text=text,
                atom_ids=[turn.atom_id],
                complete=True,
                confidence=turn.confidence,
            )
        if turn.quality not in {
            RefusalClass.TRUNCATED,
            RefusalClass.PARTIAL_REFUSAL,
            RefusalClass.HEDGE_HEAVY,
            RefusalClass.DISCLAIMER_ONLY,
        }:
            return None
        prefix, tail = salvage_complete_prefix(text)
        if not prefix:
            return None
        return EvidenceSpan(
            source_id=turn.turn_id,
            origin="remote",
            text=prefix,
            atom_ids=[turn.atom_id],
            complete=False,
            salvaged=True,
            tail_anchor=tail[-150:],
            confidence=turn.confidence,
        )
