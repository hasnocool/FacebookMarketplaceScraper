# Changelog

All notable changes to this project are documented here.

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
