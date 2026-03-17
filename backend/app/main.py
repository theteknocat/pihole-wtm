import asyncio
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
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


@app.get("/api/stats/trackers")
async def stats_trackers(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    return await db.fetch_tracker_stats(hours=hours)


@app.get("/api/stats/domains")
async def stats_domains(
    hours: int = Query(default=24, ge=1, le=168),
    category: str | None = Query(default=None),
    company: str | None = Query(default=None),
) -> dict[str, Any]:
    return await db.fetch_domain_stats(hours=hours, category=category, company=company)


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
