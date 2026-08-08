# src/facebook_marketplace_scraper/dashboard.py
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .storage import MarketplaceStore

_DASHBOARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marketplace Research Dashboard</title>
<style>
:root{color-scheme:dark;background:#0b0f14;color:#e7edf5;font-family:system-ui,sans-serif}
body{margin:0;background:#0b0f14}.wrap{max-width:1400px;margin:auto;padding:24px}
h1{margin:0 0 6px}.muted{color:#91a0b4}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:22px 0}
.card{background:#121923;border:1px solid #243044;border-radius:12px;padding:16px}.value{font-size:28px;font-weight:700}
table{width:100%;border-collapse:collapse;background:#121923;border-radius:12px;overflow:hidden}th,td{padding:11px;border-bottom:1px solid #243044;text-align:left}th{color:#91a0b4}.score{font-weight:700}.price{white-space:nowrap}a{color:#70b7ff;text-decoration:none}img{width:64px;height:48px;object-fit:cover;border-radius:6px;background:#202b3b}
</style></head><body><div class="wrap"><h1>Marketplace Research Dashboard</h1><div class="muted">Collection history, watchlists and deal scoring</div><div id="stats" class="stats"></div><table><thead><tr><th></th><th>Listing</th><th>Price</th><th>Location</th><th>Score</th><th>Confidence</th><th>Last seen</th></tr></thead><tbody id="rows"></tbody></table></div>
<script>
const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function load(){const [s,l]=await Promise.all([fetch('/api/stats').then(r=>r.json()),fetch('/api/listings?limit=100').then(r=>r.json())]);
document.getElementById('stats').innerHTML=Object.entries(s).map(([k,v])=>`<div class="card"><div class="muted">${esc(k.replaceAll('_',' '))}</div><div class="value">${esc(v)}</div></div>`).join('');
document.getElementById('rows').innerHTML=l.map(x=>`<tr><td>${x.image_url?`<img src="${esc(x.image_url)}" loading="lazy">`:''}</td><td><a href="${esc(x.url)}" target="_blank" rel="noreferrer">${esc(x.title)}</a><div class="muted">${esc(x.source_query)}</div></td><td class="price">${esc(x.latest_price_text??'—')}</td><td>${esc(x.location??'—')}</td><td class="score">${Number(x.deal_score).toFixed(1)}</td><td>${Math.round(Number(x.score_confidence)*100)}%</td><td>${esc(x.last_seen)}</td></tr>`).join('');}
load();setInterval(load,30000);
</script></body></html>"""


def create_dashboard_app(db_path: Path) -> FastAPI:
    store = MarketplaceStore(db_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await store.initialize()
        yield

    app = FastAPI(
        title="Facebook Marketplace Scraper Dashboard",
        version="0.2.0",
        lifespan=lifespan,
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return _DASHBOARD

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/stats")
    async def stats() -> dict[str, object]:
        return await store.dashboard_stats()

    @app.get("/api/listings")
    async def listings(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
        return await store.recent_listings(limit=limit)

    @app.get("/api/listings/{listing_id}/history")
    async def history(listing_id: str) -> list[dict[str, object]]:
        result = await store.listing_history(listing_id)
        if not result:
            raise HTTPException(status_code=404, detail="No price history for listing")
        return result

    @app.get("/api/watchlists")
    async def watchlists() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in await store.list_watchlists()]

    return app
