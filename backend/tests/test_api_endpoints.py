"""
Tests for all API endpoints in app/main.py.

Uses the `client` + `db` fixtures from conftest.py.
When both are declared in the same test, pytest shares the same `db`
instance, so data seeded via `db` is visible to the HTTP client.

sync_manager module-level attributes (pihole, sync_task, sync_source)
are patched where endpoints depend on them.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

import app.services.sync_manager as sync_manager_module
from app.services.database import LocalDatabase
from app.services.sync_manager import SyncSource


# ---------------------------------------------------------------------------
# Seed helpers (same pattern as test_database.py)
# ---------------------------------------------------------------------------

async def _domain(
    db: LocalDatabase,
    domain: str,
    *,
    category: str | None = None,
    company_name: str | None = None,
    enrichment_source: str = "trackerdb",
) -> None:
    await db.upsert_domains([domain])
    await db.batch_update_domain_enrichment([{
        "domain": domain,
        "tracker_name": None,
        "category": category,
        "company_name": company_name,
        "company_country": None,
        "source": enrichment_source,
    }])


async def _query(
    db: LocalDatabase,
    id: int,
    domain: str,
    timestamp: float,
    *,
    status: str = "FORWARDED",
    client_ip: str = "192.168.1.1",
) -> None:
    await db.insert_queries([{
        "id": id, "timestamp": timestamp, "domain": domain,
        "client_ip": client_ip, "status": status,
        "query_type": "A", "reply_type": "IP",
        "reply_time": 0.001, "upstream": None, "list_id": None,
    }])


def _mock_pihole(base_url: str = "http://pihole.local") -> MagicMock:
    mock = MagicMock()
    mock._base_url = base_url
    return mock


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

async def test_health_returns_ok(client: AsyncClient) -> None:
    with patch.object(sync_manager_module, "pihole", _mock_pihole()), \
         patch.object(sync_manager_module, "sync_task", MagicMock()), \
         patch.object(sync_manager_module, "sync_source", SyncSource.SESSION):
        res = await client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["sync_active"] is True
    assert body["sync_source"] == "session"
    assert body["pihole_api_url"] == "http://pihole.local"


async def test_health_no_sync_running(client: AsyncClient) -> None:
    with patch.object(sync_manager_module, "pihole", None), \
         patch.object(sync_manager_module, "sync_task", None), \
         patch.object(sync_manager_module, "sync_source", None):
        res = await client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["sync_active"] is False
    assert body["pihole_api_url"] is None


# ---------------------------------------------------------------------------
# GET /api/pihole/test
# ---------------------------------------------------------------------------

async def test_pihole_test_returns_connected(client: AsyncClient) -> None:
    mock = _mock_pihole()
    mock.test_connection = AsyncMock(return_value={"connected": True, "version": "6.0"})
    with patch.object(sync_manager_module, "pihole", mock):
        res = await client.get("/api/pihole/test")
    assert res.status_code == 200
    assert res.json()["connected"] is True


async def test_pihole_test_503_when_sync_not_running(client: AsyncClient) -> None:
    with patch.object(sync_manager_module, "pihole", None):
        res = await client.get("/api/pihole/test")
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/pihole/summary
# ---------------------------------------------------------------------------

async def test_pihole_summary_returns_stats(client: AsyncClient) -> None:
    from app.models.pihole import SummaryStats
    mock = _mock_pihole()
    mock.get_summary = AsyncMock(return_value=SummaryStats(
        total_queries=1000, blocked_queries=100, blocked_percent=10.0,
        unique_domains=200, queries_cached=50, domains_on_blocklist=99000,
    ))
    with patch.object(sync_manager_module, "pihole", mock):
        res = await client.get("/api/pihole/summary")
    assert res.status_code == 200
    assert res.json()["total_queries"] == 1000


async def test_pihole_summary_503_when_sync_not_running(client: AsyncClient) -> None:
    with patch.object(sync_manager_module, "pihole", None):
        res = await client.get("/api/pihole/summary")
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/queries
# ---------------------------------------------------------------------------

async def test_queries_returns_empty_list(client: AsyncClient) -> None:
    res = await client.get("/api/queries")
    assert res.status_code == 200
    body = res.json()
    assert body["queries"] == []
    assert body["cursor"] is None


async def test_queries_returns_seeded_data(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "example.com", category="analytics")
    await _query(db, 1, "example.com", now - 10)

    res = await client.get("/api/queries")
    body = res.json()
    assert len(body["queries"]) == 1
    assert body["queries"][0]["domain"] == "example.com"


async def test_queries_limit_param(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.com")
    for i in range(5):
        await _query(db, i + 1, "a.com", now - i)

    res = await client.get("/api/queries", params={"limit": 2})
    assert len(res.json()["queries"]) == 2


async def test_queries_status_type_filter(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.com")
    await _query(db, 1, "a.com", now - 10, status="GRAVITY")
    await _query(db, 2, "a.com", now - 20, status="FORWARDED")

    res = await client.get("/api/queries", params={"status_type": "blocked"})
    queries = res.json()["queries"]
    assert len(queries) == 1
    assert queries[0]["status"] == "GRAVITY"


async def test_queries_tracker_only_filter(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "tracker.com", category="analytics")
    await _domain(db, "plain.com")  # no category
    await _query(db, 1, "tracker.com", now - 10)
    await _query(db, 2, "plain.com",   now - 20)

    res = await client.get("/api/queries", params={"tracker_only": True})
    queries = res.json()["queries"]
    assert all(q["category"] is not None for q in queries)


async def test_queries_rejects_invalid_limit(client: AsyncClient) -> None:
    res = await client.get("/api/queries", params={"limit": 0})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/stats/trackers
# ---------------------------------------------------------------------------

async def test_stats_trackers_returns_shape(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "ads.example.com", category="advertising", company_name="Acme")
    await _query(db, 1, "ads.example.com", now - 60)

    res = await client.get("/api/stats/trackers", params={"hours": 1, "end_ts": now})
    assert res.status_code == 200
    body = res.json()
    assert "total_queries" in body
    assert "by_category" in body


# ---------------------------------------------------------------------------
# GET /api/stats/timeline
# ---------------------------------------------------------------------------

async def test_stats_timeline_returns_buckets(client: AsyncClient) -> None:
    res = await client.get("/api/stats/timeline", params={"hours": 24})
    assert res.status_code == 200
    body = res.json()
    assert "buckets" in body
    assert "bucket_seconds" in body


# ---------------------------------------------------------------------------
# GET /api/stats/timeline/clients
# ---------------------------------------------------------------------------

async def test_stats_timeline_clients_returns_shape(client: AsyncClient) -> None:
    res = await client.get("/api/stats/timeline/clients", params={"hours": 24})
    assert res.status_code == 200
    assert "clients" in res.json()


# ---------------------------------------------------------------------------
# GET /api/stats/domains
# ---------------------------------------------------------------------------

async def test_stats_domains_returns_shape(client: AsyncClient) -> None:
    res = await client.get("/api/stats/domains")
    assert res.status_code == 200
    body = res.json()
    assert "domains" in body
    assert "window_hours" in body


async def test_stats_domains_domain_filter(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "analytics.example.com", category="analytics", company_name="Acme")
    await _domain(db, "other.com", category="advertising", company_name="Corp")
    await _query(db, 1, "analytics.example.com", now - 60)
    await _query(db, 2, "other.com", now - 60)

    res = await client.get("/api/stats/domains", params={"domain": "analytics", "end_ts": now})
    domains = [d["domain"] for d in res.json()["domains"]]
    assert "analytics.example.com" in domains
    assert "other.com" not in domains


# ---------------------------------------------------------------------------
# GET /api/domains/search
# ---------------------------------------------------------------------------

async def test_search_domains_returns_matches(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "analytics.example.com")
    await _query(db, 1, "analytics.example.com", now - 60)

    res = await client.get("/api/domains/search", params={"q": "analytics", "end_ts": now})
    assert res.status_code == 200
    assert "analytics.example.com" in res.json()


async def test_search_domains_rejects_short_query(client: AsyncClient) -> None:
    res = await client.get("/api/domains/search", params={"q": "a"})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/stats/clients
# ---------------------------------------------------------------------------

async def test_stats_clients_returns_shape(client: AsyncClient) -> None:
    res = await client.get("/api/stats/clients")
    assert res.status_code == 200
    assert "clients" in res.json()


# ---------------------------------------------------------------------------
# GET /api/settings/options
# ---------------------------------------------------------------------------

async def test_settings_options_returns_categories_and_companies(
    client: AsyncClient, db: LocalDatabase
) -> None:
    await _domain(db, "a.com", category="analytics", company_name="Acme")

    res = await client.get("/api/settings/options")
    assert res.status_code == 200
    body = res.json()
    assert "analytics" in body["categories"]
    assert "Acme" in body["companies"]


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------

async def test_get_settings_returns_defaults(client: AsyncClient) -> None:
    res = await client.get("/api/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["sync_interval_seconds"] == 60
    assert body["data_retention_days"] == 7
    assert body["excluded_categories"] == []


async def test_get_settings_reflects_stored_values(client: AsyncClient, db: LocalDatabase) -> None:
    await db.set_config("data_retention_days", "30")

    res = await client.get("/api/settings")
    assert res.json()["data_retention_days"] == 30


# ---------------------------------------------------------------------------
# PUT /api/settings/{key}
# ---------------------------------------------------------------------------

async def test_put_setting_int_success(client: AsyncClient, db: LocalDatabase) -> None:
    res = await client.put("/api/settings/data_retention_days", json={"value": 14})
    assert res.status_code == 200
    assert await db.get_config("data_retention_days") == "14"


async def test_put_setting_int_below_min(client: AsyncClient) -> None:
    res = await client.put("/api/settings/data_retention_days", json={"value": 0})
    assert res.status_code == 422


async def test_put_setting_int_above_max(client: AsyncClient) -> None:
    res = await client.put("/api/settings/data_retention_days", json={"value": 999})
    assert res.status_code == 422


async def test_put_setting_int_wrong_type(client: AsyncClient) -> None:
    res = await client.put("/api/settings/data_retention_days", json={"value": "not-an-int"})
    assert res.status_code == 422


async def test_put_setting_exclusion_list(client: AsyncClient, db: LocalDatabase) -> None:
    res = await client.put("/api/settings/excluded_categories", json={"value": ["advertising", "analytics"]})
    assert res.status_code == 200
    stored = await db.get_config("excluded_categories")
    assert stored == '["advertising", "analytics"]'


async def test_put_setting_exclusion_list_wrong_type(client: AsyncClient) -> None:
    res = await client.put("/api/settings/excluded_categories", json={"value": "not-a-list"})
    assert res.status_code == 422


async def test_put_setting_unknown_key_returns_404(client: AsyncClient) -> None:
    res = await client.put("/api/settings/nonexistent_key", json={"value": 42})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/clients
# ---------------------------------------------------------------------------

async def test_get_clients_returns_empty(client: AsyncClient) -> None:
    res = await client.get("/api/clients")
    assert res.status_code == 200
    assert res.json()["clients"] == []


async def test_get_clients_returns_seeded_data(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "example.com")
    await _query(db, 1, "example.com", now - 10, client_ip="192.168.1.5")

    res = await client.get("/api/clients")
    clients = res.json()["clients"]
    assert any(c["client_ip"] == "192.168.1.5" for c in clients)


# ---------------------------------------------------------------------------
# PUT /api/clients/{client_ip}
# ---------------------------------------------------------------------------

async def test_set_client_name(client: AsyncClient, db: LocalDatabase) -> None:
    res = await client.put("/api/clients/192.168.1.1", json={"name": "My Laptop"})
    assert res.status_code == 200
    names = await db.get_client_names()
    assert names["192.168.1.1"] == "My Laptop"


async def test_set_client_name_empty_returns_422(client: AsyncClient) -> None:
    res = await client.put("/api/clients/192.168.1.1", json={"name": ""})
    assert res.status_code == 422


async def test_set_client_name_too_long_returns_422(client: AsyncClient) -> None:
    res = await client.put("/api/clients/192.168.1.1", json={"name": "x" * 65})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/clients/{client_ip}
# ---------------------------------------------------------------------------

async def test_delete_client_name(client: AsyncClient, db: LocalDatabase) -> None:
    await db.set_client_name("192.168.1.1", "My Laptop")

    res = await client.delete("/api/clients/192.168.1.1")
    assert res.status_code == 200
    assert "192.168.1.1" not in await db.get_client_names()


async def test_delete_client_name_nonexistent_is_safe(client: AsyncClient) -> None:
    res = await client.delete("/api/clients/10.0.0.1")
    assert res.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/admin/reenrich
# ---------------------------------------------------------------------------

async def test_admin_reenrich_returns_flagged_count(client: AsyncClient, db: LocalDatabase) -> None:
    await _domain(db, "a.com", category=None, enrichment_source="heuristic")
    await _domain(db, "b.com", category="analytics", enrichment_source="trackerdb")

    res = await client.post("/api/admin/reenrich")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["flagged"] == 1  # only heuristic domain


# ---------------------------------------------------------------------------
# POST /api/admin/reset
# ---------------------------------------------------------------------------

async def test_admin_reset_clears_data(client: AsyncClient, db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "example.com")
    await _query(db, 1, "example.com", now - 10)
    await db.update_sync_state(99)

    with patch.object(sync_manager_module, "trigger_sync"):
        res = await client.post("/api/admin/reset")

    assert res.status_code == 200
    results, _ = await db.fetch_queries(limit=10)
    assert results == []
    assert await db.get_last_query_id() == 0
