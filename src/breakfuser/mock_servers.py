"""Standalone high-fidelity HTTP mocks for all external provider boundaries."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import TypeAdapter

from breakfuser.adapters import MockLocalBackend, MockSmartBackend
from breakfuser.browser import MockBrowser
from breakfuser.decider import MockDecider, Question
from breakfuser.models import ChatMessage
from breakfuser.privacy import PreemptSanitizer


def create_app() -> FastAPI:
    app = FastAPI(title="BreakFuser mock provider stack")
    local = MockLocalBackend()
    smart = MockSmartBackend()
    decider = MockDecider()
    browser = MockBrowser()
    sanitizer = PreemptSanitizer(os.getenv("BREAKFUSER_SANITIZER_KEY"))

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "services": ["local", "smart", "decider", "browser", "sanitizer"]}

    async def completions(request: Request, backend: Any) -> Any:
        payload = await request.json()
        messages = [ChatMessage.model_validate(message) for message in payload["messages"]]
        model = payload.get("model", "unspecified")
        response = await backend.complete(messages, model, max_tokens=payload.get("max_tokens"))
        data = {
            "id": "mock-completion",
            "object": "chat.completion",
            "created": 0,
            "model": response.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response.content},
                    "finish_reason": response.finish_reason,
                }
            ],
            "usage": response.usage.model_dump(),
        }
        if not payload.get("stream"):
            return data

        async def events() -> AsyncIterator[str]:
            yield f"data: {json.dumps({'id': 'mock-completion', 'object': 'chat.completion.chunk', 'created': 0, 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': response.content}, 'finish_reason': None}]})}\n\n"
            yield f"data: {json.dumps({'id': 'mock-completion', 'object': 'chat.completion.chunk', 'created': 0, 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': response.usage.model_dump()})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/local/v1/chat/completions")
    async def local_completions(request: Request) -> Any:
        return await completions(request, local)

    @app.post("/smart/v1/chat/completions")
    async def smart_completions(request: Request) -> Any:
        return await completions(request, smart)

    @app.post("/decisions")
    async def decisions(request: Request) -> dict[str, Any]:
        payload = await request.json()
        raw_questions = payload["questions"]
        for question in raw_questions.values():
            if question.get("type") == "choice" and "criteria" in question:
                question["options"] = question.pop("criteria")
            elif question.get("type") == "score" and "criteria" in question:
                question["levels"] = question.pop("criteria")
        questions = TypeAdapter(dict[str, Question]).validate_python(raw_questions)
        response = await decider.decide(payload.get("state", ""), questions)
        return {
            "model": payload.get("model", response.model),
            "answers": {key: value.model_dump() for key, value in response.answers.items()},
            "usage": {"input_tokens": response.input_tokens, "output_tokens": 0, "cost": 0},
        }

    @app.post("/browser/snapshot")
    async def snapshot() -> dict[str, Any]:
        return (await browser.browser_snapshot()).model_dump()

    @app.post("/browser/run")
    async def run(request: Request) -> dict[str, Any]:
        payload = await request.json()
        return (await browser.browser_run(payload["action"], payload.get("value"))).model_dump()

    @app.post("/browser/screenshot")
    async def screenshot() -> dict[str, Any]:
        return (await browser.browser_screenshot()).model_dump()

    @app.post("/browser/handoff")
    async def handoff() -> dict[str, Any]:
        return (await browser.browser_handoff()).model_dump()

    @app.post("/sanitize")
    async def sanitize(request: Request) -> dict[str, Any]:
        payload = await request.json()
        result = await sanitizer.sanitize(payload["text"])
        return {"text": result.text, "helper": result.helper, "metadata": result.metadata}

    @app.post("/desanitize")
    async def desanitize(request: Request) -> dict[str, Any]:
        payload = await request.json()
        return {"text": await sanitizer.desanitize(payload["text"], payload["helper"])}

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run BreakFuser mock HTTP providers")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
