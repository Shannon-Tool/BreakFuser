from __future__ import annotations

import time

import httpx
import pytest

from breakfuser.browser import Handoff, MockBrowser, PlaywrightBrowser, StagehandBrowser
from breakfuser.errors import ConfigurationError
from breakfuser.mock_servers import create_app


@pytest.mark.asyncio
async def test_mock_browser_all_tools_and_expiry() -> None:
    browser = MockBrowser()
    await browser.browser_run("navigate", "https://example.test")
    snapshot = await browser.browser_snapshot()
    assert "RootWebArea" in snapshot.accessibility_tree
    extracted = await browser.browser_run("extract", "fact")
    assert extracted.data["extracted"] == "fact"
    await browser.browser_run("act", "click")
    assert (await browser.browser_run("observe", "buttons")).text
    assert (await browser.browser_screenshot()).data_base64
    handoff = await browser.browser_handoff()
    assert handoff.expires_at - time.time() <= 900
    assert not handoff.expired
    assert Handoff(url="expired", expires_at=time.time() - 1).expired
    with pytest.raises(ValueError):
        await browser.browser_run("navigate", "file:///etc/passwd")
    with pytest.raises(ValueError):
        await browser.browser_run("unsupported")


@pytest.mark.asyncio
async def test_stagehand_http_binding() -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport) as client:
        browser = StagehandBrowser("http://mock/browser", client=client)
        result = await browser.browser_run("navigate", "https://example.test")
        assert result.url == "https://example.test"
        assert (await browser.browser_snapshot()).url == result.url
        assert (await browser.browser_screenshot()).data_base64
        assert (await browser.browser_handoff()).expires_at > time.time()
    with pytest.raises(ConfigurationError):
        StagehandBrowser("")


class _Locator:
    def __init__(self, text="body"):
        self.text = text
        self.first = self

    async def aria_snapshot(self):
        return self.text

    async def inner_text(self):
        return self.text

    async def all_inner_texts(self):
        return [self.text]

    async def click(self):
        return None


class _Page:
    def __init__(self):
        self.url = "about:blank"

    def locator(self, _):
        return _Locator()

    def get_by_text(self, *_, **__):
        return _Locator()

    async def goto(self, url, wait_until):
        self.url = url
        assert wait_until == "domcontentloaded"

    async def screenshot(self):
        return b"png"


@pytest.mark.asyncio
async def test_playwright_fallback_with_fake_page() -> None:
    browser = PlaywrightBrowser(_Page())
    await browser.browser_run("navigate", "https://example.test")
    assert (await browser.browser_snapshot()).accessibility_tree == "body"
    assert (await browser.browser_run("extract")).data["extracted"] == "body"
    assert (await browser.browser_run("observe")).data["actions"] == ["body"]
    await browser.browser_run("act", "click")
    assert (await browser.browser_screenshot()).data_base64 == "cG5n"
    with pytest.raises(ConfigurationError):
        await browser.browser_handoff()
