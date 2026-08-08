# FacebookMarketplaceScraper

Async-first Python 3.12+ Facebook Marketplace research toolkit with a full local collection pipeline:

**search → extract → normalize → SQLite → deduplicate → historical pricing → deal scoring → watchlists → daemon → dashboard**

The collector uses Playwright and only reads Marketplace content available to the browser session you provide. It does not include CAPTCHA bypass, credential theft, access-control bypass, or anti-abuse evasion.

## Features

- Stable-ish extraction adapter based on `/marketplace/item/` links rather than generated CSS classes.
- Normalized listing IDs, titles, prices, currencies, locations, canonical URLs, and fingerprints.
- Non-blocking SQLite persistence using thread-isolated standard-library connections and WAL mode.
- Versioned SQLite migrations that upgrade existing databases in place.
- Primary deduplication by Marketplace listing ID across searches and watchlists.
- Compact historical pricing that records the initial observation and later price changes.
- Deal scoring against the latest prices of comparable normalized-title listings.
- Persistent watchlists with local price filters, target prices, collection limits, and intervals.
- Resource-conscious daemon that reuses one browser and processes watchlists sequentially.
- Durable daemon heartbeat, active-watchlist, success, and last-error state.
- FastAPI JSON API and dark dashboard for inventory, scores, service health, and watchlist management.
- Manual browser-session capture so credentials do not need to be stored by the application.

## Install

```bash
# README.md usage commands
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
playwright install chromium
fb-market init-db
```

`fb-market init-db` is safe to run on an existing database. Schema upgrades are applied as versioned migrations and recorded in `schema_migrations`.

## Create a browser session

Some Marketplace views require you to be signed in. The project opens a normal headed Chromium window and lets you sign in yourself:

```bash
# README.md usage commands
fb-market session login
```

The resulting `data/facebook_storage_state.json` is ignored by Git and reused for later searches. Do not commit or share that file.

## Run a collection

```bash
# README.md usage commands
fb-market search "thinkpad" --max-items 50
fb-market search "solar panel" --min-price 25 --max-price 500 --max-items 100
```

Each run writes normalized listings into `data/marketplace.sqlite3`, deduplicates previously seen listing IDs, records price changes, and recomputes deal scores.

## Watchlists

Create watchlists from the CLI:

```bash
# README.md usage commands
fb-market watch add --name laptops --query "thinkpad" --target-price 250 --interval-minutes 30
fb-market watch add --name solar --query "solar panel" --max-price 500 --interval-minutes 60
fb-market watch list
```

You can also create, edit, enable/disable, and delete watchlists directly from the web dashboard.

Run all enabled watchlists once:

```bash
# README.md usage commands
fb-market daemon --once
```

Run continuously:

```bash
# README.md usage commands
fb-market daemon
```

The daemon uses one browser process and runs due watchlists sequentially to keep CPU, RAM, and network use predictable. Daemon lifecycle and errors are persisted in SQLite so the dashboard can distinguish running, stale, stopped, and error states.

## Dashboard

```bash
# README.md usage commands
fb-market dashboard --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787/`.

The dashboard shows collection statistics, daemon health, recent listings, deal scores, and watchlist controls.

API endpoints include:

- `GET /api/health`
- `GET /api/stats`
- `GET /api/listings?limit=100`
- `GET /api/listings/{listing_id}/history`
- `GET /api/watchlists`
- `POST /api/watchlists`
- `PATCH /api/watchlists/{watchlist_id}`
- `DELETE /api/watchlists/{watchlist_id}`

`GET /api/health` reports the current database schema version and durable daemon state. A stale heartbeat or daemon error returns a degraded health status.

## systemd user service

An example unit is provided at `deploy/facebook-marketplace-scraper.service`.

```bash
# README.md usage commands
mkdir -p ~/.config/systemd/user
cp deploy/facebook-marketplace-scraper.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now facebook-marketplace-scraper.service
```

Adjust `WorkingDirectory`/`ExecStart` if you clone the repository somewhere other than `~/FacebookMarketplaceScraper`.

## Data model

SQLite tables:

- `schema_migrations`: applied database schema versions.
- `listings`: canonical/latest listing state and current score.
- `listing_prices`: initial price plus later price changes.
- `search_runs`: collection-run audit trail and counters.
- `search_run_listings`: run-to-listing membership.
- `watchlists`: recurring searches, thresholds, and per-watchlist run/error state.
- `watchlist_matches`: listings observed by each watchlist.
- `daemon_status`: singleton durable daemon heartbeat/lifecycle/error record.

## Scoring

The initial score is intentionally transparent rather than ML-based. It considers:

1. current price versus the median latest price of exact normalized-title peers,
2. price drops versus the listing's prior observation,
3. watchlist target-price hits,
4. sample-size confidence.

This provides a useful baseline that can later be upgraded with fuzzy comparables, category-aware models, or a local LLM without changing the collection/storage contract.

## Development

```bash
# README.md usage commands
pytest
ruff check .
python -m compileall src tests
```

CI runs Ruff, bytecode compilation, and the test suite on Python 3.12 and Python 3.13.
