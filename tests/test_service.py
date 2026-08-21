# tests/test_service.py
from pathlib import Path

from facebook_marketplace_scraper.models import RawListing, SearchSpec
from facebook_marketplace_scraper.service import MarketplaceCollector
from facebook_marketplace_scraper.storage import MarketplaceStore


class FakePage:
    async def close(self) -> None:
        return None


class FakeBrowser:
    def __init__(self) -> None:
        self.locations: list[str] = []

    async def set_marketplace_location(self, location: str) -> None:
        self.locations.append(location)

    async def open_search_page(self, query: str) -> FakePage:
        assert query == "thinkpad"
        return FakePage()


class FakeExtractor:
    async def extract(self, page: FakePage, *, max_items: int) -> list[RawListing]:
        return [
            RawListing(
                url="/marketplace/item/42/",
                text="$200\nThinkPad T480\nVictoria, BC",
            )
        ][:max_items]


async def test_collection_pipeline(tmp_path: Path) -> None:
    store = MarketplaceStore(tmp_path / "market.sqlite3")
    collector = MarketplaceCollector(store=store, extractor=FakeExtractor())
    browser = FakeBrowser()
    result = await collector.collect(SearchSpec(query="thinkpad"), browser=browser)
    assert result.extracted == 1
    assert result.normalized == 1
    assert result.inserted == 1
    assert result.listings[0].listing.listing_id == "42"
    assert browser.locations == list(MarketplaceCollector.SEARCH_LOCATIONS)
