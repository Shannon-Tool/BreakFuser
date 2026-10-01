"""Sandboxed Stagehand-compatible browser tools with Playwright and mock backends."""

from __future__ import annotations

import asyncio
import base64
import secrets
import time
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from breakfuser.errors import AdapterError, ConfigurationError


class BrowserSnapshot(BaseModel):
    url: str
    accessibility_tree: str


class BrowserResult(BaseModel):
    url: str
    text: str
    data: dict[str, Any] = Field(default_factory=dict)


class Screenshot(BaseModel):
    mime_type: str = "image/png"
    data_base64: str


class Handoff(BaseModel):
    url: str
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class BrowserAdapter(Protocol):
    async def browser_snapshot(self) -> BrowserSnapshot: ...

    async def browser_run(self, action: str, value: str | None = None) -> BrowserResult: ...

    async def browser_screenshot(self) -> Screenshot: ...

    async def browser_handoff(self) -> Handoff: ...


class MockBrowser:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.content = "Empty sandbox page"
        self.handoffs: dict[str, Handoff] = {}

    async def browser_snapshot(self) -> BrowserSnapshot:
        return BrowserSnapshot(
            url=self.url, accessibility_tree=f"RootWebArea\n  text: {self.content}"
        )

    async def browser_run(self, action: str, value: str | None = None) -> BrowserResult:
        await asyncio.sleep(0)
        if action == "navigate":
            if not value or not value.startswith(("https://", "http://")):
                raise ValueError("Sandbox navigation requires an HTTP(S) URL")
            self.url = value
            self.content = f"Mock page for {value}"
        elif action == "extract":
            return BrowserResult(
                url=self.url, text=self.content, data={"extracted": value or self.content}
            )
        elif action in {"act", "observe"}:
            self.content = f"{action}: {value or ''}\n{self.content}"
        else:
            raise ValueError(f"Unsupported browser action: {action}")
        return BrowserResult(url=self.url, text=self.content)

    async def browser_screenshot(self) -> Screenshot:
        payload = base64.b64encode(f"mock-screenshot:{self.url}".encode()).decode()
        return Screenshot(data_base64=payload)

    async def browser_handoff(self) -> Handoff:
        token = secrets.token_urlsafe(24)
        handoff = Handoff(url=f"mock-handoff://{token}", expires_at=time.time() + 900)
        self.handoffs[token] = handoff
        return handoff


class StagehandBrowser:
    """HTTP binding for a configured Stagehand/Browserbase-compatible tool service."""

    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        timeout: float = 20,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not endpoint:
            raise ConfigurationError("Stagehand endpoint is required")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = client

    async def _call(self, operation: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with asyncio.timeout(self.timeout):
            if self._client is not None:
                response = await self._client.post(
                    f"{self.endpoint}/{operation}", json=payload or {}, headers=headers
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.endpoint}/{operation}", json=payload or {}, headers=headers
                    )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise AdapterError("Browser service returned a non-object")
        return data

    async def browser_snapshot(self) -> BrowserSnapshot:
        return BrowserSnapshot.model_validate(await self._call("snapshot"))

    async def browser_run(self, action: str, value: str | None = None) -> BrowserResult:
        return BrowserResult.model_validate(
            await self._call("run", {"action": action, "value": value})
        )

    async def browser_screenshot(self) -> Screenshot:
        return Screenshot.model_validate(await self._call("screenshot"))

    async def browser_handoff(self) -> Handoff:
        return Handoff.model_validate(await self._call("handoff"))


class PlaywrightBrowser:
    """Optional Playwright fallback using navigation events, never fixed page-load sleeps."""

    def __init__(self, playwright_page: Any, timeout: float = 20) -> None:
        self.page = playwright_page
        self.timeout = timeout
        self._manager: Any = None
        self._browser: Any = None

    @classmethod
    async def create(cls, timeout: float = 20) -> PlaywrightBrowser:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise ConfigurationError("Install BreakFuser[browser] for Playwright") from exc
        manager = await async_playwright().start()
        browser = await manager.chromium.launch(headless=True)
        instance = cls(await browser.new_page(), timeout)
        instance._manager = manager
        instance._browser = browser
        return instance

    async def browser_snapshot(self) -> BrowserSnapshot:
        tree = await asyncio.wait_for(self.page.locator("body").aria_snapshot(), self.timeout)
        return BrowserSnapshot(url=self.page.url, accessibility_tree=tree)

    async def browser_run(self, action: str, value: str | None = None) -> BrowserResult:
        async with asyncio.timeout(self.timeout):
            if action == "navigate":
                await self.page.goto(value, wait_until="domcontentloaded")
            elif action == "act":
                await self.page.get_by_text(value or "", exact=False).first.click()
            elif action == "extract":
                text = await self.page.locator("body").inner_text()
                return BrowserResult(url=self.page.url, text=text, data={"extracted": text})
            elif action == "observe":
                text = await self.page.locator("a,button,input").all_inner_texts()
                return BrowserResult(
                    url=self.page.url, text="\n".join(text), data={"actions": text}
                )
            else:
                raise ValueError(f"Unsupported browser action: {action}")
            text = await self.page.locator("body").inner_text()
            return BrowserResult(url=self.page.url, text=text)

    async def browser_screenshot(self) -> Screenshot:
        data = await asyncio.wait_for(self.page.screenshot(), self.timeout)
        return Screenshot(data_base64=base64.b64encode(data).decode())

    async def browser_handoff(self) -> Handoff:
        raise ConfigurationError(
            "Local Playwright handoff requires a configured remote session provider"
        )
