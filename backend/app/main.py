import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.database import LocalDatabase
from app.services.pihole.api_client import (
    PiholeApiClient,
    PiholeAuthError,
    PiholeConnectionError,
)
from app.services.sources import TrackerSource, get_tracker_sources
from app.services.sync import run_sync_loop

pihole: PiholeApiClient
sources: list[TrackerSource]
db: LocalDatabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pihole, sources, db

    pihole = PiholeApiClient()
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

    sync_task = asyncio.create_task(run_sync_loop(pihole, sources, db))

    yield

    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    await pihole.close()


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


@app.get("/api/health")
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
        "pihole_api_url": settings.pihole_api_url,
        "version": "0.1.0",
        "sources": source_statuses,
        **sync_status,
    }


@app.get("/api/pihole/test")
async def pihole_test() -> dict[str, Any]:
    try:
        return await pihole.test_connection()
    except PiholeAuthError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except PiholeConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/pihole/summary")
async def pihole_summary() -> dict[str, Any]:
    try:
        summary = await pihole.get_summary()
        return summary.model_dump()
    except (PiholeAuthError, PiholeConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/api/queries")
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


@app.get("/api/stats/trackers")
async def stats_trackers(
    hours: int = Query(default=24, ge=1, le=168),
    client_ip: str | None = Query(default=None),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_tracker_stats(hours=hours, client_ip=client_ip, **excl)


@app.get("/api/stats/timeline")
async def stats_timeline(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_timeline_stats(hours=hours, **excl)


@app.get("/api/stats/domains")
async def stats_domains(
    hours: int = Query(default=24, ge=1, le=168),
    category: str | None = Query(default=None),
    company: str | None = Query(default=None),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_domain_stats(hours=hours, category=category, company=company, **excl)


@app.get("/api/stats/clients")
async def stats_clients(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    excl = await _get_exclusions()
    return await db.fetch_client_stats(hours=hours, **excl)


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    """Return all user configuration as a structured object."""
    raw = await db.get_all_config()
    return {
        "excluded_categories": json.loads(raw.get("excluded_categories", "[]")),
        "excluded_companies": json.loads(raw.get("excluded_companies", "[]")),
        "excluded_domains": json.loads(raw.get("excluded_domains", "[]")),
    }


@app.put("/api/config")
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


@app.get("/api/config/options")
async def config_options() -> dict[str, Any]:
    """Return the available categories and companies from stored data."""
    categories = await db.get_available_categories()
    companies = await db.get_available_companies()
    return {"categories": categories, "companies": companies}


@app.get("/api/clients")
async def get_clients() -> dict[str, Any]:
    """Return all distinct client IPs with query counts and assigned names."""
    return {"clients": await db.get_clients()}


@app.put("/api/clients/{client_ip:path}")
async def set_client(client_ip: str, request: Request) -> dict[str, str]:
    """Set or update a friendly name for a client IP."""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    await db.set_client_name(client_ip, name)
    return {"status": "ok"}


@app.delete("/api/clients/{client_ip:path}")
async def delete_client(client_ip: str) -> dict[str, str]:
    """Remove a client name mapping."""
    await db.delete_client_name(client_ip)
    return {"status": "ok"}


@app.post("/api/admin/reenrich")
async def admin_reenrich() -> dict[str, Any]:
    """Flag heuristic and rdap_failed domains for re-enrichment."""
    count = await db.flag_for_reenrichment()
    return {"status": "ok", "flagged": count}


@app.post("/api/admin/reset")
async def admin_reset() -> dict[str, str]:
    await db.reset()
    return {"status": "ok"}


@app.get("/api/debug/raw-query")
async def debug_raw_query(status: str = "GRAVITY") -> dict[str, Any]:
    """Returns the raw Pi-hole API response for one query of the given status."""
    data = await pihole._get("/api/queries", params={"length": 50})  # noqa: SLF001
    pi_queries = data.get("queries", [])
    match = next(
        (q for q in pi_queries if q.get("status") == status),
        pi_queries[0] if pi_queries else {},
    )
    return {"raw": match, "all_fields": list(match.keys()) if match else []}


@app.get("/api/debug/pihole")
async def debug_pihole(path: str) -> dict[str, Any]:
    """Proxy a raw authenticated GET request to the Pi-hole API for exploration."""
    return await pihole._get(f"/{path.lstrip('/')}")  # noqa: SLF001
