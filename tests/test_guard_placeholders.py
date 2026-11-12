from __future__ import annotations

import pytest

from breakfuser.context import VirtualFilesystem
from breakfuser.decider import MockDecider
from breakfuser.privacy import PreemptSanitizer
from breakfuser.security import SecurityGuard


@pytest.mark.asyncio
async def test_guard_rejects_literal_placeholder_shaped_pii() -> None:
    guard = SecurityGuard(MockDecider(), VirtualFilesystem())

    result = await guard.outbound("N0(alice@example.com)")

    assert not result.allowed
    assert result.reasons == ["residual-pii"]


@pytest.mark.asyncio
async def test_guard_accepts_authentic_preempt_tokens() -> None:
    guard = SecurityGuard(MockDecider(), VirtualFilesystem())
    protected = await PreemptSanitizer("key", seed=4).sanitize(
        "Alice age 42; contact alice@example.com"
    )

    assert protected.metadata["protected_tokens"]
    result = await guard.outbound(
        protected.text, protected_tokens=protected.metadata["protected_tokens"]
    )
    assert result.allowed
