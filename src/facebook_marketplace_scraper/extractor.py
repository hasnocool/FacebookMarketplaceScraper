# src/facebook_marketplace_scraper/extractor.py
from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .models import RawListing


CardRecord = dict[str, Any]


def records_to_raw_listings(records: list[CardRecord], *, max_items: int) -> list[RawListing]:
    """Convert browser snapshots or JSON fixtures through the same extraction contract."""
    found: dict[str, RawListing] = {}
    for record in records:
        href = str(record.get("href") or "")
        if "/marketplace/item/" not in href:
            continue
        key = href.split("?", 1)[0]
        aria_label = str(record.get("aria_label") or "").strip() or None
        image_alt = str(record.get("image_alt") or "").strip() or None
        found.setdefault(
            key,
            RawListing(
                url=key,
                text=str(record.get("text") or "").strip(),
                title_hint=aria_label or image_alt,
                image_url=str(record.get("image_url") or "").strip() or None,
            ),
        )
        if len(found) >= max_items:
            break
    return list(found.values())[:max_items]


class MarketplaceDomExtractor:
    """Extract listing candidates using item-link semantics instead of generated CSS classes."""

    ITEM_LINK = "a[href*='/marketplace/item/']"

    async def extract(self, page: Page, *, max_items: int) -> list[RawListing]:
        records = await self.snapshot(page, max_items=max_items)
        return records_to_raw_listings(records, max_items=max_items)

    async def snapshot(self, page: Page, *, max_items: int) -> list[CardRecord]:
        try:
            await page.locator(self.ITEM_LINK).first.wait_for(state="attached", timeout=12_000)
        except PlaywrightTimeoutError:
            return []

        await self._scroll_until_stable(page, max_items=max_items)
        links = page.locator(self.ITEM_LINK)
        limit = max_items * 3
        return await links.evaluate_all(
            """(nodes, limit) => nodes.slice(0, limit).map(anchor => {
                const image = anchor.querySelector('img');
                return {
                    href: anchor.getAttribute('href'),
                    text: anchor.innerText || '',
                    aria_label: anchor.getAttribute('aria-label'),
                    image_url: image ? image.getAttribute('src') : null,
                    image_alt: image ? image.getAttribute('alt') : null
                };
            })""",
            limit,
        )

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
