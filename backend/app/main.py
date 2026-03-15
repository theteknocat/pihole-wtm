import asyncio
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.pihole import EnrichedQuery, RawQuery
from app.services.pihole.api_client import (
    BLOCKED_STATUSES,
    PiholeApiClient,
    PiholeAuthError,
    PiholeConnectionError,
)
from app.services.stats import get_tracker_stats
from app.services.trackerdb.enricher import TrackerEnricher
from app.services.trackerdb.loader import ensure_trackerdb, trackerdb_exists
from app.services.trackerdb.repository import TrackerRepository

pihole: PiholeApiClient
tracker_repo: TrackerRepository
enricher: TrackerEnricher


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pihole, tracker_repo, enricher
    pihole = PiholeApiClient()
    tracker_repo = TrackerRepository()
    enricher = TrackerEnricher(tracker_repo)
    await ensure_trackerdb()
    yield
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
    return {
        "status": "ok",
        "pihole_api_url": settings.pihole_api_url,
        "trackerdb_loaded": trackerdb_exists(),
        "version": "0.1.0",
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


async def _enrich(raw: list[RawQuery]) -> list[EnrichedQuery]:
    tracker_results = await asyncio.gather(*[enricher.enrich(q.domain) for q in raw])
    return [
        EnrichedQuery(
            **q.model_dump(),
            tracker_name=t.tracker_name if t else None,
            category=t.category if t else None,
            company_name=t.company_name if t else None,
            company_country=t.company_country if t else None,
        )
        for q, t in zip(raw, tracker_results)
    ]


@app.get("/api/queries")
async def queries(
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int | None = Query(default=None),
    status_type: Literal["allowed", "blocked"] | None = Query(default=None),
    tracker_only: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        # Fast path: no filtering needed
        if status_type is None and not tracker_only:
            raw_queries, next_cursor = await pihole.get_queries(limit=limit, cursor=cursor)
            return {"queries": [q.model_dump() for q in await _enrich(raw_queries)], "cursor": next_cursor}

        # Filtered path: page through results, enrich as we go, apply filters
        results: list[EnrichedQuery] = []
        fetch_cursor = cursor
        for _ in range(20):  # cap at 2000 queries examined
            batch, fetch_cursor = await pihole.get_queries(limit=100, cursor=fetch_cursor)
            if not batch:
                break
            for q in await _enrich(batch):
                if status_type == "blocked" and q.status not in BLOCKED_STATUSES:
                    continue
                if status_type == "allowed" and q.status in BLOCKED_STATUSES:
                    continue
                if tracker_only and q.category is None:
                    continue
                results.append(q)
                if len(results) >= limit:
                    break
            if len(results) >= limit or fetch_cursor is None:
                break

    except (PiholeAuthError, PiholeConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {"queries": [q.model_dump() for q in results], "cursor": None}


@app.get("/api/stats/trackers")
async def stats_trackers(
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    try:
        return await get_tracker_stats(pihole, enricher, hours=hours)
    except (PiholeAuthError, PiholeConnectionError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


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
