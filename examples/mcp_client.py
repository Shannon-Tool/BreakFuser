"""Use BreakFuser through the official MCP client and a real stdio subprocess."""

import asyncio
import os
import sys

from mcp import Client, StdioServerParameters


async def main() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "breakfuser.cli", "mcp"],
        env=os.environ.copy(),
    )
    async with Client(parameters) as client:
        tools = await client.list_tools()
        print([tool.name for tool in tools.tools])
        result = await client.call_tool(
            "breakfuser_chat",
            {"message": "Hello from an MCP harness", "skill_ids": ["research"]},
        )
        print(result.structured_content["choices"][0]["message"]["content"])


if __name__ == "__main__":
    asyncio.run(main())
