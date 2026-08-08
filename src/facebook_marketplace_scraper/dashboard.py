# src/facebook_marketplace_scraper/dashboard.py
from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, model_validator

from . import __version__
from .models import Watchlist
from .storage import LATEST_SCHEMA_VERSION, MarketplaceStore


class WatchlistWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=500)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    max_items: int = Field(default=50, ge=1, le=500)
    default_currency: str = Field(default="CAD", min_length=3, max_length=8)
    interval_seconds: int = Field(default=1800, ge=60)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_price_range(self) -> WatchlistWrite:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot be greater than max_price")
        return self


class WatchlistPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    query: str | None = Field(default=None, min_length=1, max_length=500)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    max_items: int | None = Field(default=None, ge=1, le=500)
    default_currency: str | None = Field(default=None, min_length=3, max_length=8)
    interval_seconds: int | None = Field(default=None, ge=60)
    enabled: bool | None = None


_DASHBOARD = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marketplace Research Dashboard</title><style>
:root{color-scheme:dark;background:#0b0f14;color:#e7edf5;font-family:system-ui,sans-serif}*{box-sizing:border-box}body{margin:0;background:#0b0f14}.wrap{max-width:1480px;margin:auto;padding:24px}.muted{color:#91a0b4}.ok{color:#6ee7a0}.bad{color:#ff8a8a}h1,h2{margin:0 0 8px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}.card,.panel{background:#121923;border:1px solid #243044;border-radius:12px;padding:16px}.value{font-size:25px;font-weight:700}.grid{display:grid;grid-template-columns:minmax(320px,420px) 1fr;gap:16px;margin-bottom:20px}@media(max-width:900px){.grid{grid-template-columns:1fr}}form{display:grid;grid-template-columns:1fr 1fr;gap:10px}form .wide{grid-column:1/-1}label{font-size:12px;color:#91a0b4}input,button{width:100%;border-radius:8px;border:1px solid #34445d;background:#0b111a;color:#e7edf5;padding:10px}button{cursor:pointer;background:#1b2b40}button.danger{background:#3c1c22}button.small{width:auto;padding:6px 9px;margin-right:5px}table{width:100%;border-collapse:collapse;background:#121923;border-radius:12px;overflow:hidden;margin-bottom:18px}th,td{padding:10px;border-bottom:1px solid #243044;text-align:left;vertical-align:top}th{color:#91a0b4}.score{font-weight:700}.price{white-space:nowrap}a{color:#70b7ff;text-decoration:none}img{width:64px;height:48px;object-fit:cover;border-radius:6px;background:#202b3b}.error{max-width:420px;white-space:normal;color:#ff9d9d}.pill{display:inline-block;border:1px solid #34445d;border-radius:999px;padding:2px 7px;margin:2px;font-size:12px;color:#b8c5d8}
</style></head><body><div class="wrap"><h1>Marketplace Research Dashboard</h1><div class="muted">Collection, valuation, watchlists, health, notifications and run timing</div><div id="stats" class="stats"></div>
<div class="grid"><section class="panel"><h2 id="formTitle">Add watchlist</h2><form id="watchForm"><input id="watchId" type="hidden"><div class="wide"><label>Name</label><input id="name" required maxlength="120"></div><div class="wide"><label>Search query</label><input id="query" required maxlength="500"></div><div><label>Min price</label><input id="minPrice" type="number" min="0" step="0.01"></div><div><label>Max price</label><input id="maxPrice" type="number" min="0" step="0.01"></div><div><label>Target price</label><input id="targetPrice" type="number" min="0" step="0.01"></div><div><label>Interval minutes</label><input id="interval" type="number" min="1" value="30"></div><div><label>Max items</label><input id="maxItems" type="number" min="1" max="500" value="50"></div><div><label>Currency</label><input id="currency" value="CAD" maxlength="8"></div><div class="wide"><button type="submit">Save watchlist</button></div><div class="wide"><button id="cancelEdit" type="button" hidden>Cancel edit</button></div></form></section><section class="panel"><h2>Watchlists</h2><div id="watchlists"></div></section></div>
<h2>Listings</h2><table><thead><tr><th></th><th>Listing</th><th>Metadata</th><th>Price</th><th>Score</th><th>Confidence</th><th>Last seen</th></tr></thead><tbody id="rows"></tbody></table>
<div class="grid"><section class="panel"><h2>Recent notifications</h2><div id="notifications"></div></section><section class="panel"><h2>Recent runs</h2><div id="runs"></div></section></div></div><script>
const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));const num=v=>v===''?null:Number(v);let watchCache=[];async function api(url,opts={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opts});if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||r.statusText)}return r.status===204?null:r.json()}
async function load(){const [s,l,w,h,n,runs]=await Promise.all([api('/api/stats'),api('/api/listings?limit=100'),api('/api/watchlists'),api('/api/health'),api('/api/notifications?limit=20'),api('/api/runs?limit=20')]);watchCache=w;const daemon=h.daemon||{};const healthClass=h.status==='ok'?'ok':'bad';const cards={...s,health:`<span class="${healthClass}">${esc(h.status)}</span>`,daemon:esc(daemon.effective_state||'unknown')};document.getElementById('stats').innerHTML=Object.entries(cards).map(([k,v])=>`<div class="card"><div class="muted">${esc(k.replaceAll('_',' '))}</div><div class="value">${typeof v==='string'&&v.startsWith('<span')?v:esc(v)}</div></div>`).join('');
document.getElementById('watchlists').innerHTML=w.length?`<table><tbody>${w.map(x=>`<tr><td><b>${esc(x.name)}</b><div class="muted">${esc(x.query)}</div>${x.last_error?`<div class="error">${esc(x.last_error)}</div>`:''}</td><td>${Math.round(x.interval_seconds/60)}m<br>${x.enabled?'enabled':'disabled'}</td><td><button class="small" onclick="editWatch(${x.id})">Edit</button><button class="small" onclick="toggleWatch(${x.id},${!x.enabled})">${x.enabled?'Disable':'Enable'}</button><button class="small danger" onclick="removeWatch(${x.id})">Delete</button></td></tr>`).join('')}</tbody></table>`:'<div class="muted">No watchlists yet.</div>';
document.getElementById('rows').innerHTML=l.map(x=>`<tr><td>${x.image_url?`<img src="${esc(x.image_url)}" loading="lazy">`:''}</td><td><a href="/listing/${encodeURIComponent(x.listing_id)}">${esc(x.title)}</a><div class="muted"><a href="${esc(x.url)}" target="_blank" rel="noreferrer">Marketplace</a> · ${esc(x.source_query)}</div></td><td><span class="pill">${esc(x.category)}</span><span class="pill">${esc(x.condition)}</span><div class="muted">${esc(x.classification_source)}</div></td><td class="price">${esc(x.latest_price_text??'—')}<div class="muted">${esc(x.location??'—')}</div></td><td class="score">${Number(x.deal_score).toFixed(1)}</td><td>${Math.round(Number(x.score_confidence)*100)}%</td><td>${esc(x.last_seen)}</td></tr>`).join('');
document.getElementById('notifications').innerHTML=n.length?`<table><tbody>${n.map(x=>`<tr><td><b>${esc(x.payload?.title||x.listing_id)}</b><div class="muted">${esc(x.event_type)} · score ${esc(x.score)} · ${esc(x.created_at)}</div></td></tr>`).join('')}</tbody></table>`:'<div class="muted">No notification events.</div>';document.getElementById('runs').innerHTML=runs.length?`<table><tbody>${runs.map(x=>`<tr><td>${esc(x.query)}<div class="muted">${esc(x.extracted)} extracted / ${esc(x.normalized)} stored</div></td><td>${x.duration_ms==null?'—':Math.round(x.duration_ms)+' ms'}</td></tr>`).join('')}</tbody></table>`:'<div class="muted">No search runs.</div>'}
function resetForm(){for(const id of ['watchId','name','query','minPrice','maxPrice','targetPrice'])document.getElementById(id).value='';document.getElementById('interval').value=30;document.getElementById('maxItems').value=50;document.getElementById('currency').value='CAD';document.getElementById('formTitle').textContent='Add watchlist';document.getElementById('cancelEdit').hidden=true}function editWatch(id){const x=watchCache.find(v=>v.id===id);if(!x)return;document.getElementById('watchId').value=x.id;document.getElementById('name').value=x.name;document.getElementById('query').value=x.query;document.getElementById('minPrice').value=x.min_price??'';document.getElementById('maxPrice').value=x.max_price??'';document.getElementById('targetPrice').value=x.target_price??'';document.getElementById('interval').value=x.interval_seconds/60;document.getElementById('maxItems').value=x.max_items;document.getElementById('currency').value=x.default_currency;document.getElementById('formTitle').textContent='Edit watchlist';document.getElementById('cancelEdit').hidden=false;window.scrollTo({top:200,behavior:'smooth'})}async function toggleWatch(id,enabled){await api(`/api/watchlists/${id}`,{method:'PATCH',body:JSON.stringify({enabled})});await load()}async function removeWatch(id){if(!confirm('Delete this watchlist?'))return;await api(`/api/watchlists/${id}`,{method:'DELETE'});resetForm();await load()}document.getElementById('cancelEdit').onclick=resetForm;document.getElementById('watchForm').onsubmit=async e=>{e.preventDefault();const id=document.getElementById('watchId').value;const body={name:document.getElementById('name').value.trim(),query:document.getElementById('query').value.trim(),min_price:num(document.getElementById('minPrice').value),max_price:num(document.getElementById('maxPrice').value),target_price:num(document.getElementById('targetPrice').value),interval_seconds:Math.max(60,Math.round(Number(document.getElementById('interval').value)*60)),max_items:Number(document.getElementById('maxItems').value),default_currency:document.getElementById('currency').value.trim()||'CAD'};try{await api(id?`/api/watchlists/${id}`:'/api/watchlists',{method:id?'PATCH':'POST',body:JSON.stringify(body)});resetForm();await load()}catch(err){alert(err.message)}};load();setInterval(load,30000);
</script></body></html>"""

_DETAIL = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Listing detail</title><style>:root{color-scheme:dark;background:#0b0f14;color:#e7edf5;font-family:system-ui,sans-serif}body{margin:0}.wrap{max-width:1100px;margin:auto;padding:24px}.panel{background:#121923;border:1px solid #243044;border-radius:12px;padding:18px;margin:16px 0}.muted{color:#91a0b4}a{color:#70b7ff;text-decoration:none}.meta{display:flex;gap:8px;flex-wrap:wrap}.pill{border:1px solid #34445d;border-radius:999px;padding:3px 8px}svg{width:100%;height:280px;background:#0b111a;border-radius:10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:760px){.grid{grid-template-columns:1fr}}</style></head><body><div class="wrap"><a href="/">← Dashboard</a><div id="content"></div></div><script>const listingId=__LISTING_ID__;const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));async function api(u){const r=await fetch(u);if(!r.ok)throw new Error((await r.json()).detail||r.statusText);return r.json()}function chart(history){const pts=history.filter(x=>x.price_value!=null).reverse();if(!pts.length)return '<div class="muted">No numeric price history.</div>';const w=900,h=240,p=30;const vals=pts.map(x=>Number(x.price_value));const min=Math.min(...vals),max=Math.max(...vals);const span=Math.max(1,max-min);const xy=pts.map((x,i)=>{const px=p+(i*(w-2*p)/Math.max(1,pts.length-1));const py=h-p-((Number(x.price_value)-min)/span)*(h-2*p);return [px,py]});return `<svg viewBox="0 0 ${w} ${h}" role="img"><polyline fill="none" stroke="currentColor" stroke-width="3" points="${xy.map(p=>p.join(',')).join(' ')}"/>${xy.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(pts[i].price_text)} · ${esc(pts[i].captured_at)}</title></circle>`).join('')}<text x="${p}" y="20" fill="currentColor">${esc(max.toFixed(2))}</text><text x="${p}" y="${h-6}" fill="currentColor">${esc(min.toFixed(2))}</text></svg>`}async function load(){const [x,h]=await Promise.all([api(`/api/listings/${encodeURIComponent(listingId)}`),api(`/api/listings/${encodeURIComponent(listingId)}/history`)]);document.getElementById('content').innerHTML=`<div class="panel"><h1>${esc(x.title)}</h1><div class="meta"><span class="pill">${esc(x.category)}</span><span class="pill">${esc(x.condition)}</span><span class="pill">score ${Number(x.deal_score).toFixed(1)}</span><span class="pill">confidence ${Math.round(Number(x.score_confidence)*100)}%</span></div><p><b>${esc(x.latest_price_text??'—')}</b> · ${esc(x.location??'location unknown')}</p><p class="muted">classified by ${esc(x.classification_source)} (${Math.round(Number(x.classification_confidence)*100)}%)</p><p><a href="${esc(x.url)}" target="_blank" rel="noreferrer">Open Marketplace listing</a></p></div><div class="panel"><h2>Price history</h2>${chart(h)}</div><div class="grid"><div class="panel"><h2>Score reasons</h2><ul>${(x.score_reasons||[]).map(r=>`<li>${esc(r)}</li>`).join('')}</ul></div><div class="panel"><h2>Observed metadata</h2><p>First seen: ${esc(x.first_seen)}</p><p>Last seen: ${esc(x.last_seen)}</p><p>Source query: ${esc(x.source_query)}</p></div></div>`}load().catch(e=>document.getElementById('content').textContent=e.message);</script></body></html>"""


def _watchlist_payload(item: Watchlist) -> dict[str, object]:
    return item.model_dump(mode="json")


def create_dashboard_app(db_path: Path) -> FastAPI:
    store = MarketplaceStore(db_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await store.initialize()
        yield

    app = FastAPI(title="Facebook Marketplace Scraper Dashboard", version=__version__, lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return _DASHBOARD

    @app.get("/listing/{listing_id}", response_class=HTMLResponse)
    async def listing_page(listing_id: str) -> str:
        if await store.listing_detail(listing_id) is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        return _DETAIL.replace("__LISTING_ID__", json.dumps(listing_id))

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        schema_version = await store.schema_version()
        daemon = await store.daemon_status()
        degraded = schema_version != LATEST_SCHEMA_VERSION or daemon.get("effective_state") in {"error", "stale"}
        return {"status": "degraded" if degraded else "ok", "schema_version": schema_version, "latest_schema_version": LATEST_SCHEMA_VERSION, "daemon": daemon}

    @app.get("/api/stats")
    async def stats() -> dict[str, object]:
        return await store.dashboard_stats()

    @app.get("/api/listings")
    async def listings(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, object]]:
        return await store.recent_listings(limit=limit)

    @app.get("/api/listings/{listing_id}")
    async def listing_detail(listing_id: str) -> dict[str, object]:
        result = await store.listing_detail(listing_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        return result

    @app.get("/api/listings/{listing_id}/history")
    async def history(listing_id: str) -> list[dict[str, object]]:
        if await store.listing_detail(listing_id) is None:
            raise HTTPException(status_code=404, detail="Listing not found")
        return await store.listing_history(listing_id)

    @app.get("/api/notifications")
    async def notifications(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, object]]:
        return await store.recent_notifications(limit=limit)

    @app.get("/api/runs")
    async def runs(limit: int = Query(default=30, ge=1, le=200)) -> list[dict[str, object]]:
        return await store.search_run_metrics(limit=limit)

    @app.get("/api/watchlists")
    async def watchlists() -> list[dict[str, object]]:
        return [_watchlist_payload(item) for item in await store.list_watchlists()]

    @app.post("/api/watchlists", status_code=status.HTTP_201_CREATED)
    async def create_watchlist(payload: WatchlistWrite) -> dict[str, object]:
        try:
            watchlist_id = await store.create_watchlist(Watchlist(**payload.model_dump()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Watchlist name already exists") from exc
        created = await store.get_watchlist(watchlist_id)
        if created is None:
            raise HTTPException(status_code=500, detail="Watchlist was not persisted")
        return _watchlist_payload(created)

    @app.patch("/api/watchlists/{watchlist_id}")
    async def update_watchlist(watchlist_id: int, payload: WatchlistPatch) -> dict[str, object]:
        current = await store.get_watchlist(watchlist_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        updates = payload.model_dump(exclude_unset=True)
        merged = {
            "name": current.name, "query": current.query, "min_price": current.min_price,
            "max_price": current.max_price, "target_price": current.target_price,
            "max_items": current.max_items, "default_currency": current.default_currency,
            "interval_seconds": current.interval_seconds, "enabled": current.enabled, **updates,
        }
        validated = WatchlistWrite(**merged)
        try:
            updated = await store.update_watchlist(watchlist_id, validated.model_dump())
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Watchlist name already exists") from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        return _watchlist_payload(updated)

    @app.delete("/api/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_watchlist(watchlist_id: int) -> Response:
        if not await store.delete_watchlist(watchlist_id):
            raise HTTPException(status_code=404, detail="Watchlist not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app
