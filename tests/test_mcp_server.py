from __future__ import annotations

import os
import sys

import pytest
from mcp import Client, StdioServerParameters

from BreakFuser import AsyncBreakFuser
from breakfuser.mcp_server import create_mcp_server


@pytest.mark.asyncio
async def test_mcp_tools_and_progressive_skill_resources(settings) -> None:
    engine = AsyncBreakFuser(settings=settings)
    server = create_mcp_server(client=engine)

    async with Client(server) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "breakfuser_chat",
            "breakfuser_harvest",
        }
        chat = await client.call_tool(
            "breakfuser_chat",
            {
                "message": "Research an MCP integration fact",
                "skill_ids": ["research"],
                "harvest_provenance": True,
            },
        )
        assert chat.structured_content is not None
        assert chat.structured_content["choices"][0]["message"]["content"]
        assert chat.structured_content["breakfuser"]["fusion"]["composition_mode"] == (
            "targeted_synthesis"
        )
        harvest = await client.call_tool(
            "breakfuser_harvest",
            {"question": "Recover one MCP fact", "strategy": "direct"},
        )
        assert harvest.structured_content is not None
        assert harvest.structured_content["facts"]
        resources = await client.list_resources()
        assert str(resources.resources[0].uri) == "breakfuser://skills"
        templates = await client.list_resource_templates()
        assert str(templates.resource_templates[0].uri_template) == ("breakfuser://skills/{name}")
        index = await client.read_resource("breakfuser://skills")
        assert "research" in index.contents[0].text
        body = await client.read_resource("breakfuser://skills/research")
        assert "Plan evidence-led multi-turn research" in body.contents[0].text

    await engine.close()


@pytest.mark.asyncio
async def test_real_stdio_mcp_subprocess() -> None:
    environment = os.environ.copy()
    environment["BREAKFUSER_MODE"] = "mock"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "breakfuser.cli", "mcp", "--transport", "stdio"],
        env=environment,
    )

    async with Client(parameters) as client:
        tools = await client.list_tools()
        assert "breakfuser_chat" in {tool.name for tool in tools.tools}
        response = await client.call_tool("breakfuser_chat", {"message": "Hello over MCP stdio"})
        assert response.structured_content is not None
        assert response.structured_content["choices"][0]["message"]["content"]
