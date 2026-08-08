# src/facebook_marketplace_scraper/daemon.py
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from .browser import MarketplaceBrowser
from .models import SearchSpec, Watchlist
from .service import MarketplaceCollector
from .storage import MarketplaceStore

logger = logging.getLogger(__name__)


def _error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:2000]


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
    await store.daemon_started(os.getpid())
    collector = MarketplaceCollector(
        store=store,
        storage_state_path=storage_state_path,
        headless=headless,
    )
    fatal_error: str | None = None

    try:
        async with MarketplaceBrowser(
            headless=headless,
            storage_state_path=storage_state_path,
        ) as browser:
            while True:
                await store.daemon_heartbeat()
                watchlists = (
                    await store.list_watchlists(enabled_only=True)
                    if once
                    else await store.due_watchlists()
                )
                cycle_errors: list[str] = []

                for watchlist in watchlists:
                    await store.daemon_heartbeat(active_watchlist=watchlist.name)
                    try:
                        await _run_watchlist(collector, browser, watchlist)
                    except Exception as exc:
                        error = _error_text(exc)
                        cycle_errors.append(f"{watchlist.name}: {error}")
                        logger.exception("Watchlist %s failed", watchlist.name)
                        if watchlist.id is not None:
                            await store.mark_watchlist_run(
                                watchlist.id,
                                success=False,
                                error=error,
                            )
                    else:
                        if watchlist.id is not None:
                            await store.mark_watchlist_run(watchlist.id, success=True)
                    finally:
                        await store.daemon_heartbeat(active_watchlist=None)

                cycle_error = "; ".join(cycle_errors)[:2000] or None
                await store.daemon_cycle_completed(
                    success=cycle_error is None,
                    error=cycle_error,
                )
                if once:
                    return
                await asyncio.sleep(max(5, poll_seconds))
    except Exception as exc:
        fatal_error = _error_text(exc)
        logger.exception("Marketplace daemon stopped after a fatal error")
        raise
    finally:
        await store.daemon_stopped(error=fatal_error)


async def _run_watchlist(
    collector: MarketplaceCollector,
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
    await collector.collect(spec, watchlist=watchlist, browser=browser)
