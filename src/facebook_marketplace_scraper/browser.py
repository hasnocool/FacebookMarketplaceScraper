# src/facebook_marketplace_scraper/browser.py
from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import quote_plus

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class MarketplaceBrowser:
    """Async browser lifecycle wrapper with optional user-created session state."""

    def __init__(
        self,
        *,
        headless: bool = True,
        storage_state_path: Path | None = None,
    ) -> None:
        self._headless = headless
        self._storage_state_path = storage_state_path
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "MarketplaceBrowser":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        context_options: dict[str, object] = {
            "locale": "en-CA",
            "viewport": {"width": 1440, "height": 1000},
        }
        state_exists = bool(
            self._storage_state_path
            and await asyncio.to_thread(self._storage_state_path.exists)
        )
        if state_exists:
            context_options["storage_state"] = str(self._storage_state_path)
        self._context = await self._browser.new_context(**context_options)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def open_search_page(self, query: str) -> Page:
        if self._context is None:
            raise RuntimeError("MarketplaceBrowser must be used as an async context manager")
        page = await self._context.new_page()
        url = f"https://www.facebook.com/marketplace/search/?query={quote_plus(query)}"
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return page

    async def open_marketplace(self) -> Page:
        if self._context is None:
            raise RuntimeError("MarketplaceBrowser must be used as an async context manager")
        page = await self._context.new_page()
        await page.goto("https://www.facebook.com/marketplace/", wait_until="domcontentloaded")
        return page

    async def save_storage_state(self, path: Path | None = None) -> Path:
        if self._context is None:
            raise RuntimeError("MarketplaceBrowser must be used as an async context manager")
        target = path or self._storage_state_path
        if target is None:
            raise ValueError("storage state path is required")
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await self._context.storage_state(path=str(target))
        return target
