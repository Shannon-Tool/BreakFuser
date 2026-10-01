from __future__ import annotations

import pytest

from breakfuser.context import VirtualFilesystem
from breakfuser.decider import MockDecider
from breakfuser.security import SecurityGuard


@pytest.mark.asyncio
async def test_guard_evaluates_residual_not_encrypted_placeholders() -> None:
    guard = SecurityGuard(MockDecider(), VirtualFilesystem())
    protected = "NAME_0[pm9s] EMAIL_1[qwe9] N2(42.1)"
    assert (await guard.outbound(protected)).allowed
    assert not (await guard.outbound("person@example.com")).allowed
