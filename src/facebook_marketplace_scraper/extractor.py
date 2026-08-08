# src/facebook_marketplace_scraper/extractor.py
from __future__ import annotations

import asyncio

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .models import RawListing


class MarketplaceDomExtractor:
    """Extract listing candidates using stable item-link semantics instead of CSS classes."""

    ITEM_LINK = "a[href*='/marketplace/item/']"

    async def extract(self, page: Page, *, max_items: int) -> list[RawListing]:
        try:
            await page.locator(self.ITEM_LINK).first.wait_for(state="attached", timeout=12_000)
        except PlaywrightTimeoutError:
            return []

        await self._scroll_until_stable(page, max_items=max_items)
        links = page.locator(self.ITEM_LINK)
        count = min(await links.count(), max_items * 3)
        found: dict[str, RawListing] = {}

        for index in range(count):
            anchor = links.nth(index)
            href = await anchor.get_attribute("href")
            if not href or "/marketplace/item/" not in href:
                continue

            text = (await anchor.inner_text()).strip()
            aria_label = await anchor.get_attribute("aria-label")
            image = anchor.locator("img").first
            image_url = None
            if await image.count():
                image_url = await image.get_attribute("src")
                if not aria_label:
                    aria_label = await image.get_attribute("alt")

            key = href.split("?", 1)[0]
            found.setdefault(
                key,
                RawListing(
                    url=key,
                    text=text,
                    title_hint=aria_label.strip() if aria_label else None,
                    image_url=image_url,
                ),
            )
            if len(found) >= max_items:
                break

        return list(found.values())[:max_items]

    async def _scroll_until_stable(self, page: Page, *, max_items: int) -> None:
        stable_rounds = 0
        previous_count = 0
        for _ in range(12):
            current_count = await page.locator(self.ITEM_LINK).count()
            if current_count >= max_items:
                break
            if current_count == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
            if stable_rounds >= 3:
                break
            previous_count = current_count
            await page.mouse.wheel(0, 2400)
            await asyncio.sleep(0.45)
