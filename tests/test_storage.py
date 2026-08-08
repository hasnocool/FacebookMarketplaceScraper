# tests/test_storage.py
import asyncio
from pathlib import Path

from facebook_marketplace_scraper.models import MarketplaceListing, Watchlist
from facebook_marketplace_scraper.storage import MarketplaceStore


def _listing(price: float) -> MarketplaceListing:
    return MarketplaceListing(
        listing_id="100",
        title="ThinkPad T480",
        normalized_title="thinkpad t480",
        fingerprint="f1",
        url="https://www.facebook.com/marketplace/item/100/",
        price_text=f"${price:g}",
        price_value=price,
        currency="CAD",
        source_query="thinkpad",
    )


async def test_store_deduplicates_and_only_records_price_changes(tmp_path: Path) -> None:
    store = MarketplaceStore(tmp_path / "market.sqlite3")
    await store.initialize()

    run1 = await store.start_search_run("thinkpad")
    assert await store.upsert_listing(_listing(300), run_id=run1) == (True, False)

    run2 = await store.start_search_run("thinkpad")
    assert await store.upsert_listing(_listing(300), run_id=run2) == (False, False)

    run3 = await store.start_search_run("thinkpad")
    assert await store.upsert_listing(_listing(250), run_id=run3) == (False, True)

    history = await store.listing_history("100")
    assert [row["price_value"] for row in history] == [250.0, 300.0]


async def test_watchlist_crud(tmp_path: Path) -> None:
    store = MarketplaceStore(tmp_path / "market.sqlite3")
    await store.initialize()
    watch_id = await store.create_watchlist(Watchlist(name="laptops", query="thinkpad"))
    items = await store.list_watchlists()
    assert items[0].id == watch_id
    assert items[0].name == "laptops"
    assert await store.delete_watchlist(watch_id)


async def test_parallel_writes_use_isolated_connections(tmp_path: Path) -> None:
    store = MarketplaceStore(tmp_path / "market.sqlite3")
    await store.initialize()
    run_id = await store.start_search_run("thinkpad")

    first = _listing(300)
    second = _listing(275).model_copy(
        update={
            "listing_id": "101",
            "fingerprint": "f2",
            "url": "https://www.facebook.com/marketplace/item/101/",
        }
    )
    results = await asyncio.gather(
        store.upsert_listing(first, run_id=run_id),
        store.upsert_listing(second, run_id=run_id),
    )
    assert results == [(True, False), (True, False)]
