# AGENTS.md

## Project rules

- Target Python 3.12 or newer.
- Use semantic versioning for releases and keep package/runtime version declarations aligned.
- Prefer async APIs for browser, network, database, and filesystem work.
- Never put blocking network/disk operations directly on the asyncio event loop.
- Preserve thread safety when moving unavoidable blocking work to worker threads.
- Do not implement CAPTCHA bypasses, credential theft, access-control bypasses, or anti-abuse evasion.
- Keep extraction logic behind adapters because Marketplace markup changes frequently.
- Add tests for parsers, normalization, persistence, migrations, scoring, and API behavior before expanding scraping coverage.
- Every persistent SQLite schema change must be represented by an idempotent versioned migration and tested against an older database fixture.
- Keep daemon defaults resource-conscious; reuse expensive resources, expose durable health/error state, and avoid unbounded concurrency.
- Update README.md, CHANGELOG.md, and TODO.md whenever user-visible behavior or roadmap state changes.
- Never commit browser storage-state files, credentials, cookies, databases, or collected private data.
