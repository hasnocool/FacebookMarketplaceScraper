# src/facebook_marketplace_scraper/service.py
from __future__ import annotations

from pathlib import Path

from .browser import MarketplaceBrowser
from .extractor import MarketplaceDomExtractor
from .models import CollectionResult, MarketplaceListing, SearchSpec, Watchlist
from .normalizer import normalize_raw_listing
from .scoring import score_listing
from .storage import MarketplaceStore


class MarketplaceCollector:
    def __init__(
        self,
        *,
        store: MarketplaceStore,
        extractor: MarketplaceDomExtractor | None = None,
        storage_state_path: Path | None = None,
        headless: bool = True,
    ) -> None:
        self.store = store
        self.extractor = extractor or MarketplaceDomExtractor()
        self.storage_state_path = storage_state_path
        self.headless = headless

    async def collect(
        self,
        spec: SearchSpec,
        *,
        watchlist: Watchlist | None = None,
        browser: MarketplaceBrowser | None = None,
    ) -> CollectionResult:
        if not spec.query.strip():
            raise ValueError("query must not be empty")
        await self.store.initialize()
        run_id = await self.store.start_search_run(spec.query)

        if browser is None:
            async with MarketplaceBrowser(
                headless=self.headless,
                storage_state_path=self.storage_state_path,
            ) as owned_browser:
                raw = await self._extract(owned_browser, spec)
        else:
            raw = await self._extract(browser, spec)

        normalized: list[MarketplaceListing] = []
        for item in raw:
            listing = normalize_raw_listing(
                item,
                query=spec.query,
                default_currency=spec.default_currency,
            )
            if spec.min_price is not None and (
                listing.price_value is None or listing.price_value < spec.min_price
            ):
                continue
            if spec.max_price is not None and (
                listing.price_value is None or listing.price_value > spec.max_price
            ):
                continue
            normalized.append(listing)

        inserted = 0
        updated = 0
        price_changes = 0
        scored = []
        for listing in normalized:
            was_inserted, price_changed = await self.store.upsert_listing(listing, run_id=run_id)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
            price_changes += int(price_changed)
            stats = await self.store.price_stats(listing)
            item_score = score_listing(listing, stats, watchlist=watchlist)
            await self.store.update_score(
                listing.listing_id,
                item_score.deal_score,
                item_score.confidence,
            )
            if watchlist and watchlist.id is not None:
                await self.store.record_watchlist_match(
                    watchlist.id,
                    listing.listing_id,
                    item_score.deal_score,
                )
            scored.append(item_score)

        scored.sort(key=lambda item: item.deal_score, reverse=True)
        await self.store.finish_search_run(
            run_id,
            extracted=len(raw),
            normalized=len(normalized),
            inserted=inserted,
            updated=updated,
            price_changes=price_changes,
        )
        return CollectionResult(
            query=spec.query,
            run_id=run_id,
            extracted=len(raw),
            normalized=len(normalized),
            inserted=inserted,
            updated=updated,
            price_changes=price_changes,
            listings=scored,
        )

    async def _extract(self, browser: MarketplaceBrowser, spec: SearchSpec):
        page = await browser.open_search_page(spec.query)
        try:
            return await self.extractor.extract(page, max_items=spec.max_items)
        finally:
            await page.close()
