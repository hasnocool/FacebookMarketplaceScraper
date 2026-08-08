# TODO

## Near term

- Add fixture-based extraction tests captured from real Marketplace result markup.
- Add fuzzy comparable grouping so minor title variations share pricing history.
- Add optional category/condition fields when reliably extractable.
- Add dashboard watchlist create/edit/enable controls.
- Add daemon health/status metadata and last-error reporting.
- Add migrations/versioned schema upgrades before the next breaking DB change.
- Add structured logging and configurable retention limits.

## Later

- Optional local-LLM classification for category, condition, and comparable grouping.
- Notification adapters for high-score or target-price matches.
- CSV/JSON export and analytics reports.
- Multiple Marketplace regions/profiles with separate browser storage states.
- Pluggable scoring strategies and category-specific valuation models.
