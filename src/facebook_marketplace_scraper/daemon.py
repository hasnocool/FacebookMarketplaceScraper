# src/facebook_marketplace_scraper/daemon.py
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from .browser import MarketplaceBrowser
from .models import SearchSpec, Watchlist
from .service import MarketplaceCollector
from .storage import MarketplaceStore

logger = logging.getLogger(__name__)


async def run_daemon(
    *,
    db_path: Path,
    storage_state_path: Path | None,
    poll_seconds: int = 30,
    headless: bool = True,
    once: bool = False,
) -> None:
    store = MarketplaceStore(db_path)
    await store.initialize()
    collector = MarketplaceCollector(
        store=store,
        storage_state_path=storage_state_path,
        headless=headless,
    )

    async with MarketplaceBrowser(
        headless=headless,
        storage_state_path=storage_state_path,
    ) as browser:
        while True:
            watchlists = (
                await store.list_watchlists(enabled_only=True)
                if once
                else await store.due_watchlists()
            )
            for watchlist in watchlists:
                try:
                    await _run_watchlist(collector, store, browser, watchlist)
                except Exception:
                    logger.exception("Watchlist %s failed", watchlist.name)
            if once:
                return
            await asyncio.sleep(max(5, poll_seconds))


async def _run_watchlist(
    collector: MarketplaceCollector,
    store: MarketplaceStore,
    browser: MarketplaceBrowser,
    watchlist: Watchlist,
) -> None:
    spec = SearchSpec(
        query=watchlist.query,
        max_items=watchlist.max_items,
        min_price=watchlist.min_price,
        max_price=watchlist.max_price,
        default_currency=watchlist.default_currency,
    )
    try:
        await collector.collect(spec, watchlist=watchlist, browser=browser)
    finally:
        if watchlist.id is not None:
            await store.mark_watchlist_run(watchlist.id)
