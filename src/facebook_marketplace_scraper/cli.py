# src/facebook_marketplace_scraper/cli.py
from __future__ import annotations

import asyncio

import typer

from .service import search_marketplace

app = typer.Typer(no_args_is_help=True)


@app.command()
def search(
    query: str = typer.Argument(..., help="Marketplace search query."),
    max_items: int = typer.Option(20, min=1, help="Maximum listings to collect."),
    headed: bool = typer.Option(False, help="Show the browser window."),
) -> None:
    """Open a Marketplace search using the async browser layer."""

    async def _run() -> None:
        result = await search_marketplace(query, max_items=max_items, headless=not headed)
        typer.echo(f"query={result.query!r}")
        typer.echo(f"page_title={result.page_title!r}")
        typer.echo("Listing extraction adapter is the next implementation step.")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
