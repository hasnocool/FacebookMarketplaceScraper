from __future__ import annotations

import asyncio
import json
import math
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _iso_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 4)


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


class MarketplaceAnalytics:
    """Read-only, thread-isolated analytics over the Marketplace database."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    async def _thread[T](self, work: Callable[[], T]) -> T:
        return await asyncio.to_thread(work)

    async def trends(self, *, days: int) -> dict[str, Any]:
        since = _iso_days_ago(days)

        def work() -> dict[str, Any]:
            with self._connect() as db:
                collection_rows = db.execute(
                    """SELECT date(started_at) AS bucket, COUNT(*) AS runs,
                              COUNT(DISTINCT query) AS queries, SUM(extracted) AS extracted,
                              SUM(normalized) AS normalized, SUM(inserted) AS new_listings,
                              SUM(updated) AS repeat_observations,
                              SUM(price_changes) AS price_changes,
                              AVG(duration_ms) AS avg_duration_ms
                       FROM search_runs WHERE started_at >= ?
                       GROUP BY date(started_at) ORDER BY bucket""",
                    (since,),
                ).fetchall()
                price_rows = db.execute(
                    """WITH ordered AS (
                           SELECT lp.id, lp.listing_id, lp.price_value, lp.currency,
                                  lp.captured_at, l.category,
                                  LAG(lp.price_value) OVER (
                                      PARTITION BY lp.listing_id
                                      ORDER BY lp.captured_at, lp.id
                                  ) AS previous_price
                           FROM listing_prices lp
                           JOIN listings l ON l.listing_id=lp.listing_id
                           WHERE l.restricted=0 AND lp.price_value IS NOT NULL
                       )
                       SELECT date(captured_at) AS bucket, category, currency,
                              COUNT(*) AS price_points,
                              ROUND(AVG(price_value), 2) AS mean_price,
                              SUM(CASE WHEN previous_price > price_value THEN 1 ELSE 0 END) AS drops,
                              AVG(CASE WHEN previous_price > 0
                                  THEN (price_value-previous_price)/previous_price END) AS mean_change_pct
                       FROM ordered WHERE captured_at >= ?
                       GROUP BY date(captured_at), category, currency
                       ORDER BY bucket, category, currency""",
                    (since,),
                ).fetchall()

            collection = []
            for row in collection_rows:
                item = dict(row)
                item["normalization_rate"] = _ratio(item["normalized"], item["extracted"])
                item["discovery_rate"] = _ratio(item["new_listings"], item["normalized"])
                if item["avg_duration_ms"] is not None:
                    item["avg_duration_ms"] = round(item["avg_duration_ms"], 2)
                collection.append(item)

            price_changes = []
            for row in price_rows:
                item = dict(row)
                movement = item["mean_change_pct"]
                item["mean_change_pct"] = round(movement, 4) if movement is not None else None
                item["direction"] = (
                    "stable" if movement is None or abs(movement) < 0.02
                    else "up" if movement > 0
                    else "down"
                )
                price_changes.append(item)
            return {"days": days, "collection": collection, "price_change_observations": price_changes}

        return await self._thread(work)

    async def categories(self, *, days: int, high_score: float) -> list[dict[str, Any]]:
        since = _iso_days_ago(days)

        def work() -> list[dict[str, Any]]:
            with self._connect() as db:
                rows = db.execute(
                    """SELECT category, currency, latest_price_value, deal_score,
                              score_confidence, classification_confidence,
                              classification_source, condition, first_seen, last_seen
                       FROM listings
                       WHERE restricted=0 AND last_seen >= ?
                       ORDER BY category, currency""",
                    (since,),
                ).fetchall()
            groups: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
            for row in rows:
                groups[(str(row["category"]), str(row["currency"] or "unknown"))].append(row)

            result = []
            for (category, currency), items in sorted(groups.items()):
                prices = [float(row["latest_price_value"]) for row in items if row["latest_price_value"] is not None]
                high_count = sum(float(row["deal_score"]) >= high_score for row in items)
                sources = Counter(str(row["classification_source"]) for row in items)
                conditions = Counter(str(row["condition"]) for row in items)
                result.append(
                    {
                        "category": category,
                        "currency": currency,
                        "listings": len(items),
                        "priced_listings": len(prices),
                        "mean_price": round(sum(prices) / len(prices), 2) if prices else None,
                        "p25_price": _percentile(prices, 0.25),
                        "median_price": _percentile(prices, 0.5),
                        "p75_price": _percentile(prices, 0.75),
                        "mean_deal_score": round(sum(float(row["deal_score"]) for row in items) / len(items), 2),
                        "mean_score_confidence": round(sum(float(row["score_confidence"]) for row in items) / len(items), 4),
                        "mean_classification_confidence": round(
                            sum(float(row["classification_confidence"]) for row in items) / len(items), 4
                        ),
                        "high_score_count": high_count,
                        "high_score_rate": _ratio(high_count, len(items)),
                        "new_listings": sum(str(row["first_seen"]) >= since for row in items),
                        "classification_sources": dict(sorted(sources.items())),
                        "conditions": dict(sorted(conditions.items())),
                    }
                )
            return result

        return await self._thread(work)

    async def watchlist_performance(self, *, days: int) -> list[dict[str, Any]]:
        since = _iso_days_ago(days)

        def work() -> list[dict[str, Any]]:
            with self._connect() as db:
                rows = db.execute(
                    """WITH match_stats AS (
                           SELECT wm.watchlist_id, COUNT(*) AS total_matches,
                                  SUM(CASE WHEN wm.first_matched >= ? THEN 1 ELSE 0 END) AS new_matches,
                                  SUM(CASE WHEN wm.last_matched >= ? THEN 1 ELSE 0 END) AS recent_matches,
                                  AVG(wm.latest_score) AS mean_score, MAX(wm.latest_score) AS max_score,
                                  SUM(CASE WHEN l.restricted=0 AND w.target_price IS NOT NULL
                                      AND l.latest_price_value IS NOT NULL
                                      AND l.latest_price_value <= w.target_price
                                      AND l.currency=w.default_currency THEN 1 ELSE 0 END) AS target_hits
                           FROM watchlist_matches wm
                           JOIN watchlists w ON w.id=wm.watchlist_id
                           JOIN listings l ON l.listing_id=wm.listing_id
                           WHERE l.restricted=0 GROUP BY wm.watchlist_id
                       ), notification_stats AS (
                           SELECT ne.watchlist_id, COUNT(*) AS notifications,
                                  SUM(CASE WHEN event_type='target_price' THEN 1 ELSE 0 END) AS target_notifications,
                                  SUM(CASE WHEN event_type='high_score' THEN 1 ELSE 0 END) AS high_score_notifications
                           FROM notification_events ne
                           JOIN listings l ON l.listing_id=ne.listing_id
                           WHERE ne.created_at >= ? AND l.restricted=0
                           GROUP BY ne.watchlist_id
                       )
                       SELECT w.id, w.name, w.query, w.enabled, w.target_price,
                              w.default_currency, w.last_run_at, w.last_success_at,
                              w.last_error_at, w.last_error,
                              COALESCE(m.total_matches,0) AS total_matches,
                              COALESCE(m.new_matches,0) AS new_matches,
                              COALESCE(m.recent_matches,0) AS recent_matches,
                              m.mean_score, m.max_score,
                              COALESCE(m.target_hits,0) AS target_hits,
                              COALESCE(n.notifications,0) AS notifications,
                              COALESCE(n.target_notifications,0) AS target_notifications,
                              COALESCE(n.high_score_notifications,0) AS high_score_notifications
                       FROM watchlists w
                       LEFT JOIN match_stats m ON m.watchlist_id=w.id
                       LEFT JOIN notification_stats n ON n.watchlist_id=w.id
                       ORDER BY notifications DESC, total_matches DESC, w.name""",
                    (since, since, since),
                ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["enabled"] = bool(item["enabled"])
                item["target_hit_rate"] = _ratio(item["target_hits"], item["total_matches"])
                item["notification_rate"] = _ratio(item["notifications"], item["new_matches"])
                for key in ("mean_score", "max_score"):
                    if item[key] is not None:
                        item[key] = round(item[key], 2)
                result.append(item)
            return result

        return await self._thread(work)

    async def opportunities(
        self,
        *,
        days: int,
        limit: int,
        min_score: float,
        min_confidence: float,
    ) -> list[dict[str, Any]]:
        since = _iso_days_ago(days)
        candidate_limit = min(1000, max(200, limit * 10))

        def work() -> list[dict[str, Any]]:
            with self._connect() as db:
                rows = db.execute(
                    """WITH ranked_prices AS (
                           SELECT listing_id, price_value,
                                  ROW_NUMBER() OVER (
                                      PARTITION BY listing_id ORDER BY captured_at DESC, id DESC
                                  ) AS rn
                           FROM listing_prices WHERE price_value IS NOT NULL
                       ), price_summary AS (
                           SELECT listing_id,
                                  MAX(CASE WHEN rn=2 THEN price_value END) AS previous_price
                           FROM ranked_prices WHERE rn <= 2 GROUP BY listing_id
                       ), watch_names AS (
                           SELECT wm.listing_id, GROUP_CONCAT(DISTINCT w.name) AS watchlists,
                                  MAX(wm.latest_score) AS best_watchlist_score
                           FROM watchlist_matches wm JOIN watchlists w ON w.id=wm.watchlist_id
                           GROUP BY wm.listing_id
                       )
                       SELECT l.listing_id, l.title, l.url, l.latest_price_text,
                              l.latest_price_value, l.currency, l.location, l.category,
                              l.condition, l.deal_score, l.score_confidence, l.last_seen,
                              l.score_reasons, p.previous_price, wn.watchlists,
                              wn.best_watchlist_score
                       FROM listings l
                       LEFT JOIN price_summary p ON p.listing_id=l.listing_id
                       LEFT JOIN watch_names wn ON wn.listing_id=l.listing_id
                       WHERE l.restricted=0 AND l.latest_price_value IS NOT NULL
                         AND l.last_seen >= ? AND l.deal_score >= ? AND l.score_confidence >= ?
                       ORDER BY l.deal_score DESC, l.last_seen DESC LIMIT ?""",
                    (since, min_score, min_confidence, candidate_limit),
                ).fetchall()

            result = []
            for row in rows:
                item = dict(row)
                previous = item.pop("previous_price")
                current = float(item["latest_price_value"])
                drop = (float(previous) - current) / float(previous) if previous and previous > 0 else None
                adjusted = 50 + (float(item["deal_score"]) - 50) * float(item["score_confidence"])
                opportunity_score = adjusted + min(10.0, max(0.0, (drop or 0) * 20))
                item["price_drop_pct"] = round(drop, 4) if drop is not None else None
                item["evidence_adjusted_score"] = round(adjusted, 2)
                item["opportunity_score"] = round(opportunity_score, 2)
                item["watchlists"] = item["watchlists"].split(",") if item["watchlists"] else []
                try:
                    item["score_reasons"] = json.loads(item["score_reasons"] or "[]")
                except json.JSONDecodeError:
                    item["score_reasons"] = []
                result.append(item)
            result.sort(key=lambda item: (item["opportunity_score"], item["last_seen"]), reverse=True)
            return result[:limit]

        return await self._thread(work)
