# TODO

## Near term

- Capture and commit a sanitized authenticated Marketplace fixture with `fb-market fixture capture` in an environment that has the saved browser session; the repository keeps a sanitized contract sample until that external validation can run.
- Add category-specific feature extraction beyond title text where stable detail-page fields are available.
- Add robust-outlier comparable statistics and category-specific scoring calibration datasets.
- Add notification adapters for additional self-hosted destinations.
- Add CPU/RSS/network measurements to the existing run-duration operational metrics.
- Add CSV/JSON export for analytics reports.
- Add persistent per-run listing/score snapshots for inventory-style historical analytics.

## Later

- Multiple Marketplace profiles with separate browser storage states (single-session Victoria/Sooke/Nanaimo switching is implemented).
- Pluggable scoring strategies and learned category-specific valuation models.
- Optional local embeddings/reranking for comparable grouping while retaining deterministic fallback behavior.
