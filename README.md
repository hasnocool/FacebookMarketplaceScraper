# FacebookMarketplaceScraper

An async-first Python 3.12 foundation for collecting and analyzing Facebook Marketplace listings.

## Goals

- Search Marketplace listings by query and location.
- Normalize listing data into a stable model.
- Deduplicate listings across repeated scans.
- Save results for later analysis and alerting.
- Keep browser/network operations asynchronous and avoid blocking the event loop.
- Leave room for price scoring, notifications, a dashboard, and scheduled monitoring.

## Important boundary

Use this project only with pages and accounts you are authorized to access. Do not use it to bypass authentication, CAPTCHAs, rate limits, access controls, or other anti-abuse protections. Facebook can change its interface and terms at any time.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -e '.[dev]'
playwright install chromium
```

## Run

```bash
fb-market search "solar panel" --max-items 20
```

The initial browser adapter intentionally stops short of relying on brittle private APIs or anti-bot bypasses. It opens the Marketplace search page and provides the project structure for robust extraction logic.

## Development

```bash
ruff check .
pytest
```

## Planned roadmap

- Stable DOM extraction adapters.
- SQLite persistence using an async database layer.
- Deduplication and listing-history tracking.
- Location/radius filters.
- Price normalization and deal scoring.
- Watchlists and change detection.
- Optional local LLM classification.
- Web and CLI dashboards.
- Service/daemon mode.
