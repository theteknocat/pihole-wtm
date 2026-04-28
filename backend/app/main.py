import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version
from typing import Any, Literal, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel

import app.services.sync_manager as sync_manager
from app.log import setup_logging
from app.routers.auth import router as auth_router
from app.services.auth.middleware import require_session
from app.services.auth.session_store import session_store
from app.services.database import LocalDatabase
from app.services.pihole.api_client import (
    PiholeAuthError,
    PiholeConnectionError,
)
from app.services.sources import TrackerSource, get_tracker_sources

setup_logging()
logger = logging.getLogger(__name__)

sources: list[TrackerSource]
db: LocalDatabase


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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

    # Start sync: prefer env var credentials (always-on), fall back to active session
    if not await sync_manager.start_sync_from_env(sources, db):
        active = session_store.get_active()
        if active:
            await sync_manager.start_sync_from_session(active, sources, db)

    yield

    await sync_manager.stop_sync_service()
    await db.close()


app = FastAPI(
    title="pihole-wtm",
    description="Pi-hole dashboard enriched with WhoTracksMe tracker intelligence",
    version=pkg_version("pihole-wtm"),
    lifespan=lifespan,
)

# Auth routes — no session required
app.include_router(auth_router)


@app.get("/api/health", dependencies=[Depends(require_session)])
async def health() -> dict[str, Any]:
    sync_status = await db.get_sync_status()
    data_range = await db.get_data_range()
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
        "version": pkg_version("pihole-wtm"),
        "sources": source_statuses,
        "sync_active": sync_manager.sync_task is not None,
        "sync_source": sync_manager.sync_source.value if sync_manager.sync_source else None,
        **sync_status,
        **data_range,
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
    group_consecutive: bool = Query(default=False),
) -> dict[str, Any]:
    if group_consecutive:
        results = await db.fetch_queries_grouped(
            limit=limit,
            status_type=status_type,
            tracker_only=tracker_only,
        )
        return {"queries": results}
    results, next_cursor = await db.fetch_queries(
        limit=limit,
        cursor=cursor,
        status_type=status_type,
        tracker_only=tracker_only,
    )
    return {"queries": results, "cursor": next_cursor}


_EXCLUSION_KEYS = ("excluded_categories", "excluded_companies", "excluded_domains")


@app.get("/api/stats/trackers", dependencies=[Depends(require_session)])
async def stats_trackers(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
    client_ip: list[str] = Query(default=[]),  # noqa: B008
    include_timeline: bool = Query(default=False),
) -> dict[str, Any]:
    return await db.fetch_tracker_stats(
        hours=hours,
        end_ts=end_ts,
        client_ips=client_ip or None,
        include_timeline=include_timeline,
    )


@app.get("/api/stats/timeline", dependencies=[Depends(require_session)])
async def stats_timeline(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
) -> dict[str, Any]:
    return await db.fetch_timeline_stats(hours=hours, end_ts=end_ts)


@app.get("/api/stats/timeline/clients", dependencies=[Depends(require_session)])
async def stats_timeline_clients(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
) -> dict[str, Any]:
    return await db.fetch_client_timeline_stats(hours=hours, end_ts=end_ts)


@app.get("/api/stats/domains", dependencies=[Depends(require_session)])
async def stats_domains(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
    category: str | None = Query(default=None),
    company: str | None = Query(default=None),
    client_ip: list[str] = Query(default=[]),  # noqa: B008
    domain: str | None = Query(default=None),
    domain_exact: bool = Query(default=False),
) -> dict[str, Any]:
    return await db.fetch_domain_stats(
        hours=hours,
        end_ts=end_ts,
        category=category,
        company=company,
        client_ips=client_ip or None,
        domain=domain,
        domain_exact=domain_exact,
    )


@app.get("/api/domains/search", dependencies=[Depends(require_session)])
async def search_domains(
    q: str = Query(min_length=2),
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
) -> list[str]:
    return await db.search_domains(query=q, hours=hours, end_ts=end_ts)


@app.get("/api/stats/clients", dependencies=[Depends(require_session)])
async def stats_clients(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
    category: str | None = Query(default=None),
    company: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    include_timeline: bool = Query(default=False),
) -> dict[str, Any]:
    return await db.fetch_client_stats(
        hours=hours, end_ts=end_ts, category=category, company=company, domain=domain,
        include_timeline=include_timeline,
    )


@app.get("/api/settings/options", dependencies=[Depends(require_session)])
async def settings_options(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
) -> dict[str, Any]:
    """Return categories and companies that have queries in the active time window,
    after applying user exclusions."""
    categories = await db.get_available_categories(hours=hours, end_ts=end_ts)
    companies = await db.get_available_companies(hours=hours, end_ts=end_ts)
    return {"categories": categories, "companies": companies}


# ---- Settings (all stored in user_config, auto-saved from the UI) -----------

# Key → (default, min, max) for each integer setting.
_INT_SETTINGS: dict[str, tuple[int, int, int]] = {
    "sync_interval_seconds": (60, 10, 3600),
    "data_retention_days": (7, 1, 365),
    "trackerdb_update_interval_hours": (24, 0, 720),
    "disconnect_update_interval_hours": (24, 0, 720),
}


@app.get("/api/settings", dependencies=[Depends(require_session)])
async def get_settings() -> dict[str, Any]:
    """Return all settings: integer operational settings + exclusion lists."""
    raw = await db.get_all_config()
    result: dict[str, Any] = {}
    for key, (default, _, _) in _INT_SETTINGS.items():
        val = raw.get(key)
        result[key] = int(val) if val is not None else default
    for key in _EXCLUSION_KEYS:
        result[key] = json.loads(raw.get(key, "[]"))
    return result


@app.put("/api/settings/{key}", dependencies=[Depends(require_session)])
async def put_setting(key: str, request: Request) -> dict[str, str]:
    """Update a single setting. Integer settings expect { "value": <int> },
    exclusion lists expect { "value": [<strings>] }."""
    body = await request.json()
    value = body.get("value")

    if key in _INT_SETTINGS:
        if not isinstance(value, int):
            raise HTTPException(status_code=422, detail="value must be an integer")
        _, min_val, max_val = _INT_SETTINGS[key]
        if value < min_val or value > max_val:
            raise HTTPException(
                status_code=422, detail=f"{key} must be between {min_val} and {max_val}"
            )
        await db.set_config(key, str(value))
    elif key in _EXCLUSION_KEYS:
        if not isinstance(value, list):
            raise HTTPException(status_code=422, detail="value must be an array")
        await db.set_config(key, json.dumps(value))
    else:
        raise HTTPException(status_code=404, detail=f"Unknown setting: {key}")

    return {"status": "ok"}


@app.get("/api/clients", dependencies=[Depends(require_session)])
async def get_clients(
    hours: int = Query(default=24, ge=1, le=2160),
    end_ts: float | None = Query(default=None),
) -> dict[str, Any]:
    """Return client IPs with query counts in the active time window,
    after applying user exclusions."""
    return {"clients": await db.get_clients(hours=hours, end_ts=end_ts)}


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


# ---- Device groups ----------------------------------------------------------

class DeviceGroupRequest(BaseModel):
    name: str
    member_ips: list[str]


@app.get("/api/device-groups", dependencies=[Depends(require_session)])
async def get_device_groups() -> dict[str, Any]:
    """Return all device groups with their members."""
    return {"groups": await db.get_device_groups()}


@app.post("/api/device-groups", dependencies=[Depends(require_session)])
async def create_device_group(body: DeviceGroupRequest) -> dict[str, Any]:
    """Create a new device group."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if len(name) > 64:
        raise HTTPException(status_code=422, detail="name must be 64 characters or fewer")
    try:
        group_id = await db.create_device_group(name, body.member_ips)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"status": "ok", "id": group_id}


@app.put("/api/device-groups/{group_id}", dependencies=[Depends(require_session)])
async def update_device_group(group_id: int, body: DeviceGroupRequest) -> dict[str, str]:
    """Update a device group's name and member list."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if len(name) > 64:
        raise HTTPException(status_code=422, detail="name must be 64 characters or fewer")
    try:
        found = await db.update_device_group(group_id, name, body.member_ips)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not found:
        raise HTTPException(status_code=404, detail="Device group not found")
    return {"status": "ok"}


@app.delete("/api/device-groups/{group_id}", dependencies=[Depends(require_session)])
async def delete_device_group(group_id: int) -> dict[str, str]:
    """Delete a device group."""
    found = await db.delete_device_group(group_id)
    if not found:
        raise HTTPException(status_code=404, detail="Device group not found")
    return {"status": "ok"}


@app.post("/api/admin/reenrich", dependencies=[Depends(require_session)])
@app.post("/api/admin/reenrich/{domain}", dependencies=[Depends(require_session)])
async def admin_reenrich(domain: str | None = None) -> dict[str, Any]:
    """Flag heuristic/rdap_failed domains for re-enrichment. Omit domain to flag all."""
    count = await db.flag_for_reenrichment(domain)
    if domain is not None and count == 0:
        raise HTTPException(status_code=404, detail="Domain not found")
    return {"status": "ok", "flagged": count}


@app.post("/api/admin/reset", dependencies=[Depends(require_session)])
async def admin_reset() -> dict[str, str]:
    await db.reset()
    sync_manager.trigger_sync()
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
    return cast(dict[str, Any], await sync_manager.pihole._get(f"/{path.lstrip('/')}"))  # noqa: SLF001
