# Changelog

All notable changes to this project are documented here.

## [0.4.0] - 2026-08-08

### Added

- Deterministic fuzzy comparable-title matching for deal-score price evidence.
- Unit/spec normalization for common Marketplace title variants such as `100 watts`/`100W` and `16 GB`/`16GB`.
- Model-number guardrails so different model tokens such as T480 and T490 are not grouped as comparables.
- Regression coverage for comparable tokenization, model matching, unit aliases, and fuzzy historical price statistics.

### Changed

- Upgraded package version from 0.3.0 to 0.4.0.
- Comparable-price lookups now use a broad indexed-title prefilter followed by weighted token similarity instead of exact normalized-title equality.
- Comparable candidates are capped to recent same-currency listings to keep scoring CPU and I/O bounded.

## [0.3.0] - 2026-08-08

### Added

- Versioned, idempotent SQLite migrations with an explicit schema version.
- Automatic in-place upgrade path for existing 0.2.x databases.
- Persistent daemon lifecycle, heartbeat, active-watchlist, success, and last-error metadata.
- Per-watchlist last-success and last-error metadata.
- Dashboard/API watchlist create, edit, enable/disable, and delete controls.
- Health API backed by real schema and daemon state instead of a constant response.
- Regression tests for legacy migrations, daemon health state, and dashboard watchlist CRUD.

### Changed

- Upgraded package version from 0.2.0 to 0.3.0.
- Updated dependency floors to versions verified by the 2026-08-08 GitHub CI environment.
- Daemon errors remain visible until a successful cycle rather than being cleared by a heartbeat.
- Watchlist run completion now records success/failure explicitly.

## [0.2.0] - 2026-08-08

### Added

- End-to-end Marketplace collection pipeline.
- DOM extraction adapter using Marketplace item links.
- Listing normalization and canonical IDs/fingerprints.
- Async SQLite storage with WAL mode, deduplication, search-run audit data, and price history.
- Comparable-market deal scoring with confidence and price-drop reasons.
- Persistent watchlists and watchlist match tracking.
- Resource-conscious recurring daemon with a reusable browser context.
- Manual Playwright session-state capture.
- FastAPI JSON endpoints and a live dashboard.
- Example systemd user service.
- Tests for normalization, scoring, storage/deduplication, watchlists, and the collection pipeline.

### Changed

- Upgraded package version from 0.1.0 to 0.2.0.
- Updated runtime dependency floors for Playwright and the new database/dashboard stack.

## [0.1.0] - 2026-08-08

### Added

- Initial Python 3.12 project scaffold.
- Async Playwright browser lifecycle wrapper.
- Typer CLI foundation.
- Pydantic listing model.
- Initial tests and project governance files.
