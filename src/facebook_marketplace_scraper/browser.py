# src/facebook_marketplace_scraper/browser.py
from __future__ import annotations

from urllib.parse import quote_plus

from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright


class MarketplaceBrowser:
    """Async browser lifecycle wrapper for Marketplace research."""

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> "MarketplaceBrowser":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    async def open_search(self, query: str) -> str:
        """Open a Marketplace search and return the resulting page title.

        Extraction is intentionally kept separate because Facebook's DOM changes
        frequently and should be implemented behind a tested adapter.
        """
        if self._context is None:
            raise RuntimeError("MarketplaceBrowser must be used as an async context manager")

        page = await self._context.new_page()
        url = f"https://www.facebook.com/marketplace/search/?query={quote_plus(query)}"
        await page.goto(url, wait_until="domcontentloaded")
        return await page.title()
