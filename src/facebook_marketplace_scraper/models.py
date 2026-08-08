# src/facebook_marketplace_scraper/models.py
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl


class MarketplaceListing(BaseModel):
    """Normalized Marketplace listing."""

    listing_id: str
    title: str
    url: HttpUrl
    price_text: str | None = None
    price_value: float | None = None
    currency: str | None = None
    location: str | None = None
    image_url: HttpUrl | None = None
    seller_name: str | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
