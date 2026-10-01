"""OpenAI-compatible HTTP serving over the complete async fusion pipeline."""

from __future__ import annotations

import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from breakfuser.client import AsyncBreakFuser
from breakfuser.config import Settings
from breakfuser.errors import (
    AdapterError,
    BreakFuserError,
    BudgetExhausted,
    ConfigurationError,
    HarvestStopped,
    SecurityBlocked,
    VerificationError,
)
from breakfuser.models import ChatCompletion, ChatCompletionChunk, ChatMessage, ToolDefinition


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = False
    max_tokens: int | None = Field(default=None, gt=0)
    max_completion_tokens: int | None = Field(default=None, gt=0)
    temperature: float = Field(default=0, ge=0, le=2)
    harvest_provenance: bool = False
    tools: list[ToolDefinition] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    skill_ids: list[str] | None = None


class _APIError(Exception):
    def __init__(self, status: int, message: str, error_type: str, code: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.error_type = error_type
        self.code = code


def _error_response(status: int, message: str, error_type: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "message": message,
                "type": error_type,
                "param": None,
                "code": code,
            }
        },
    )


def create_api_app(
    *,
    client: AsyncBreakFuser | None = None,
    settings: Settings | None = None,
    api_key: str | None = None,
) -> FastAPI:
    """Create a server over an injected or configured shared fusion client."""
    engine = client or AsyncBreakFuser(settings=settings)
    configured_key = api_key
    if configured_key is None and engine.settings.server.api_key is not None:
        configured_key = engine.settings.server.api_key.get_secret_value()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if client is None:
                await engine.close()

    app = FastAPI(title="BreakFuser OpenAI-compatible fusion API", lifespan=lifespan)
    app.state.breakfuser = engine

    def authorize(request: Request) -> None:
        if not configured_key:
            return
        scheme, separator, credential = request.headers.get("authorization", "").partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not secrets.compare_digest(credential, configured_key)
        ):
            raise _APIError(
                401,
                "Invalid or missing API key.",
                "authentication_error",
                "invalid_api_key",
            )

    @app.exception_handler(_APIError)
    async def api_error(_: Request, exc: _APIError) -> JSONResponse:
        return _error_response(exc.status, exc.message, exc.error_type, exc.code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error_response(
            400,
            "Invalid chat completion request.",
            "invalid_request_error",
            "invalid_request",
        )

    @app.exception_handler(ValueError)
    async def invalid_selection(_: Request, __: ValueError) -> JSONResponse:
        return _error_response(
            400,
            "Invalid tool, skill, or harvest selection.",
            "invalid_request_error",
            "invalid_selection",
        )

    @app.exception_handler(BreakFuserError)
    async def pipeline_error(_: Request, exc: BreakFuserError) -> JSONResponse:
        if isinstance(exc, BudgetExhausted):
            status, message, error_type, code = (
                429,
                "The configured fusion budget is exhausted.",
                "rate_limit_error",
                "budget_exhausted",
            )
        elif isinstance(exc, SecurityBlocked):
            status, message, error_type, code = (
                403,
                "A configured privacy or tool-security guard blocked the request.",
                "permission_error",
                "security_blocked",
            )
        elif isinstance(exc, AdapterError | VerificationError):
            status, message, error_type, code = (
                502,
                "An upstream model or verification stage failed.",
                "upstream_error",
                "fusion_upstream_failed",
            )
        elif isinstance(exc, HarvestStopped):
            status, message, error_type, code = (
                400,
                "Harvesting stopped at a configured policy boundary.",
                "invalid_request_error",
                "harvest_stopped",
            )
        elif isinstance(exc, ConfigurationError):
            status, message, error_type, code = (
                500,
                "The fusion server is not configured correctly.",
                "server_error",
                "configuration_error",
            )
        else:
            status, message, error_type, code = (
                500,
                "The fusion request failed.",
                "server_error",
                "fusion_failed",
            )
        return _error_response(status, message, error_type, code)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "pipeline": "local_owned_fusion"}

    @app.get("/v1/models")
    async def models(request: Request) -> dict[str, Any]:
        authorize(request)
        return {
            "object": "list",
            "data": [
                {
                    "id": engine.settings.models.local,
                    "object": "model",
                    "created": 0,
                    "owned_by": "breakfuser",
                }
            ],
        }

    @app.post("/v1/chat/completions")
    async def completions(payload: ChatCompletionRequest, request: Request) -> Any:
        authorize(request)
        headers: dict[str, str] = {}
        harvest_mode = request.headers.get("x-breakfuser-harvest")
        if harvest_mode:
            headers["x-breakfuser-harvest"] = harvest_mode
        provenance_header = request.headers.get("x-breakfuser-harvest-provenance", "").lower() in {
            "1",
            "true",
            "yes",
        }
        result = await engine.chat.completions.create(
            messages=payload.messages,
            stream=payload.stream,
            headers=headers,
            harvest_provenance=payload.harvest_provenance or provenance_header,
            max_tokens=payload.max_tokens or payload.max_completion_tokens,
            temperature=payload.temperature,
            tools=(
                [tool.model_dump(mode="json") for tool in payload.tools]
                if payload.tools is not None
                else None
            ),
            tool_choice=payload.tool_choice,
            response_format=payload.response_format,
            skill_ids=payload.skill_ids,
        )
        if payload.stream:
            stream = cast(AsyncIterator[ChatCompletionChunk], result)

            async def events() -> AsyncIterator[str]:
                async for chunk in stream:
                    data = chunk.model_dump(mode="json", exclude_none=True)
                    yield f"data: {json.dumps(data, separators=(',', ':'))}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                events(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache"},
            )
        completion = cast(ChatCompletion, result)
        return JSONResponse(completion.model_dump(mode="json"))

    return app
