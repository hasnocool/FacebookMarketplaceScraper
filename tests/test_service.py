# tests/test_service.py
import asyncio

import pytest

from facebook_marketplace_scraper.service import search_marketplace


def test_search_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        asyncio.run(search_marketplace("   "))


def test_search_rejects_invalid_max_items() -> None:
    with pytest.raises(ValueError, match="max_items must be at least 1"):
        asyncio.run(search_marketplace("bike", max_items=0))
