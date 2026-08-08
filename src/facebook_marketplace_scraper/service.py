# src/facebook_marketplace_scraper/service.py
from __future__ import annotations

from dataclasses import dataclass

from .browser import MarketplaceBrowser


@dataclass(slots=True, frozen=True)
class SearchResult:
    query: str
    page_title: str


async def search_marketplace(
    query: str,
    *,
    max_items: int = 20,
    headless: bool = True,
) -> SearchResult:
    """Run one Marketplace search without blocking the event loop."""
    if not query.strip():
        raise ValueError("query must not be empty")
    if max_items < 1:
        raise ValueError("max_items must be at least 1")

    async with MarketplaceBrowser(headless=headless) as browser:
        page_title = await browser.open_search(query)

    return SearchResult(query=query, page_title=page_title)
