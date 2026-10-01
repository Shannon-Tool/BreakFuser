"""Strictly allowlisted loopback HTTP execution for authorized black-box tests."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from breakfuser.errors import AdapterError


class SandboxProposal(BaseModel):
    method: Literal["GET", "POST"]
    url: str
    json_body: dict[str, Any] | None = None


class SandboxReplay(BaseModel):
    executed_by: Literal["allowlisted-sandbox-executor"] = "allowlisted-sandbox-executor"
    status_code: int
    response: dict[str, Any]


class SandboxExecutor:
    def __init__(self, client: httpx.AsyncClient | None = None, timeout: float = 10) -> None:
        self.client = client
        self.timeout = timeout

    @staticmethod
    def _validate(url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme != "http":
            raise ValueError("Sandbox requests require plain HTTP loopback")
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Sandbox target must be an exact loopback host")
        if parsed.port is None:
            raise ValueError("Sandbox target requires an explicit port")
        if parsed.username or parsed.password:
            raise ValueError("Sandbox URL must not contain credentials")

    async def execute(self, proposal: SandboxProposal) -> SandboxReplay:
        self._validate(proposal.url)
        if self.client is not None:
            response = await self.client.request(
                proposal.method, proposal.url, json=proposal.json_body, timeout=self.timeout
            )
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    proposal.method, proposal.url, json=proposal.json_body
                )
        try:
            data = response.json()
        except ValueError as exc:
            raise AdapterError("Sandbox returned a non-JSON response") from exc
        if not isinstance(data, dict):
            raise AdapterError("Sandbox returned a non-object JSON response")
        return SandboxReplay(status_code=response.status_code, response=data)
