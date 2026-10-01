from __future__ import annotations

from breakfuser.fusion.outcomes import OutcomeKind, ProviderOutcome
from breakfuser.models import BackendResponse


def test_outcome_distinguishes_filter_length_empty_and_answer() -> None:
    assert (
        ProviderOutcome.from_backend(
            BackendResponse(content="", finish_reason="content_filter", model="m")
        ).kind
        is OutcomeKind.REFUSAL
    )
    assert (
        ProviderOutcome.from_backend(
            BackendResponse(content="partial", finish_reason="length", model="m")
        ).kind
        is OutcomeKind.PARTIAL
    )
    assert (
        ProviderOutcome.from_backend(
            BackendResponse(content="", finish_reason="length", model="m")
        ).kind
        is OutcomeKind.EMPTY_LENGTH
    )
    assert (
        ProviderOutcome.from_backend(BackendResponse(content="answer", model="m")).kind
        is OutcomeKind.ANSWER
    )


def test_empty_stop_and_error_are_distinct() -> None:
    assert (
        ProviderOutcome.from_backend(BackendResponse(content="", model="m")).kind
        is OutcomeKind.EMPTY
    )
    error = ProviderOutcome.from_error("HTTP 403", status_code=403)
    assert error.kind is OutcomeKind.ERROR
    assert error.status_code == 403
    assert not error.retryable
