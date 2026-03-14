from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.pihole.api_client import PiholeApiClient, PiholeAuthError, PiholeConnectionError
from app.services.trackerdb.enricher import TrackerEnricher
from app.services.trackerdb.loader import TrackerDbLoadError, ensure_trackerdb, trackerdb_exists
from app.services.trackerdb.repository import TrackerRepository

pihole = PiholeApiClient()
tracker_repo = TrackerRepository()
enricher = TrackerEnricher(tracker_repo)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "pihole_api_url": settings.pihole_api_url,
        "trackerdb_loaded": trackerdb_exists(),
        "version": "0.1.0",
    }


@app.get("/api/pihole/test")
async def pihole_test() -> dict:
    try:
        return await pihole.test_connection()
    except PiholeAuthError as e:
        return {"connected": False, "error": str(e)}
    except PiholeConnectionError as e:
        return {"connected": False, "error": str(e)}


@app.get("/api/pihole/summary")
async def pihole_summary() -> dict:
    try:
        summary = await pihole.get_summary()
        return summary.model_dump()
    except (PiholeAuthError, PiholeConnectionError) as e:
        return {"error": str(e)}


@app.get("/api/trackerdb/status")
async def trackerdb_status() -> dict:
    return {
        "loaded": trackerdb_exists(),
        "cache": enricher.cache_info,
        "categories": await tracker_repo.get_categories(),
    }


@app.get("/api/trackerdb/lookup")
async def trackerdb_lookup(domain: str) -> dict:
    result = await enricher.enrich(domain)
    if result is None:
        return {"domain": domain, "found": False}
    return {"domain": domain, "found": True, **result.model_dump()}
