import asyncio
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.database import LocalDatabase
from app.services.disconnect.loader import DisconnectDB
from app.services.pihole.api_client import (
    PiholeApiClient,
    PiholeAuthError,
    PiholeConnectionError,
)
from app.services.sync import run_sync_loop
from app.services.trackerdb.enricher import TrackerEnricher
from app.services.trackerdb.loader import ensure_trackerdb, trackerdb_exists
from app.services.trackerdb.repository import TrackerRepository

pihole: PiholeApiClient
tracker_repo: TrackerRepository
enricher: TrackerEnricher
disconnect_db: DisconnectDB
db: LocalDatabase


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pihole, tracker_repo, enricher, disconnect_db, db

    pihole = PiholeApiClient()
    tracker_repo = TrackerRepository()
    enricher = TrackerEnricher(tracker_repo)
    disconnect_db = DisconnectDB()
    db = LocalDatabase()

    await ensure_trackerdb()
    await disconnect_db.load()
    await db.init()

    sync_task = asyncio.create_task(run_sync_loop(pihole, enricher, disconnect_db, db))

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
    return {
        "status": "ok",
        "pihole_api_url": settings.pihole_api_url,
        "trackerdb_loaded": trackerdb_exists(),
        "version": "0.1.0",
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


@app.get("/api/trackerdb/status")
async def trackerdb_status() -> dict[str, Any]:
    return {
        "loaded": trackerdb_exists(),
        "cache": enricher.cache_info,
        "categories": await tracker_repo.get_categories(),
    }


@app.get("/api/trackerdb/lookup")
async def trackerdb_lookup(domain: str) -> dict[str, Any]:
    result = await enricher.enrich(domain)
    if result is None:
        return {"domain": domain, "found": False}
    return {"domain": domain, "found": True, **result.model_dump()}


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
