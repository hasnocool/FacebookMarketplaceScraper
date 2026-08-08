# AGENTS.md

## Project rules

- Target Python 3.12 or newer.
- Prefer async APIs for browser, network, database, and filesystem work.
- Never put blocking network/disk operations directly on the asyncio event loop.
- Preserve thread safety when moving unavoidable blocking work to worker threads.
- Do not implement CAPTCHA bypasses, credential theft, access-control bypasses, or anti-abuse evasion.
- Keep extraction logic behind adapters because Marketplace markup changes frequently.
- Add tests for parsers and normalization before expanding scraping coverage.
- Update README.md and CHANGELOG.md for user-visible changes.
