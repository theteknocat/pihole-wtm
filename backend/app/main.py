from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.pihole.api_client import PiholeApiClient, PiholeAuthError, PiholeConnectionError

pihole = PiholeApiClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
