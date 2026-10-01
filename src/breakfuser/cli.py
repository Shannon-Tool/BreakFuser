"""BreakFuser mock/live readiness CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

import httpx

from breakfuser.adapters import OpenAIChatBackend
from breakfuser.client import BreakFuser
from breakfuser.config import load_settings
from breakfuser.decider import NoulQuestion, OpenRouterDecider
from breakfuser.mock_servers import create_app
from breakfuser.models import ChatMessage


async def _mock_doctor() -> dict[str, Any]:
    transport = httpx.ASGITransport(app=create_app())
    checks: dict[str, Any] = {}
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        health = await client.get("/health")
        health.raise_for_status()
        checks["http_services"] = health.json()["services"]
        decision = await client.post(
            "/decisions",
            json={
                "model": "mock",
                "state": "healthy",
                "questions": {"ok": {"type": "noul", "instructions": "Is this healthy?"}},
            },
        )
        decision.raise_for_status()
        checks["decider_noul"] = decision.json()["answers"]["ok"]["noul"]
        completion = await client.post(
            "/local/v1/chat/completions",
            json={"model": "mock", "messages": [{"role": "user", "content": "health"}]},
        )
        completion.raise_for_status()
        checks["chat_schema"] = "choices" in completion.json() and "usage" in completion.json()
    with BreakFuser(decider="mock", uncensoredmodel="mock", smartmodel="mock") as client:
        response = client.chat.completions.create(messages=[{"role": "user", "content": "Hello!"}])
        checks["exact_api"] = bool(response.choices[0].message.content)
        checks["pipeline_stages"] = len(response.breakfuser.pipeline_stages)
        harvest = client.harvest("Verify one factual statement")
        checks["harvesting"] = bool(harvest.turns)
    checks["status"] = (
        "ok"
        if all((checks["chat_schema"], checks["exact_api"], checks["harvesting"]))
        else "failed"
    )
    return checks


async def _live_doctor() -> dict[str, Any]:
    settings = load_settings()
    local = OpenAIChatBackend(
        settings.endpoints.local or "",
        settings.local_api_key.get_secret_value() if settings.local_api_key else None,
        timeout=settings.transport.timeout_seconds,
        retries=settings.transport.retries,
    )
    smart = OpenAIChatBackend(
        settings.endpoints.smart or "",
        settings.smart_api_key.get_secret_value() if settings.smart_api_key else None,
        timeout=settings.transport.timeout_seconds,
        retries=settings.transport.retries,
    )
    output_limit = min(64, settings.transport.max_output_tokens)
    local_response = await local.complete(
        [ChatMessage(role="user", content="Return OK")],
        settings.models.local,
        max_tokens=output_limit,
    )
    smart_response = await smart.complete(
        [ChatMessage(role="user", content="Return OK")],
        settings.models.smart,
        max_tokens=output_limit,
    )
    if settings.use_decider:
        decider = OpenRouterDecider(
            settings.endpoints.decider or "",
            settings.decider_api_key.get_secret_value() if settings.decider_api_key else None,
            settings.models.decider,
            timeout=settings.transport.timeout_seconds,
            retries=settings.transport.retries,
        )
        decision = await decider.decide(
            "Readiness check", {"ready": NoulQuestion(instructions="Is this a readiness check?")}
        )
        decider_ok = "ready" in decision.answers
    else:
        decider_ok = True
    local_ok = bool(local_response.content)
    smart_ok = bool(smart_response.content)
    return {
        "status": "ok" if local_ok and smart_ok and decider_ok else "failed",
        "local": local_ok,
        "smart": smart_ok,
        "decider": decider_ok if settings.use_decider else "disabled",
        "next": [
            "run mock-equivalent smoke tests",
            "collect traces and metrics",
            "report live failures before tuning",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="breakfuser")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="Check provider readiness")
    mode = doctor.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", action="store_true")
    mode.add_argument("--live", action="store_true")
    serve = subcommands.add_parser("serve", help="Run the OpenAI-compatible fusion API")
    serve.add_argument("--host", help="Listen address; defaults to configured loopback")
    serve.add_argument("--port", type=int, help="Listen port; defaults to configured port")
    mcp = subcommands.add_parser("mcp", help="Run the MCP fusion and skill server")
    mcp.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    mcp.add_argument("--host", help="HTTP listen address; defaults to configured loopback")
    mcp.add_argument("--port", type=int, help="HTTP listen port; defaults to configured port")
    args = parser.parse_args()
    if args.command == "doctor":
        result = asyncio.run(_mock_doctor() if args.mock else _live_doctor())
        print(json.dumps(result, indent=2))
        if result.get("status") != "ok":
            raise SystemExit(1)
    elif args.command == "serve":
        import uvicorn

        from breakfuser.server import create_api_app

        settings = load_settings()
        uvicorn.run(
            create_api_app(settings=settings),
            host=args.host or settings.server.host,
            port=args.port or settings.server.port,
        )
    elif args.command == "mcp":
        from breakfuser.mcp_server import create_mcp_server

        settings = load_settings()
        server = create_mcp_server(settings=settings)
        if args.transport == "stdio":
            server.run(transport="stdio")
        else:
            server.run(
                transport="streamable-http",
                host=args.host or settings.server.host,
                port=args.port or settings.server.port,
            )


if __name__ == "__main__":
    main()
