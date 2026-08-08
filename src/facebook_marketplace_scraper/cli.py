# src/facebook_marketplace_scraper/cli.py
from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import uvicorn

from .browser import MarketplaceBrowser
from .daemon import run_daemon
from .dashboard import create_dashboard_app
from .models import SearchSpec, Watchlist
from .service import MarketplaceCollector
from .storage import MarketplaceStore

app = typer.Typer(no_args_is_help=True, help="Facebook Marketplace research collector.")
watch_app = typer.Typer(no_args_is_help=True, help="Manage recurring Marketplace watchlists.")
session_app = typer.Typer(no_args_is_help=True, help="Manage the local browser session state.")
app.add_typer(watch_app, name="watch")
app.add_typer(session_app, name="session")

DEFAULT_DB = Path("data/marketplace.sqlite3")
DEFAULT_SESSION = Path("data/facebook_storage_state.json")


@app.command("init-db")
def init_db(db: Path = typer.Option(DEFAULT_DB, help="SQLite database path.")) -> None:
    """Create or upgrade the local SQLite schema."""
    asyncio.run(MarketplaceStore(db).initialize())
    typer.echo(f"Initialized {db}")


@session_app.command("login")
def session_login(
    session: Path = typer.Option(DEFAULT_SESSION, help="Playwright storage-state output path."),
) -> None:
    """Open a headed browser for manual sign-in and save its session state."""

    async def _run() -> None:
        async with MarketplaceBrowser(headless=False, storage_state_path=session) as browser:
            await browser.open_marketplace()
            typer.echo("Sign in manually in the browser window. No password is read by this tool.")
            await asyncio.to_thread(input, "Press Enter here after Marketplace is ready: ")
            target = await browser.save_storage_state(session)
            typer.echo(f"Saved browser session to {target}")

    asyncio.run(_run())


@app.command()
def search(
    query: str = typer.Argument(..., help="Marketplace search query."),
    max_items: int = typer.Option(20, min=1, max=500, help="Maximum listings to collect."),
    min_price: float | None = typer.Option(None, min=0, help="Local minimum price filter."),
    max_price: float | None = typer.Option(None, min=0, help="Local maximum price filter."),
    currency: str = typer.Option("CAD", help="Currency used for ambiguous '$' prices."),
    db: Path = typer.Option(DEFAULT_DB, help="SQLite database path."),
    session: Path = typer.Option(DEFAULT_SESSION, help="Playwright storage-state path."),
    headed: bool = typer.Option(False, help="Show the browser window."),
) -> None:
    """Collect, normalize, persist, deduplicate, and score one Marketplace search."""

    async def _run() -> None:
        store = MarketplaceStore(db)
        collector = MarketplaceCollector(
            store=store,
            storage_state_path=session,
            headless=not headed,
        )
        result = await collector.collect(
            SearchSpec(
                query=query,
                max_items=max_items,
                min_price=min_price,
                max_price=max_price,
                default_currency=currency,
            )
        )
        typer.echo(
            f"run={result.run_id} extracted={result.extracted} normalized={result.normalized} "
            f"inserted={result.inserted} updated={result.updated} price_changes={result.price_changes}"
        )
        for item in result.listings[:20]:
            listing = item.listing
            typer.echo(
                f"{item.deal_score:5.1f}  {listing.price_text or '—':>12}  "
                f"{listing.title[:70]}  {listing.url}"
            )

    asyncio.run(_run())


@watch_app.command("add")
def watch_add(
    name: str = typer.Option(..., help="Unique watchlist name."),
    query: str = typer.Option(..., help="Marketplace query."),
    min_price: float | None = typer.Option(None, min=0),
    max_price: float | None = typer.Option(None, min=0),
    target_price: float | None = typer.Option(None, min=0),
    max_items: int = typer.Option(50, min=1, max=500),
    interval_minutes: int = typer.Option(30, min=1),
    currency: str = typer.Option("CAD"),
    db: Path = typer.Option(DEFAULT_DB),
) -> None:
    """Create a recurring watchlist."""

    async def _run() -> None:
        store = MarketplaceStore(db)
        await store.initialize()
        watchlist_id = await store.create_watchlist(
            Watchlist(
                name=name,
                query=query,
                min_price=min_price,
                max_price=max_price,
                target_price=target_price,
                max_items=max_items,
                default_currency=currency,
                interval_seconds=interval_minutes * 60,
            )
        )
        typer.echo(f"Created watchlist {watchlist_id}: {name}")

    asyncio.run(_run())


@watch_app.command("list")
def watch_list(db: Path = typer.Option(DEFAULT_DB)) -> None:
    """List configured watchlists."""

    async def _run() -> None:
        store = MarketplaceStore(db)
        await store.initialize()
        for item in await store.list_watchlists():
            state = "on" if item.enabled else "off"
            typer.echo(
                f"{item.id:>3} [{state}] {item.name}: {item.query!r} "
                f"every {item.interval_seconds // 60}m target={item.target_price}"
            )

    asyncio.run(_run())


@watch_app.command("remove")
def watch_remove(
    watchlist_id: int = typer.Argument(...),
    db: Path = typer.Option(DEFAULT_DB),
) -> None:
    """Delete a watchlist and its match records."""

    async def _run() -> None:
        store = MarketplaceStore(db)
        await store.initialize()
        removed = await store.delete_watchlist(watchlist_id)
        if not removed:
            raise typer.Exit(code=1)
        typer.echo(f"Removed watchlist {watchlist_id}")

    asyncio.run(_run())


@app.command("daemon")
def daemon_command(
    db: Path = typer.Option(DEFAULT_DB),
    session: Path = typer.Option(DEFAULT_SESSION),
    poll_seconds: int = typer.Option(30, min=5),
    headed: bool = typer.Option(False),
    once: bool = typer.Option(False, help="Run all enabled watchlists once and exit."),
) -> None:
    """Run due watchlists continuously using one reusable browser session."""
    asyncio.run(
        run_daemon(
            db_path=db,
            storage_state_path=session,
            poll_seconds=poll_seconds,
            headless=not headed,
            once=once,
        )
    )


@app.command("dashboard")
def dashboard_command(
    db: Path = typer.Option(DEFAULT_DB),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8787, min=1, max=65535),
) -> None:
    """Serve the dashboard and JSON API."""
    uvicorn.run(create_dashboard_app(db), host=host, port=port, log_level="info")


if __name__ == "__main__":
    app()
