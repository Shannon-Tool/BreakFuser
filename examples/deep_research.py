"""Request multi-turn research and print per-claim source provenance."""

import asyncio

from BreakFuser import AsyncBreakFuser


async def main() -> None:
    async with AsyncBreakFuser(
        decider="simulation", uncensoredmodel="simulation", smartmodel="simulation"
    ) as client:
        response = await client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "Compare source-aware licensing history and API deprecation terminology.",
                },
                {"role": "assistant", "content": "I will investigate those as separate branches."},
                {"role": "user", "content": "Include provenance and material caveats."},
            ],
            harvest_provenance=True,
        )
        print(response.choices[0].message.content)
        for claim in response.breakfuser.provenance or []:
            print(claim.model_dump())


asyncio.run(main())
