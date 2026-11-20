"""Start a background subagent, enqueue steering, and await completion.

Uses configured providers and defaults to local development services without live configuration.
"""

import asyncio

from BreakFuser import AsyncBreakFuser


async def main() -> None:
    async with AsyncBreakFuser() as client:
        tasks = client.orchestrator.tasks
        task_id = await tasks.start_async_task("Investigate independent evidence")
        await tasks.update_async_task(task_id, "Add a verification pass", "enqueue")
        completed = await client.orchestrator.wait_for_background(timeout=5)
        print(completed.state, completed.result)


asyncio.run(main())
