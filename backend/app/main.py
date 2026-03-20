import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.auth import router as auth_router
from app.services.auth.middleware import require_session
from app.services.auth.session_store import session_store
from app.services.database import LocalDatabase
from app.services.pihole.api_client import (
    PiholeAuthError,
    PiholeConnectionError,
)
from app.services.sources import TrackerSource, get_tracker_sources
import app.services.sync_manager as sync_manager

logger = logging.getLogger(__name__)

sources: list[TrackerSource]
db: LocalDatabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    global sources, db

    sources = get_tracker_sources()
    db = LocalDatabase()

    # Initialize all tracker sources (download data, open connections, etc.)
    for source in sources:
        await source.initialize()

    # Register source-specific API routes (debug/diagnostic endpoints)
    for source in sources:
        router = source.api_router()
        if router is not None:
            app.include_router(router)

    await db.init()
    await db.flag_heuristic_uncategorized_for_reenrichment()

    # If there's an active session (e.g. from a quick restart), resume sync
    active = session_store.get_active()
    if active:
        await sync_manager.start_sync_service(active, sources, db)

    yield

    await sync_manager.stop_sync_service()


app = FastAPI(
    title="pihole-wtm",
    description="Pi-hole dashboard enriched with WhoTracksMe tracker intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes — no session required
app.include_router(auth_router)


@app.get("/api/health", dependencies=[Depends(require_session)])
async def health() -> dict[str, Any]:
    sync_status = await db.get_sync_status()
    source_statuses = [
        {
            "name": source.source_name,
            "label": source.label,
            **(await source.health_check()),
        }
        for source in sources
    ]
    return {
        "status": "ok",
        "pihole_api_url": sync_manager.pihole._base_url if sync_manager.pihole else None,
        "version": "0.1.0",
        "sources": source_statuses,
        **sync_status,
    }


@app.get("/api/pihole/test", dependencies=[Depends(require_session)])
async def pihole_test() -> dict[str, Any]:
    if sync_manager.pihole is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    try:
        return await sync_manager.pihole.test_connection()
    except PiholeAuthError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except PiholeConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/pihole/summary", dependencies=[Depends(require_session)])
async def pihole_summary() -> dict[str, Any]:
    if sync_manager.pihole is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    try:
        summary = await sync_manager.pihole.get_summary()
        return summary.model_dump()
    except (PiholeAuthError, PiholeConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/queries", dependencies=[Depends(require_session)])
async def queries(
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int | None = Query(default=None),
    status_type: Literal["allowed", "blocked"] | None = Query(default=None),
    tracker_only: bool = Query(default=False),
) -> dict[str, Any]:
    results, next_cursor = await db.fetch_queries(
        limit=limit,
        cursor=cursor,
        status_type=status_type,
        tracker_only=tracker_only,
    )
    return {"queries": results, "cursor": next_cursor}


async def _get_exclusions() -> dict[str, list[str]]:
    """Read user exclusion config from the database."""
    raw = await db.get_all_config()
    return {
        "excluded_categories": json.loads(raw.get("excluded_categories", "[]")),
        "excluded_companies": json.loads(raw.get("excluded_companies", "[]")),
        "excluded_domains": json.loads(raw.get("excluded_domains", "[]")),
    }


@app.get("/api/stats/trackers", dependencies=[Depends(require_session)])
async def stats_trackers(
    hours: int = Query(default=24, ge=1, le=168),
    client_ip: str | None = Query(default=None),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_tracker_stats(hours=hours, client_ip=client_ip, **excl)


@app.get("/api/stats/timeline", dependencies=[Depends(require_session)])
async def stats_timeline(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_timeline_stats(hours=hours, **excl)


@app.get("/api/stats/timeline/clients", dependencies=[Depends(require_session)])
async def stats_timeline_clients(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_client_timeline_stats(hours=hours, **excl)


@app.get("/api/stats/domains", dependencies=[Depends(require_session)])
async def stats_domains(
    hours: int = Query(default=24, ge=1, le=168),
    category: str | None = Query(default=None),
    company: str | None = Query(default=None),
    client_ip: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    domain_exact: bool = Query(default=False),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_domain_stats(
        hours=hours, category=category, company=company,
        client_ip=client_ip, domain=domain, domain_exact=domain_exact, **excl,
    )


@app.get("/api/domains/search", dependencies=[Depends(require_session)])
async def search_domains(
    q: str = Query(min_length=2),
    hours: int = Query(default=24, ge=1, le=168),
) -> list[str]:
    return await db.search_domains(query=q, hours=hours)


@app.get("/api/stats/clients", dependencies=[Depends(require_session)])
async def stats_clients(
    hours: int = Query(default=24, ge=1, le=168),
    category: str | None = Query(default=None),
    company: str | None = Query(default=None),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_client_stats(hours=hours, category=category, company=company, **excl)


@app.get("/api/config", dependencies=[Depends(require_session)])
async def get_config() -> dict[str, Any]:
    """Return all user configuration as a structured object."""
    raw = await db.get_all_config()
    return {
        "excluded_categories": json.loads(raw.get("excluded_categories", "[]")),
        "excluded_companies": json.loads(raw.get("excluded_companies", "[]")),
        "excluded_domains": json.loads(raw.get("excluded_domains", "[]")),
    }


@app.put("/api/config", dependencies=[Depends(require_session)])
async def put_config(request: Request) -> dict[str, str]:
    """Update user configuration. Accepts partial updates."""
    body = await request.json()
    items: dict[str, str] = {}
    for key in ("excluded_categories", "excluded_companies", "excluded_domains"):
        if key in body:
            if not isinstance(body[key], list):
                raise HTTPException(status_code=422, detail=f"{key} must be an array")
            items[key] = json.dumps(body[key])
    if items:
        await db.set_config_bulk(items)
    return {"status": "ok"}


@app.get("/api/config/options", dependencies=[Depends(require_session)])
async def config_options() -> dict[str, Any]:
    """Return the available categories and companies from stored data."""
    categories = await db.get_available_categories()
    companies = await db.get_available_companies()
    return {"categories": categories, "companies": companies}


@app.get("/api/clients", dependencies=[Depends(require_session)])
async def get_clients() -> dict[str, Any]:
    """Return all distinct client IPs with query counts and assigned names."""
    return {"clients": await db.get_clients()}


@app.put("/api/clients/{client_ip:path}", dependencies=[Depends(require_session)])
async def set_client(client_ip: str, request: Request) -> dict[str, str]:
    """Set or update a friendly name for a client IP."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if len(name) > 64:
        raise HTTPException(status_code=422, detail="name must be 64 characters or fewer")
    await db.set_client_name(client_ip, name)
    return {"status": "ok"}


@app.delete("/api/clients/{client_ip:path}", dependencies=[Depends(require_session)])
async def delete_client(client_ip: str) -> dict[str, str]:
    """Remove a client name mapping."""
    await db.delete_client_name(client_ip)
    return {"status": "ok"}


@app.post("/api/admin/reenrich", dependencies=[Depends(require_session)])
async def admin_reenrich() -> dict[str, Any]:
    """Flag heuristic and rdap_failed domains for re-enrichment."""
    count = await db.flag_for_reenrichment()
    return {"status": "ok", "flagged": count}


@app.post("/api/admin/reset", dependencies=[Depends(require_session)])
async def admin_reset() -> dict[str, str]:
    await db.reset()
    return {"status": "ok"}


@app.get("/api/debug/raw-query", dependencies=[Depends(require_session)])
async def debug_raw_query(status: str = "GRAVITY") -> dict[str, Any]:
    """Returns the raw Pi-hole API response for one query of the given status."""
    if sync_manager.pihole is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    data = await sync_manager.pihole._get("/api/queries", params={"length": 50})  # noqa: SLF001
    pi_queries = data.get("queries", [])
    match = next(
        (q for q in pi_queries if q.get("status") == status),
        pi_queries[0] if pi_queries else {},
    )
    return {"raw": match, "all_fields": list(match.keys()) if match else []}


@app.get("/api/debug/pihole", dependencies=[Depends(require_session)])
async def debug_pihole(path: str) -> dict[str, Any]:
    """Proxy a raw authenticated GET request to the Pi-hole API for exploration."""
    if sync_manager.pihole is None:
        raise HTTPException(status_code=503, detail="Sync service not running")
    return await sync_manager.pihole._get(f"/{path.lstrip('/')}")  # noqa: SLF001
