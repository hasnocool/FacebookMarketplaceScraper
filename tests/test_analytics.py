import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from facebook_marketplace_scraper.analytics import MarketplaceAnalytics
from facebook_marketplace_scraper.dashboard import create_dashboard_app
from facebook_marketplace_scraper.models import MarketplaceListing, NotificationEvent, Watchlist
from facebook_marketplace_scraper.storage import MarketplaceStore


def _listing(
    listing_id: str,
    price: float,
    *,
    currency: str = "CAD",
    restricted: bool = False,
) -> MarketplaceListing:
    return MarketplaceListing(
        listing_id=listing_id,
        title=f"ThinkPad {listing_id}",
        normalized_title=f"thinkpad {listing_id}",
        fingerprint=f"f-{listing_id}",
        url=f"https://www.facebook.com/marketplace/item/{listing_id}/",
        price_text=f"{currency} {price:g}",
        price_value=price,
        currency=currency,
        location="Victoria, BC",
        category="computers",
        condition="good",
        classification_confidence=0.8,
        restricted=restricted,
        source_query="thinkpad",
    )


async def _seed(path: Path) -> None:
    store = MarketplaceStore(path)
    await store.initialize()
    run_id = await store.start_search_run("thinkpad")
    for item in (_listing("1", 200), _listing("2", 100), _listing("3", 300), _listing("4", 999, currency="USD")):
        await store.upsert_listing(item, run_id=run_id)
    await store.upsert_listing(_listing("1", 150), run_id=run_id)
    await store.update_score("1", 90, 0.5, ["below comparable median"])
    restricted = _listing("5", 1, restricted=True)
    await store.upsert_listing(restricted, run_id=run_id)
    await store.update_score("5", 100, 1, ["must remain hidden"])
    watchlist_id = await store.create_watchlist(
        Watchlist(name="Laptops", query="thinkpad", target_price=180)
    )
    await store.record_watchlist_match(watchlist_id, "1", 90)
    await store.record_notification(
        NotificationEvent(
            listing_id="1",
            watchlist_id=watchlist_id,
            event_type="target_price",
            dedupe_key="analytics-target",
            score=90,
            payload={"title": "ThinkPad 1"},
        )
    )
    await store.finish_search_run(
        run_id,
        extracted=5,
        normalized=5,
        inserted=5,
        updated=1,
        price_changes=1,
        duration_ms=100,
    )


async def test_analytics_metrics_and_opportunity_ranking(tmp_path: Path) -> None:
    path = tmp_path / "market.sqlite3"
    await _seed(path)
    analytics = MarketplaceAnalytics(path)

    trends = await analytics.trends(days=30)
    assert trends["collection"][0]["normalization_rate"] == 1
    assert trends["collection"][0]["discovery_rate"] == 1
    assert trends["price_change_observations"][0]["drops"] == 1

    categories = await analytics.categories(days=30, high_score=75)
    cad = next(item for item in categories if item["currency"] == "CAD")
    usd = next(item for item in categories if item["currency"] == "USD")
    assert cad["listings"] == 3
    assert cad["median_price"] == 150
    assert cad["p25_price"] == 125
    assert usd["listings"] == 1

    watchlists = await analytics.watchlist_performance(days=30)
    assert watchlists[0]["target_hits"] == 1
    assert watchlists[0]["target_hit_rate"] == 1
    assert watchlists[0]["notifications"] == 1

    opportunities = await analytics.opportunities(
        days=30,
        limit=10,
        min_score=75,
        min_confidence=0.25,
    )
    assert [item["listing_id"] for item in opportunities] == ["1"]
    assert opportunities[0]["price_drop_pct"] == 0.25
    assert opportunities[0]["evidence_adjusted_score"] == 70
    assert opportunities[0]["opportunity_score"] == 75
    assert opportunities[0]["score_reasons"] == ["below comparable median"]


def test_analytics_api_and_empty_state(tmp_path: Path) -> None:
    populated = tmp_path / "market.sqlite3"
    asyncio.run(_seed(populated))
    with TestClient(create_dashboard_app(populated)) as client:
        assert client.get("/analytics").status_code == 200
        assert "Market Analytics" in client.get("/analytics").text
        assert client.get("/api/analytics/trends?days=30").status_code == 200
        assert client.get("/api/analytics/categories?days=30").json()
        assert client.get("/api/analytics/watchlists?days=30").json()[0]["name"] == "Laptops"
        assert client.get("/api/analytics/opportunities?days=30").status_code == 200
        assert client.get("/api/analytics/trends?days=0").status_code == 422

    empty = tmp_path / "empty.sqlite3"
    with TestClient(create_dashboard_app(empty)) as client:
        assert client.get("/api/analytics/trends").json()["collection"] == []
        assert client.get("/api/analytics/categories").json() == []
        assert client.get("/api/analytics/watchlists").json() == []
        assert client.get("/api/analytics/opportunities").json() == []
