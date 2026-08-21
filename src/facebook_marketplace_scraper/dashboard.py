# src/facebook_marketplace_scraper/dashboard.py
from __future__ import annotations

import asyncio
import json
import shutil
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
:root{color-scheme:dark;background:#0b0f14;color:#e7edf5;font-family:system-ui,sans-serif}*{box-sizing:border-box}body{margin:0;background:#0b0f14}.wrap{max-width:1480px;margin:auto;padding:24px}.muted{color:#91a0b4}.ok{color:#6ee7a0}.bad{color:#ff8a8a}h1,h2{margin:0 0 8px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}.card,.panel{background:#121923;border:1px solid #243044;border-radius:12px;padding:16px}.value{font-size:25px;font-weight:700}.grid{display:grid;grid-template-columns:minmax(320px,420px) 1fr;gap:16px;margin-bottom:20px}@media(max-width:900px){.grid{grid-template-columns:1fr}}form{display:grid;grid-template-columns:1fr 1fr;gap:10px}form .wide{grid-column:1/-1}label{font-size:12px;color:#91a0b4}input,button{width:100%;border-radius:8px;border:1px solid #34445d;background:#0b111a;color:#e7edf5;padding:10px}button{cursor:pointer;background:#1b2b40}button.danger{background:#3c1c22}button.small{width:auto;padding:6px 9px;margin-right:5px}button.primary{background:#1e3a5f}button:disabled{opacity:0.5;cursor:not-allowed}table{width:100%;border-collapse:collapse;background:#121923;border-radius:12px;overflow:hidden;margin-bottom:18px}th,td{padding:10px;border-bottom:1px solid #243044;text-align:left;vertical-align:top}th{color:#91a0b4}.score{font-weight:700}.price{white-space:nowrap}a{color:#70b7ff;text-decoration:none}img{width:64px;height:48px;object-fit:cover;border-radius:6px;background:#202b3b}.error{max-width:420px;white-space:normal;color:#ff9d9d}.pill{display:inline-block;border:1px solid #34445d;border-radius:999px;padding:2px 7px;margin:2px;font-size:12px;color:#b8c5d8}.session-status{padding:8px;border-radius:8px;margin:8px 0}.session-status.valid{background:#1a3c2e;border:1px solid #2e7d4a}.session-status.expired{background:#3c1c22;border:1px solid #7d2e2e}.session-status.unknown{background:#3c361c;border:1px solid #7d732e}
</style></head><body><div class="wrap"><h1>Marketplace Research Dashboard</h1><div class="muted">Collection, valuation, watchlists, health, notifications and run timing</div><div id="stats" class="stats"></div>
<div class="grid"><section class="panel"><h2>Facebook Session</h2><div id="sessionPanel"></div></section><section class="panel"><h2 id="formTitle">Add watchlist</h2><form id="watchForm"><input id="watchId" type="hidden"><div class="wide"><label>Name</label><input id="name" required maxlength="120"></div><div class="wide"><label>Search query</label><input id="query" required maxlength="500"></div><div><label>Min price</label><input id="minPrice" type="number" min="0" step="0.01"></div><div><label>Max price</label><input id="maxPrice" type="number" min="0" step="0.01"></div><div><label>Target price</label><input id="targetPrice" type="number" min="0" step="0.01"></div><div><label>Interval minutes</label><input id="interval" type="number" min="1" value="30"></div><div><label>Max items</label><input id="maxItems" type="number" min="1" max="500" value="50"></div><div><label>Currency</label><input id="currency" value="CAD" maxlength="8"></div><div class="wide"><button type="submit">Save watchlist</button></div><div class="wide"><button id="cancelEdit" type="button" hidden>Cancel edit</button></div></form></section><section class="panel"><h2>Watchlists</h2><div id="watchlists"></div></section></div>
<h2>Listings</h2><table><thead><tr><th></th><th>Listing</th><th>Metadata</th><th>Price</th><th>Score</th><th>Confidence</th><th>Last seen</th></tr></thead><tbody id="rows"></tbody></table>
<div class="grid"><section class="panel"><h2>Recent notifications</h2><div id="notifications"></div></section><section class="panel"><h2>Recent runs</h2><div id="runs"></div></section></div></div><script>
const esc=s=>String(s==null?"":s).replace(/[&<>\"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]});const num=v=>v===""?null:Number(v);let watchCache=[];async function api(url,opts={}){const r=await fetch(url,{headers:{"Content-Type":"application/json"},...opts});if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||r.statusText)}return r.status===204?null:r.json()}
async function load(){try{const [s,l,w,h,n,runs]=await Promise.all([api('/api/stats'),api('/api/listings?limit=100'),api('/api/watchlists'),api('/api/health'),api('/api/notifications?limit=20'),api('/api/runs?limit=20')]);watchCache=w;const daemon=h.daemon||{};const healthClass=h.status==='ok'?'ok':'bad';const cards={};Object.assign(cards,s);cards.health='<span class="'+healthClass+'">'+esc(h.status)+'</span>';cards.daemon=esc(daemon.effective_state||'unknown');document.getElementById('stats').innerHTML=Object.keys(cards).map(function(k){var v=cards[k];return '<div class="card"><div class="muted">'+esc(k.replaceAll('_',' '))+'</div><div class="value">'+(typeof v==='string'&&v.indexOf('<span')===0?v:esc(v))+'</div></div>';}).join('');
document.getElementById('watchlists').innerHTML=w.length?'<table><tbody>'+w.map(function(x){return '<tr><td><b>'+esc(x.name)+'</b><div class="muted">'+esc(x.query)+'</div>'+(x.last_error?'<div class="error">'+esc(x.last_error)+'</div>':'')+'</td><td>'+Math.round(x.interval_seconds/60)+'m<br>'+(x.enabled?'enabled':'disabled')+'</td><td><button class="small" onclick="editWatch('+x.id+')">Edit</button><button class="small" onclick="toggleWatch('+x.id+','+(!x.enabled)+')">'+(x.enabled?'Disable':'Enable')+'</button><button class="small danger" onclick="removeWatch('+x.id+')">Delete</button></td></tr>';}).join('')+'</tbody></table>':'<div class="muted">No watchlists yet.</div>';
document.getElementById('rows').innerHTML=l.map(function(x){return '<tr><td>'+(x.image_url?'<img src="'+esc(x.image_url)+'" loading="lazy">':'')+'</td><td><a href="/listing/'+encodeURIComponent(x.listing_id)+'">'+esc(x.title)+'</a><div class="muted"><a href="'+esc(x.url)+'" target="_blank" rel="noreferrer">Marketplace</a> · '+esc(x.source_query)+'</div></td><td><span class="pill">'+esc(x.category)+'</span><span class="pill">'+esc(x.condition)+'</span><div class="muted">'+esc(x.classification_source)+'</div></td><td class="price">'+esc(x.latest_price_text||'—')+'<div class="muted">'+esc(x.location||'—')+'</div></td><td class="score">'+Number(x.deal_score).toFixed(1)+'</td><td>'+Math.round(Number(x.score_confidence)*100)+'%</td><td>'+esc(x.last_seen)+'</td></tr>';}).join('');
document.getElementById('notifications').innerHTML=n.length?'<table><tbody>'+n.map(function(x){return '<tr><td><b>'+esc((x.payload&&x.payload.title)||x.listing_id)+'</b><div class="muted">'+esc(x.event_type)+' · score '+esc(x.score)+' · '+esc(x.created_at)+'</div></td></tr>';}).join('')+'</tbody></table>':'<div class="muted">No notification events.</div>';document.getElementById('runs').innerHTML=runs.length?'<table><tbody>'+runs.map(function(x){return '<tr><td>'+esc(x.query)+'<div class="muted">'+esc(x.extracted_count)+' extracted / '+esc(x.normalized_count)+' stored</div></td><td>'+(x.duration_ms==null?'—':Math.round(x.duration_ms)+' ms')+'</td></tr>';}).join('')+'</tbody></table>':'<div class="muted">No search runs.</div>';try{await loadSession()}catch(e){console.error('loadSession error:',e)}}catch(e){console.error('load error:',e);try{await loadSession()}catch(e2){console.error('loadSession error:',e2)}}}
async function loadSession(){try{var panel=document.getElementById('sessionPanel');if(!panel){console.error('sessionPanel element not found');return}var r=await api('/api/session/status');panel.innerHTML='<div class="session-status '+(r.valid?'valid':r.exists?'expired':'unknown')+'">'+(r.valid?'Session valid - searches will work':'Session expired or missing - searches will find limited results')+'</div><div class="muted">Storage: '+esc(r.storage_path)+'</div><button class="primary" onclick="refreshSession()" '+(r.refreshing?'disabled':'')+'>'+(r.refreshing?'Refreshing...':'Refresh Facebook Session')+'</button><div id="sessionMsg" class="muted" style="margin-top:8px;"></div>';}catch(e){var panel2=document.getElementById('sessionPanel');if(panel2)panel2.innerHTML='<div class="session-status unknown">Could not check session status: '+esc(e.message)+'</div>';console.error('loadSession error:',e)}}
document.addEventListener('DOMContentLoaded',function(){setTimeout(function(){load();setInterval(load,30000);},100);});
async function refreshSession(){var btn=document.querySelector('#sessionPanel button');var msg=document.getElementById('sessionMsg');btn.disabled=true;btn.textContent='Opening browser...';msg.textContent='A browser window will open on the server. Please log in to Facebook Marketplace, then return here.';try{var r=await api('/api/session/refresh',{method:'POST'});if(r.success){msg.innerHTML='Session refreshed successfully! <button class="small" onclick="loadSession()">Check Status</button>';btn.textContent='Refresh Facebook Session';btn.disabled=false;await loadSession();}else{msg.textContent='Failed: '+(r.error||'Unknown error');btn.textContent='Refresh Facebook Session';btn.disabled=false;}}catch(e){msg.textContent='Error: '+e.message;btn.textContent='Refresh Facebook Session';btn.disabled=false;}}
function resetForm(){for(const id of ['watchId','name','query','minPrice','maxPrice','targetPrice'])document.getElementById(id).value='';document.getElementById('interval').value=30;document.getElementById('maxItems').value=50;document.getElementById('currency').value='CAD';document.getElementById('formTitle').textContent='Add watchlist';document.getElementById('cancelEdit').hidden=true}function editWatch(id){const x=watchCache.find(v=>v.id===id);if(!x)return;document.getElementById('watchId').value=x.id;document.getElementById('name').value=x.name;document.getElementById('query').value=x.query;document.getElementById('minPrice').value=x.min_price??'';document.getElementById('maxPrice').value=x.max_price??'';document.getElementById('targetPrice').value=x.target_price??'';document.getElementById('interval').value=x.interval_seconds/60;document.getElementById('maxItems').value=x.max_items;document.getElementById('currency').value=x.default_currency;document.getElementById('formTitle').textContent='Edit watchlist';document.getElementById('cancelEdit').hidden=false;window.scrollTo({top:200,behavior:'smooth'})}async function toggleWatch(id,enabled){await api('/api/watchlists/'+id,{method:'PATCH',body:JSON.stringify({enabled})});await load()}async function removeWatch(id){if(!confirm('Delete this watchlist?'))return;await api('/api/watchlists/'+id,{method:'DELETE'});resetForm();await load()}document.getElementById('cancelEdit').onclick=resetForm;document.getElementById('watchForm').onsubmit=async e=>{e.preventDefault();const id=document.getElementById('watchId').value;const body={name:document.getElementById('name').value.trim(),query:document.getElementById('query').value.trim(),min_price:num(document.getElementById('minPrice').value),max_price:num(document.getElementById('maxPrice').value),target_price:num(document.getElementById('targetPrice').value),interval_seconds:Math.max(60,Math.round(Number(document.getElementById('interval').value)*60)),max_items:Number(document.getElementById('maxItems').value),default_currency:document.getElementById('currency').value.trim(),enabled:true};if(id){await api('/api/watchlists/'+id,{method:'PATCH',body:JSON.stringify(body)});}else{await api('/api/watchlists',{method:'POST',body:JSON.stringify(body)});}resetForm();await load()};
</script></body></html>"""


_DETAIL = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Listing detail</title><style>:root{color-scheme:dark;background:#0b0f14;color:#e7edf5;font-family:system-ui,sans-serif}body{margin:0}.wrap{max-width:1100px;margin:auto;padding:24px}.panel{background:#121923;border:1px solid #243044;border-radius:12px;padding:18px;margin:16px 0}.muted{color:#91a0b4}a{color:#70b7ff;text-decoration:none}.meta{display:flex;gap:8px;flex-wrap:wrap}.pill{border:1px solid #34445d;border-radius:999px;padding:3px 8px}svg{width:100%;height:280px;background:#0b111a;border-radius:10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:760px){.grid{grid-template-columns:1fr}}</style></head><body><div class="wrap"><a href="/">← Dashboard</a><div id="content"></div></div><script>const listingId=__LISTING_ID__;const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&','<':'<','>':'>','"':'"'}[c]));async function api(u){const r=await fetch(u);if(!r.ok)throw new Error((await r.json()).detail||r.statusText);return r.json()}function chart(history){const pts=history.filter(x=>x.price_value!=null).reverse();if(!pts.length)return '<div class="muted">No numeric price history.</div>';const w=900,h=240,p=30;const vals=pts.map(x=>Number(x.price_value));const min=Math.min(...vals),max=Math.max(...vals);const span=Math.max(1,max-min);const xy=pts.map((x,i)=>{const px=p+(i*(w-2*p)/Math.max(1,pts.length-1));const py=h-p-((Number(x.price_value)-min)/span)*(h-2*p);return [px,py]});return `<svg viewBox="0 0 ${w} ${h}" role="img"><polyline fill="none" stroke="currentColor" stroke-width="3" points="${xy.map(p=>p.join(',')).join(' ')}"/>${xy.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="4"><title>${esc(pts[i].price_text)} · ${esc(pts[i].captured_at)}</title></circle>`).join('')}<text x="${p}" y="20" fill="currentColor">${esc(max.toFixed(2))}</text><text x="${p}" y="${h-6}" fill="currentColor">${esc(min.toFixed(2))}</text></svg>`;}async function load(){const [detail,history,notifs]=await Promise.all([api(`/api/listings/${listingId}`),api(`/api/listings/${listingId}/history`),api(`/api/notifications?limit=50`)]);const relevant=notifs.filter(n=>n.listing_id===listingId);document.getElementById('content').innerHTML=`<h1>${esc(detail.title)}</h1><div class="meta"><span class="pill">${esc(detail.category)}</span><span class="pill">${esc(detail.condition)}</span><span class="pill">${esc(detail.classification_source)}</span><span class="muted">confidence: ${Math.round(Number(detail.classification_confidence)*100)}%</span></div><div class="muted">${esc(detail.url)}</div><div class="panel"><h2>Price History</h2>${chart(history)}</div><div class="panel"><h2>Score Reasons</h2>${detail.score_reasons&&detail.score_reasons.length?`<ul>${detail.score_reasons.map(r=>`<li>${esc(r)}</li>`).join('')}</ul>`:'<div class="muted">No score reasons.</div>'}</div><div class="panel"><h2>Metadata</h2><div class="grid"><div><b>Price:</b> ${esc(detail.latest_price_text??'—')}<br><b>Currency:</b> ${esc(detail.currency??'—')}<br><b>Location:</b> ${esc(detail.location??'—')}<br><b>Source Query:</b> ${esc(detail.source_query??'—')}<br><b>First Seen:</b> ${esc(detail.first_seen)}<br><b>Last Seen:</b> ${esc(detail.last_seen)}</div><div><b>Deal Score:</b> ${Number(detail.deal_score).toFixed(1)}<br><b>Confidence:</b> ${Math.round(Number(detail.score_confidence)*100)}%<br><b>Description:</b> ${esc(detail.description??'—')}</div></div></div><div class="panel"><h2>Notifications</h2>${relevant.length?`<table><thead><tr><th>Type</th><th>Score</th><th>Time</th></tr></thead><tbody>${relevant.map(n=>`<tr><td>${esc(n.event_type)}</td><td>${esc(n.score)}</td><td>${esc(n.created_at)}</td></tr>`).join('')}</tbody></table>`:'<div class="muted">No notifications for this listing.</div>'}</div>`;}load();</script></body></html>"""


def _watchlist_payload(item: Watchlist) -> dict[str, object]:
    return item.model_dump(mode="json")


# Global variable to track session refresh state
_session_refreshing = False


def create_dashboard_app(db_path: Path) -> FastAPI:
    store = MarketplaceStore(db_path)
    session_path = Path("data/facebook_storage_state.json")

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

    # Session management endpoints
    def _session_file_status() -> tuple[bool, bool]:
        exists = session_path.exists()
        if not exists:
            return False, False
        try:
            with session_path.open() as session_file:
                state = json.load(session_file)
            return True, bool(state.get("cookies") or state.get("origins"))
        except (OSError, ValueError, TypeError):
            return True, False

    @app.get("/api/session/status")
    async def session_status() -> dict[str, object]:
        global _session_refreshing
        exists, valid = await asyncio.to_thread(_session_file_status)
        return {
            "exists": exists,
            "valid": valid,
            "storage_path": str(session_path),
            "refreshing": _session_refreshing
        }

    @app.post("/api/session/refresh")
    async def session_refresh() -> dict[str, object]:
        global _session_refreshing
        if _session_refreshing:
            return {"success": False, "error": "Session refresh already in progress"}

        _session_refreshing = True
        try:
            # Try to extract session from existing browser profiles (Chrome/Chromium first, then Firefox)
            result = await asyncio.to_thread(_extract_facebook_session, session_path)
            if result.get("success"):
                browser = str(result.get("browser", "unknown")).title()
                return {"success": True, "message": f"Extracted session from {browser}: {result.get('cookies_count', 0)} Facebook cookies found"}
            else:
                return {"success": False, "error": result.get("error", "Failed to extract session from browser profiles")}
        finally:
            _session_refreshing = False

    def _extract_facebook_session(target_path: Path) -> dict[str, object]:
        """Extract Facebook cookies from an existing Chrome/Chromium or Firefox profile."""
        try:
            # Try Chromium-based browsers first (more common on Linux)
            chrome_result = _extract_chrome_facebook_session(target_path)
            if chrome_result.get("success"):
                return chrome_result

            # Try Firefox profiles
            firefox_result = _extract_firefox_facebook_session(target_path)
            if firefox_result.get("success"):
                return firefox_result

            return {"success": False, "error": "No Facebook cookies found in any browser profile. Please log in to Facebook in Chrome/Chromium or Firefox first."}
        except Exception as e:
            return {"success": False, "error": f"Error extracting session: {str(e)}"}

    def _extract_chrome_facebook_session(target_path: Path) -> dict[str, object]:
        """Extract Facebook cookies from Chrome/Chromium profile."""
        try:
            # Find Chrome/Chromium profiles
            chrome_profiles = _find_chrome_profiles()
            if not chrome_profiles:
                return {"success": False, "error": "No Chrome/Chromium profiles found"}

            for profile_path in chrome_profiles:
                cookies_db = profile_path / "Cookies"
                if not cookies_db.exists():
                    continue

                # Copy to temp location to avoid locking issues
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                shutil.copy2(cookies_db, tmp_path)

                try:
                    facebook_cookies = _extract_facebook_cookies_from_chrome_db(tmp_path)
                    if facebook_cookies:
                        # Create Playwright storage state
                        storage_state = _create_storage_state(facebook_cookies)
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(target_path, 'w') as f:
                            json.dump(storage_state, f, indent=2)
                        return {"success": True, "cookies_count": len(facebook_cookies), "profile": str(profile_path), "browser": "chrome"}
                finally:
                    tmp_path.unlink(missing_ok=True)

            return {"success": False, "error": "No Facebook cookies found in Chrome/Chromium profiles"}
        except Exception as e:
            return {"success": False, "error": f"Error extracting Chrome session: {str(e)}"}

    def _extract_firefox_facebook_session(target_path: Path) -> dict[str, object]:
        """Extract Facebook cookies from an existing Firefox profile."""
        try:
            # Find Firefox profiles
            firefox_profiles = _find_firefox_profiles()
            if not firefox_profiles:
                return {"success": False, "error": "No Firefox profiles found"}

            # Look for Facebook cookies in each Firefox profile
            for profile_path in firefox_profiles:
                cookies_db = profile_path / "cookies.sqlite"
                if not cookies_db.exists():
                    continue

                # Include SQLite sidecars so recent cookies from a running browser are visible.
                import tempfile
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir) / cookies_db.name
                    shutil.copy2(cookies_db, tmp_path)
                    for suffix in ("-wal", "-shm"):
                        sidecar = cookies_db.with_name(cookies_db.name + suffix)
                        if sidecar.exists():
                            shutil.copy2(sidecar, tmp_path.with_name(tmp_path.name + suffix))
                    facebook_cookies = _extract_facebook_cookies_from_firefox_db(tmp_path)
                    if facebook_cookies:
                        # Create Playwright storage state
                        storage_state = _create_storage_state(facebook_cookies)
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(target_path, 'w') as f:
                            json.dump(storage_state, f, indent=2)
                        return {"success": True, "cookies_count": len(facebook_cookies), "profile": str(profile_path), "browser": "firefox"}

            return {"success": False, "error": "No Facebook cookies found in any Firefox profile"}
        except Exception as e:
            return {"success": False, "error": f"Error extracting Firefox session: {str(e)}"}

    def _find_chrome_profiles() -> list[Path]:
        """Find all Chrome/Chromium profile directories."""
        profiles = []
        # Linux Chrome/Chromium profile locations
        chrome_dirs = [
            Path.home() / ".config" / "chromium",
            Path.home() / ".config" / "google-chrome",
            Path.home() / ".config" / "google-chrome-beta",
            Path.home() / ".config" / "google-chrome-unstable",
            Path.home() / ".var" / "app" / "org.chromium.Chromium" / "config" / "chromium",  # Flatpak
            Path.home() / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome",  # Flatpak
        ]

        for chrome_dir in chrome_dirs:
            if not chrome_dir.exists():
                continue
            # Check for Default profile and any additional profiles
            for item in chrome_dir.iterdir():
                if item.is_dir() and (item.name == "Default" or item.name.startswith("Profile ")):
                    if (item / "Cookies").exists():
                        profiles.append(item)
        return profiles

    def _find_firefox_profiles() -> list[Path]:
        """Find all Firefox profile directories."""
        profiles = []
        # Linux Firefox profile locations
        firefox_dirs = [
            Path.home() / ".mozilla" / "firefox",
            Path.home() / ".config" / "mozilla" / "firefox",
            Path.home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",  # Flatpak
        ]

        for firefox_dir in firefox_dirs:
            if not firefox_dir.exists():
                continue
            # Read profiles.ini
            profiles_ini = firefox_dir / "profiles.ini"
            if profiles_ini.exists():
                import configparser
                config = configparser.ConfigParser()
                config.read(profiles_ini)
                for section in config.sections():
                    if config.has_option(section, "Path"):
                        path = config[section]["Path"]
                        is_relative = config.getboolean(section, "IsRelative", fallback=True)
                        if is_relative:
                            profile_path = firefox_dir / path
                        else:
                            profile_path = Path(path)
                        if profile_path.exists():
                            profiles.append(profile_path)
        return profiles

    def _extract_facebook_cookies_from_chrome_db(db_path: Path) -> list[dict]:
        """Extract Facebook cookies from Chrome/Chromium Cookies database."""
        facebook_cookies = []

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Chrome cookies table: creation_utc, host_key, name, value, path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires, is_persistent, priority, samesite, source_scheme, source_port, has_cross_site_ancestor
            cursor.execute(
                "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly, samesite FROM cookies WHERE host_key LIKE '%facebook%'"
            )
            for row in cursor.fetchall():
                if not row["value"]:
                    continue
                cookie = {
                    "name": row["name"],
                    "value": row["value"],
                    "domain": row["host_key"].lstrip("."),
                    "path": row["path"],
                    "secure": bool(row["is_secure"]),
                    "httpOnly": bool(row["is_httponly"]),
                    "sameSite": _convert_chrome_samesite(row["samesite"]),
                }
                if row["expires_utc"] and row["expires_utc"] > 0:
                    # Convert Chrome timestamp (microseconds since Jan 1, 1601) to Unix timestamp (seconds since Jan 1, 1970)
                    cookie["expires"] = (row["expires_utc"] / 1_000_000) - 11644473600
                facebook_cookies.append(cookie)

            conn.close()
        except Exception as e:
            print(f"Error reading Chrome cookies database: {e}")

        return facebook_cookies

    def _extract_facebook_cookies_from_firefox_db(db_path: Path) -> list[dict]:
        """Extract Facebook cookies from Firefox cookies.sqlite."""
        facebook_cookies = []

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Firefox cookies table schema: name, value, host, path, expiry, lastAccessed, creationTime, isSecure, isHttpOnly, inBrowserElement, sameSite, rawSameSite, schemeMap
            cursor.execute(
                "SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite "
                "FROM moz_cookies WHERE host LIKE '%facebook.com'"
            )
            for row in cursor.fetchall():
                cookie = {
                    "name": row["name"],
                    "value": row["value"],
                    "domain": row["host"],
                    "path": row["path"],
                    "secure": bool(row["isSecure"]),
                    "httpOnly": bool(row["isHttpOnly"]),
                    "sameSite": _convert_samesite(row["sameSite"]),
                }
                expiry = row["expiry"]
                if expiry and expiry > 0:
                    cookie["expires"] = expiry / 1000 if expiry > 10_000_000_000 else expiry
                facebook_cookies.append(cookie)

            conn.close()
        except Exception as e:
            print(f"Error reading Firefox cookies database: {e}")

        return facebook_cookies

    def _convert_chrome_samesite(samesite_val) -> str:
        """Convert Chrome sameSite value to Playwright format."""
        # Chrome: -1 = default/unset, 0 = no restriction, 1 = lax, 2 = strict
        if samesite_val <= 0:
            return "None"
        elif samesite_val == 1:
            return "Lax"
        elif samesite_val == 2:
            return "Strict"
        return "Lax"

    def _convert_samesite(samesite_val) -> str:
        """Convert Firefox sameSite value to Playwright format."""
        # Firefox: 0 = no restriction, 1 = lax, 2 = strict
        if samesite_val == 0:
            return "None"
        elif samesite_val == 1:
            return "Lax"
        elif samesite_val == 2:
            return "Strict"
        return "Lax"

    def _create_storage_state(cookies: list[dict]) -> dict:
        """Create Playwright storage state from cookies."""
        # Convert to Playwright format
        pw_cookies = []
        for c in cookies:
            pw_cookie = {
                "name": c["name"],
                "value": c["value"],
                "domain": c["domain"],
                "path": c["path"],
                "secure": c["secure"],
                "httpOnly": c["httpOnly"],
                "sameSite": c["sameSite"],
            }
            if "expires" in c:
                pw_cookie["expires"] = c["expires"]
            pw_cookies.append(pw_cookie)

        return {
            "cookies": pw_cookies,
            "origins": []
        }

    return app
