# src/facebook_marketplace_scraper/models.py
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(UTC)


class RawListing(BaseModel):
    """DOM-derived listing candidate before normalization."""

    url: str
    text: str = ""
    title_hint: str | None = None
    price_text: str | None = None
    location_hint: str | None = None
    image_url: str | None = None


class SearchSpec(BaseModel):
    query: str
    max_items: int = Field(default=20, ge=1, le=500)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    default_currency: str = "CAD"


class MarketplaceListing(BaseModel):
    """Normalized Marketplace listing persisted by the pipeline."""

    listing_id: str
    title: str
    normalized_title: str
    fingerprint: str
    url: HttpUrl
    price_text: str | None = None
    price_value: float | None = None
    currency: str | None = None
    location: str | None = None
    image_url: HttpUrl | None = None
    seller_name: str | None = None
    source_query: str
    captured_at: datetime = Field(default_factory=utc_now)


class PriceStats(BaseModel):
    sample_size: int = 0
    median_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    previous_price: float | None = None


class ScoredListing(BaseModel):
    listing: MarketplaceListing
    deal_score: float
    confidence: float
    price_stats: PriceStats
    reasons: list[str] = Field(default_factory=list)


class Watchlist(BaseModel):
    id: int | None = None
    name: str
    query: str
    min_price: float | None = None
    max_price: float | None = None
    target_price: float | None = None
    max_items: int = Field(default=50, ge=1, le=500)
    default_currency: str = "CAD"
    interval_seconds: int = Field(default=1800, ge=60)
    enabled: bool = True
    last_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class CollectionResult(BaseModel):
    query: str
    run_id: int
    extracted: int
    normalized: int
    inserted: int
    updated: int
    price_changes: int
    listings: list[ScoredListing] = Field(default_factory=list)
