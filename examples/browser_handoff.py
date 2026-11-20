"""Inspect a browser session and request an expiring handoff.

Uses configured providers and defaults to local development services without live configuration.
A usable remote handoff link requires a configured remote browser provider.
"""

import asyncio
from datetime import UTC, datetime

from BreakFuser import AsyncBreakFuser


async def main() -> None:
    async with AsyncBreakFuser() as client:
        browser = client.orchestrator.browser
        await browser.browser_run("navigate", "https://example.com")
        print((await browser.browser_snapshot()).accessibility_tree)
        handoff = await browser.browser_handoff()
        print("Expiring handoff:", handoff.url)
        print("Expires:", datetime.fromtimestamp(handoff.expires_at, UTC).isoformat())


asyncio.run(main())
