---
title: Market Analytics Phase 1 and 2
status: frozen
version: 1.0
---

# Market Analytics Phase 1 and 2

## Goal

Turn collected Marketplace observations into bounded, explainable decision support without claiming sales, inventory, or conversion data that Facebook does not expose.

## Scope

- Daily collection and observed price-change trends for a configurable 1–365 day window.
- Current category/currency price distribution and scoring summaries.
- Watchlist match, target-price, notification, and health metrics.
- Ranked recent opportunities using confidence-adjusted deal scores and observed price drops.
- Read-only FastAPI endpoints and a dependency-free analytics dashboard.

## API contract

- `GET /api/analytics/trends?days=30`
- `GET /api/analytics/categories?days=30&high_score=75`
- `GET /api/analytics/watchlists?days=30`
- `GET /api/analytics/opportunities?days=30&limit=25&min_score=60&min_confidence=0.25`

All endpoints exclude safety-restricted listings. Category statistics remain partitioned by currency. Parameters are bounded by FastAPI validation.

## Decision formulas

- `normalization_rate = normalized / extracted`
- `discovery_rate = inserted / normalized`
- `target_hit_rate = current target-price hits / total matches`
- `notification_rate = notifications in window / new matches in window`
- `evidence_adjusted_score = 50 + (deal_score - 50) * score_confidence`
- Opportunity ranking adds up to 10 points for an observed price drop, then sorts by adjusted score and recency.

Rates with a zero denominator are `null`. Percentiles use linear interpolation over sorted numeric prices. Trend direction is up/down only when mean observed price movement exceeds ±2%; otherwise it is stable.

## Data limitations

- Price history records initial prices and changes, not daily inventory snapshots.
- Search omissions do not prove a listing sold.
- Notifications measure generated events, not user engagement or purchases.
- Global listing scores may reflect the latest watchlist scoring pass; watchlist views use match scores.

## Acceptance criteria

1. Empty databases return valid empty analytics payloads.
2. Restricted listings never appear in analytics.
3. Currency values are never combined in category price statistics.
4. Quartiles, rates, confidence adjustment, price drops, and stable ordering are tested.
5. Analytics remain async at the API boundary and SQLite work runs in worker threads.
6. The dashboard states the event-based limitations above.

## Rollback

Revert the analytics commit. No persistent schema change or data migration is introduced.
