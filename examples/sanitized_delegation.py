"""Demonstrate keyed local sanitization and explicit-atom harvesting.

Uses configured providers and defaults to local development services without live configuration.
Use a secret-managed key and review recognizer limitations in real deployments.
"""

import asyncio

from BreakFuser import AsyncBreakFuser, Atom
from breakfuser.privacy import PreemptSanitizer


async def main() -> None:
    sanitizer = PreemptSanitizer("example-only-key")
    protected = await sanitizer.sanitize("Alice is 42; contact alice@example.com")
    print("Remote-safe text:", protected.text)
    async with AsyncBreakFuser(sanitizer=sanitizer) as client:
        result = await client.harvest(
            "Provide the requested account-safe fact",
            atoms=[Atom(id="account", description="Alice is 42")],
            strategy="direct",
        )
        print(result.answer)
        print("Provenance:", result.provenance[0].model_dump())


asyncio.run(main())
