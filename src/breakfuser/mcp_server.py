"""Official MCP SDK adapter for chat, harvesting, and progressive skills."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from mcp.server import MCPServer

from breakfuser.client import AsyncBreakFuser
from breakfuser.config import HarvestPolicy, Settings
from breakfuser.harvest.models import HarvestResult
from breakfuser.models import ChatCompletion


def create_mcp_server(
    *,
    client: AsyncBreakFuser | None = None,
    settings: Settings | None = None,
) -> MCPServer:
    """Create an MCP server over an injected or configured fusion client."""
    engine = client or AsyncBreakFuser(settings=settings)

    @asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if client is None:
                await engine.close()

    server = MCPServer(
        "BreakFuser",
        instructions=(
            "Use breakfuser_chat for fused responses and breakfuser_harvest for "
            "source-linked evidence. Tool calls returned by chat are proposals for "
            "the host to execute, not observations from BreakFuser."
        ),
        lifespan=lifespan,
    )

    @server.tool()
    async def breakfuser_chat(
        message: str,
        skill_ids: list[str] | None = None,
        harvest_mode: str | None = None,
        harvest_provenance: bool = False,
    ) -> ChatCompletion:
        """Return a complete local-owned fused response with structured metadata."""
        headers = {"x-breakfuser-harvest": harvest_mode} if harvest_mode else None
        result = await engine.chat.completions.create(
            messages=[{"role": "user", "content": message}],
            headers=headers,
            harvest_provenance=harvest_provenance,
            skill_ids=skill_ids,
        )
        return cast(ChatCompletion, result)

    @server.tool()
    async def breakfuser_harvest(
        question: str,
        strategy: str | None = None,
        aggressive: bool = False,
    ) -> HarvestResult:
        """Harvest source-linked evidence without treating it as ground truth."""
        policy = engine.settings.harvest
        if aggressive:
            policy = HarvestPolicy.model_validate(
                {**policy.model_dump(), "aggressiveness": "aggressive"}
            )
        return await engine.harvest(question, policy=policy, strategy=strategy)

    @server.resource("breakfuser://skills")
    def skill_index() -> str:
        """List skill names and short descriptions without loading full bodies."""
        return json.dumps(
            [
                {"name": skill.name, "description": skill.description}
                for skill in engine.orchestrator.skills.skills.values()
            ]
        )

    @server.resource("breakfuser://skills/{name}")
    def skill_body(name: str) -> str:
        """Load one complete skill body after it is selected."""
        return engine.orchestrator.skills.load(name)

    return server
