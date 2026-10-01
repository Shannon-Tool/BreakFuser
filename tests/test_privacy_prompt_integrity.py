from __future__ import annotations

import pytest

from breakfuser.harvest.detector import RefusalDetector
from breakfuser.harvest.models import RefusalClass
from breakfuser.privacy import NERRecognizer, PreemptSanitizer


def test_ordinary_prompt_words_and_task_numbers_are_preserved() -> None:
    recognizer = NERRecognizer()
    assert recognizer.recognize("Hello!") == []
    assert recognizer.recognize("Compare 27 * 19") == []
    assert recognizer.recognize("Session Intent") == []
    named = recognizer.recognize("Alice Example has employee ID7391")
    assert {entity.kind for entity in named} == {"name", "number"}


@pytest.mark.asyncio
async def test_greeting_and_arithmetic_prompt_are_not_gibberish() -> None:
    text = "Hello! What is 27 * 19?"
    protected = await PreemptSanitizer("key").sanitize(text)
    assert protected.text == text
    assert protected.helper == ""


def test_content_filter_is_not_truncation() -> None:
    result = RefusalDetector().deterministic("", "content_filter")
    assert result.classification == RefusalClass.HARD_REFUSAL
