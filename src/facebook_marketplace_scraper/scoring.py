# src/facebook_marketplace_scraper/scoring.py
from __future__ import annotations

from .models import MarketplaceListing, PriceStats, ScoredListing, Watchlist


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_listing(
    listing: MarketplaceListing,
    stats: PriceStats,
    *,
    watchlist: Watchlist | None = None,
) -> ScoredListing:
    price = listing.price_value
    reasons: list[str] = []
    if price is None:
        return ScoredListing(
            listing=listing,
            deal_score=0.0,
            confidence=0.0,
            price_stats=stats,
            reasons=["No numeric price available"],
        )

    score = 50.0
    if stats.median_price and stats.median_price > 0:
        discount = (stats.median_price - price) / stats.median_price
        score += _clamp(discount * 100.0, -50.0, 40.0)
        if discount > 0:
            reasons.append(f"{discount:.0%} below comparable median")
        elif discount < 0:
            reasons.append(f"{-discount:.0%} above comparable median")
    else:
        score = 40.0
        reasons.append("Limited comparable-price history")

    if stats.previous_price and stats.previous_price > price:
        drop = (stats.previous_price - price) / stats.previous_price
        score += _clamp(drop * 50.0, 0.0, 15.0)
        reasons.append(f"Price dropped {drop:.0%} since previous observation")

    if watchlist and watchlist.target_price is not None and price <= watchlist.target_price:
        score += 10.0
        reasons.append("At or below watchlist target price")

    confidence = _clamp(stats.sample_size / 8.0, 0.1, 1.0)
    if stats.sample_size < 3:
        reasons.append("Low comparable sample size")

    return ScoredListing(
        listing=listing,
        deal_score=round(_clamp(score, 0.0, 100.0), 1),
        confidence=round(confidence, 2),
        price_stats=stats,
        reasons=reasons,
    )
