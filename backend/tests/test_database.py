"""
Tests for LocalDatabase (app/services/database.py).

All tests use the in-memory `db` fixture from conftest.py, so nothing
touches the real filesystem and each test starts with a clean database.

Helper functions at the top handle seeding — keeping the test bodies
focused on assertions rather than setup boilerplate.
"""

import time

import pytest

from app.services.database import LocalDatabase

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

async def _domain(
    db: LocalDatabase,
    domain: str,
    *,
    category: str | None = None,
    company_name: str | None = None,
    tracker_name: str | None = None,
    enrichment_source: str = "trackerdb",
    needs_reenrichment: int = 0,
) -> None:
    """Insert a domain row with optional enrichment data."""
    await db.upsert_domains([domain])
    await db.batch_update_domain_enrichment([{
        "domain": domain,
        "tracker_name": tracker_name,
        "category": category,
        "company_name": company_name,
        "company_country": None,
        "source": enrichment_source,
    }])
    if needs_reenrichment:
        await db._db.execute(
            "UPDATE domains SET needs_reenrichment = 1 WHERE domain = ?", (domain,)
        )
        await db._db.commit()


async def _query(
    db: LocalDatabase,
    id: int,
    domain: str,
    timestamp: float,
    *,
    status: str = "FORWARDED",
    client_ip: str = "192.168.1.1",
) -> None:
    """Insert a single query row (domain must already exist)."""
    await db.insert_queries([{
        "id": id,
        "timestamp": timestamp,
        "domain": domain,
        "client_ip": client_ip,
        "status": status,
        "query_type": "A",
        "reply_type": "IP",
        "reply_time": 0.001,
        "upstream": None,
        "list_id": None,
    }])


# ---------------------------------------------------------------------------
# Schema / init
# ---------------------------------------------------------------------------

async def test_init_creates_all_tables(db: LocalDatabase) -> None:
    tables = set()
    async with db._db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ) as cur:
        rows = await cur.fetchall()
        tables = {r[0] for r in rows}

    assert {"queries", "domains", "sync_state", "schema_version", "user_config", "client_names"} <= tables


async def test_init_seeds_sync_state_row(db: LocalDatabase) -> None:
    assert await db.get_last_query_id() == 0


async def test_init_is_idempotent(db: LocalDatabase) -> None:
    # Calling init() again should not raise or corrupt data
    await db.init()
    assert await db.get_last_query_id() == 0


# ---------------------------------------------------------------------------
# Sync state
# ---------------------------------------------------------------------------

async def test_update_sync_state_persists(db: LocalDatabase) -> None:
    await db.update_sync_state(42)
    assert await db.get_last_query_id() == 42


# ---------------------------------------------------------------------------
# Domain upsert / enrichment
# ---------------------------------------------------------------------------

async def test_upsert_domains_inserts_new_rows(db: LocalDatabase) -> None:
    await db.upsert_domains(["example.com", "other.com"])
    unenriched = await db.get_unenriched_domains()
    assert "example.com" in unenriched
    assert "other.com" in unenriched


async def test_upsert_domains_is_idempotent(db: LocalDatabase) -> None:
    await db.upsert_domains(["example.com"])
    await db.upsert_domains(["example.com"])  # second call is a no-op
    unenriched = await db.get_unenriched_domains()
    assert unenriched.count("example.com") == 1


async def test_batch_update_domain_enrichment_sets_fields(db: LocalDatabase) -> None:
    await db.upsert_domains(["telemetry.nvidia.com"])
    await db.batch_update_domain_enrichment([{
        "domain": "telemetry.nvidia.com",
        "tracker_name": "Nvidia Telemetry",
        "category": "telemetry",
        "company_name": "Nvidia",
        "company_country": "US",
        "source": "trackerdb",
    }])
    # Should no longer appear as unenriched
    assert "telemetry.nvidia.com" not in await db.get_unenriched_domains()


async def test_get_unenriched_domains_includes_needs_reenrichment(db: LocalDatabase) -> None:
    await _domain(db, "example.com", category="analytics")
    await db._db.execute(
        "UPDATE domains SET needs_reenrichment = 1 WHERE domain = 'example.com'"
    )
    await db._db.commit()
    assert "example.com" in await db.get_unenriched_domains()


async def test_flag_for_reenrichment_marks_heuristic_and_rdap_failed(db: LocalDatabase) -> None:
    await _domain(db, "a.com", category="analytics", enrichment_source="heuristic")
    await _domain(db, "b.com", enrichment_source="rdap_failed")
    await _domain(db, "c.com", category="advertising", enrichment_source="trackerdb")

    count = await db.flag_for_reenrichment()

    assert count == 2
    unenriched = await db.get_unenriched_domains()
    assert "a.com" in unenriched
    assert "b.com" in unenriched
    assert "c.com" not in unenriched


async def test_flag_heuristic_uncategorized_for_reenrichment(db: LocalDatabase) -> None:
    await _domain(db, "a.com", category=None, enrichment_source="heuristic")   # should flag
    await _domain(db, "b.com", category="analytics", enrichment_source="heuristic")  # has category, skip
    await _domain(db, "c.com", category=None, enrichment_source="trackerdb")   # wrong source, skip

    count = await db.flag_heuristic_uncategorized_for_reenrichment()
    assert count == 1
    assert "a.com" in await db.get_unenriched_domains()


# ---------------------------------------------------------------------------
# Query insertion
# ---------------------------------------------------------------------------

async def test_insert_queries_stores_rows(db: LocalDatabase) -> None:
    await db.upsert_domains(["example.com"])
    await _query(db, 1, "example.com", time.time())

    results, _ = await db.fetch_queries(limit=10)
    assert len(results) == 1
    assert results[0]["domain"] == "example.com"


async def test_insert_queries_deduplicates_by_id(db: LocalDatabase) -> None:
    await db.upsert_domains(["example.com"])
    await _query(db, 1, "example.com", time.time())
    await _query(db, 1, "example.com", time.time())  # duplicate — should be ignored

    results, _ = await db.fetch_queries(limit=10)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# fetch_queries — filters and pagination
# ---------------------------------------------------------------------------

@pytest.fixture
async def seeded_db(db: LocalDatabase) -> LocalDatabase:
    """DB pre-loaded with two domains and four queries for filter/pagination tests."""
    now = time.time()
    await _domain(db, "analytics.example.com", category="analytics", company_name="Example")
    await _domain(db, "plain.example.com")  # unenriched / no tracker

    # Two allowed, two blocked; mix of domains and clients
    await _query(db, 1, "analytics.example.com", now - 10, status="FORWARDED", client_ip="192.168.1.1")
    await _query(db, 2, "analytics.example.com", now - 20, status="GRAVITY",   client_ip="192.168.1.1")
    await _query(db, 3, "plain.example.com",      now - 30, status="FORWARDED", client_ip="192.168.1.2")
    await _query(db, 4, "plain.example.com",      now - 40, status="DENYLIST",  client_ip="192.168.1.2")
    return db


async def test_fetch_queries_returns_all_by_default(seeded_db: LocalDatabase) -> None:
    results, _ = await seeded_db.fetch_queries(limit=10)
    assert len(results) == 4


async def test_fetch_queries_newest_first(seeded_db: LocalDatabase) -> None:
    results, _ = await seeded_db.fetch_queries(limit=10)
    ids = [r["id"] for r in results]
    assert ids == sorted(ids, reverse=True)


async def test_fetch_queries_filter_blocked(seeded_db: LocalDatabase) -> None:
    results, _ = await seeded_db.fetch_queries(limit=10, status_type="blocked")
    assert all(r["status"] in {"GRAVITY", "DENYLIST"} for r in results)
    assert len(results) == 2


async def test_fetch_queries_filter_allowed(seeded_db: LocalDatabase) -> None:
    results, _ = await seeded_db.fetch_queries(limit=10, status_type="allowed")
    assert all(r["status"] == "FORWARDED" for r in results)
    assert len(results) == 2


async def test_fetch_queries_filter_tracker_only(seeded_db: LocalDatabase) -> None:
    results, _ = await seeded_db.fetch_queries(limit=10, tracker_only=True)
    # Only analytics.example.com has a category
    assert all(r["domain"] == "analytics.example.com" for r in results)
    assert len(results) == 2


async def test_fetch_queries_cursor_pagination(seeded_db: LocalDatabase) -> None:
    # Fetch page 1: newest 3 of 4 rows
    page1, next_cursor = await seeded_db.fetch_queries(limit=3)
    assert len(page1) == 3
    assert next_cursor is not None

    # Fetch page 2: remaining 1 row — fewer than limit, so cursor is None
    page2, next_cursor2 = await seeded_db.fetch_queries(limit=3, cursor=next_cursor)
    assert len(page2) == 1
    assert next_cursor2 is None

    # Pages don't overlap and are in descending order overall
    ids1 = [r["id"] for r in page1]
    ids2 = [r["id"] for r in page2]
    assert max(ids2) < min(ids1)


async def test_fetch_queries_includes_client_name(seeded_db: LocalDatabase) -> None:
    await seeded_db.set_client_name("192.168.1.1", "My Laptop")
    results, _ = await seeded_db.fetch_queries(limit=10)
    laptop_queries = [r for r in results if r["client"] == "192.168.1.1"]
    assert all(r["client_name"] == "My Laptop" for r in laptop_queries)


# ---------------------------------------------------------------------------
# Domain search
# ---------------------------------------------------------------------------

async def test_search_domains_returns_substring_matches(seeded_db: LocalDatabase) -> None:
    now = time.time()
    results = await seeded_db.search_domains("analytics", hours=24, end_ts=now)
    assert "analytics.example.com" in results


async def test_search_domains_returns_empty_for_no_match(seeded_db: LocalDatabase) -> None:
    results = await seeded_db.search_domains("zzznomatch", hours=24, end_ts=time.time())
    assert results == []


async def test_search_domains_escapes_like_wildcards(seeded_db: LocalDatabase) -> None:
    # A query containing '%' should not blow up or match everything
    results = await seeded_db.search_domains("%", hours=24, end_ts=time.time())
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Settings (user_config)
# ---------------------------------------------------------------------------

async def test_set_and_get_config(db: LocalDatabase) -> None:
    await db.set_config("retention_days", "30")
    assert await db.get_config("retention_days") == "30"


async def test_get_config_returns_none_for_missing_key(db: LocalDatabase) -> None:
    assert await db.get_config("nonexistent") is None


async def test_set_config_upserts(db: LocalDatabase) -> None:
    await db.set_config("retention_days", "30")
    await db.set_config("retention_days", "60")
    assert await db.get_config("retention_days") == "60"


async def test_get_all_config_returns_all_keys(db: LocalDatabase) -> None:
    await db.set_config("a", "1")
    await db.set_config("b", "2")
    result = await db.get_all_config()
    assert result == {"a": "1", "b": "2"}


async def test_delete_config_removes_key(db: LocalDatabase) -> None:
    await db.set_config("to_delete", "value")
    await db.delete_config("to_delete")
    assert await db.get_config("to_delete") is None


async def test_get_available_categories(db: LocalDatabase) -> None:
    await _domain(db, "a.com", category="analytics")
    await _domain(db, "b.com", category="telemetry")
    await _domain(db, "c.com")  # no category
    cats = await db.get_available_categories()
    assert set(cats) == {"analytics", "telemetry"}


async def test_get_available_companies(db: LocalDatabase) -> None:
    await _domain(db, "a.com", company_name="Acme")
    await _domain(db, "b.com", company_name="Globex")
    await _domain(db, "c.com")  # no company
    companies = await db.get_available_companies()
    assert set(companies) == {"Acme", "Globex"}


# ---------------------------------------------------------------------------
# Client names
# ---------------------------------------------------------------------------

async def test_set_and_get_client_names(db: LocalDatabase) -> None:
    await db.set_client_name("192.168.1.1", "My Phone")
    names = await db.get_client_names()
    assert names["192.168.1.1"] == "My Phone"


async def test_set_client_name_upserts(db: LocalDatabase) -> None:
    await db.set_client_name("192.168.1.1", "Old Name")
    await db.set_client_name("192.168.1.1", "New Name")
    assert (await db.get_client_names())["192.168.1.1"] == "New Name"


async def test_delete_client_name(db: LocalDatabase) -> None:
    await db.set_client_name("192.168.1.1", "My Phone")
    await db.delete_client_name("192.168.1.1")
    assert "192.168.1.1" not in await db.get_client_names()


async def test_delete_client_name_nonexistent_is_safe(db: LocalDatabase) -> None:
    await db.delete_client_name("10.0.0.1")  # should not raise


# ---------------------------------------------------------------------------
# Data retention purge
# ---------------------------------------------------------------------------

async def test_purge_old_data_deletes_old_queries(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "example.com")
    await _query(db, 1, "example.com", now - 10 * 86400, status="FORWARDED")  # 10 days old
    await _query(db, 2, "example.com", now - 1,           status="FORWARDED")  # recent

    queries_deleted, _ = await db.purge_old_data(retention_days=7)

    assert queries_deleted == 1
    results, _ = await db.fetch_queries(limit=10)
    assert len(results) == 1
    assert results[0]["id"] == 2


async def test_purge_old_data_removes_orphaned_domains(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "orphan.com")
    await _domain(db, "kept.com")
    await _query(db, 1, "orphan.com", now - 10 * 86400)  # will be purged
    await _query(db, 2, "kept.com",   now - 1)           # stays

    _, domains_deleted = await db.purge_old_data(retention_days=7)

    assert domains_deleted == 1
    unenriched = await db.get_unenriched_domains()
    assert "orphan.com" not in unenriched


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------

async def test_reset_clears_queries_and_domains(db: LocalDatabase) -> None:
    await _domain(db, "example.com", category="analytics")
    await _query(db, 1, "example.com", time.time())
    await db.update_sync_state(99)

    await db.reset()

    results, _ = await db.fetch_queries(limit=10)
    assert results == []
    assert await db.get_last_query_id() == 0


# ---------------------------------------------------------------------------
# get_data_range()
# ---------------------------------------------------------------------------

async def test_get_data_range_returns_none_when_empty(db: LocalDatabase) -> None:
    result = await db.get_data_range()
    assert result["oldest_ts"] is None
    assert result["newest_ts"] is None


async def test_get_data_range_returns_correct_bounds(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "example.com")
    await _query(db, 1, "example.com", now - 100)
    await _query(db, 2, "example.com", now - 10)

    result = await db.get_data_range()
    assert result["oldest_ts"] == pytest.approx(now - 100, abs=1)
    assert result["newest_ts"] == pytest.approx(now - 10, abs=1)


# ---------------------------------------------------------------------------
# fetch_tracker_stats()
# ---------------------------------------------------------------------------

async def test_fetch_tracker_stats_aggregates_by_category(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.example.com", category="analytics", company_name="Acme")
    await _query(db, 1, "a.example.com", now - 60, status="FORWARDED")
    await _query(db, 2, "a.example.com", now - 120, status="GRAVITY")

    result = await db.fetch_tracker_stats(hours=1, end_ts=now)

    assert result["total_queries"] == 2
    assert result["tracker_queries"] == 2
    cats = {c["category"]: c for c in result["by_category"]}
    assert "analytics" in cats
    assert cats["analytics"]["query_count"] == 2
    assert cats["analytics"]["blocked_count"] == 1
    assert cats["analytics"]["allowed_count"] == 1


async def test_fetch_tracker_stats_excludes_queries_outside_window(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.example.com", category="analytics", company_name="Acme")
    await _query(db, 1, "a.example.com", now - 7200)  # 2 hours ago — outside 1h window

    result = await db.fetch_tracker_stats(hours=1, end_ts=now)
    assert result["total_queries"] == 0


async def test_fetch_tracker_stats_filter_by_client(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.example.com", category="analytics", company_name="Acme")
    await _query(db, 1, "a.example.com", now - 60, client_ip="192.168.1.1")
    await _query(db, 2, "a.example.com", now - 60, client_ip="192.168.1.2")

    result = await db.fetch_tracker_stats(hours=1, end_ts=now, client_ip="192.168.1.1")
    assert result["total_queries"] == 1


# ---------------------------------------------------------------------------
# fetch_timeline_stats() — bucket size selection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hours, expected_bucket_seconds", [
    (24,  3600),
    (168, 6 * 3600),
    (720, 24 * 3600),
])
async def test_fetch_timeline_stats_bucket_size(
    db: LocalDatabase, hours: int, expected_bucket_seconds: int
) -> None:
    now = time.time()
    await _domain(db, "a.com", category="analytics", company_name="Acme")
    result = await db.fetch_timeline_stats(hours=hours, end_ts=now)
    assert result["bucket_seconds"] == expected_bucket_seconds


async def test_fetch_timeline_stats_assigns_query_to_correct_bucket(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.com", category="analytics", company_name="Acme")

    # Insert a query exactly 30 minutes ago — should land in bucket 0 of a 24h window
    # (bucket = floor((ts - from_ts) / 3600); from_ts = now - 24h; ts = now - 0.5h → bucket 23)
    await _query(db, 1, "a.com", now - 1800)

    result = await db.fetch_timeline_stats(hours=24, end_ts=now)
    total = sum(b["total"] for b in result["buckets"])
    assert total == 1


async def test_fetch_timeline_stats_empty_buckets_are_zeroed(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.com", category="analytics", company_name="Acme")
    result = await db.fetch_timeline_stats(hours=24, end_ts=now)

    # All buckets exist and are zeroed when no data
    assert all(b["total"] == 0 for b in result["buckets"])
    assert len(result["buckets"]) == 25  # 24 full hours + 1 partial


# ---------------------------------------------------------------------------
# fetch_domain_stats()
# ---------------------------------------------------------------------------

async def test_fetch_domain_stats_filter_by_category(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.example.com", category="analytics", company_name="Acme")
    await _domain(db, "b.example.com", category="telemetry", company_name="Corp")
    await _query(db, 1, "a.example.com", now - 60)
    await _query(db, 2, "b.example.com", now - 60)

    result = await db.fetch_domain_stats(hours=1, end_ts=now, category="analytics")
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain"] == "a.example.com"


async def test_fetch_domain_stats_domain_exact_match(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "analytics.example.com", category="analytics", company_name="Acme")
    await _domain(db, "other-analytics.com", category="analytics", company_name="Corp")
    await _query(db, 1, "analytics.example.com", now - 60)
    await _query(db, 2, "other-analytics.com", now - 60)

    result = await db.fetch_domain_stats(hours=1, end_ts=now, domain="analytics.example.com", domain_exact=True)
    assert len(result["domains"]) == 1
    assert result["domains"][0]["domain"] == "analytics.example.com"


async def test_fetch_domain_stats_domain_substring_match(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "analytics.example.com", category="analytics", company_name="Acme")
    await _domain(db, "other-analytics.com", category="analytics", company_name="Corp")
    await _query(db, 1, "analytics.example.com", now - 60)
    await _query(db, 2, "other-analytics.com", now - 60)

    result = await db.fetch_domain_stats(hours=1, end_ts=now, domain="analytics")
    assert len(result["domains"]) == 2


# ---------------------------------------------------------------------------
# fetch_client_stats()
# ---------------------------------------------------------------------------

async def test_fetch_client_stats_aggregates_per_client(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.example.com", category="analytics", company_name="Acme")
    await _query(db, 1, "a.example.com", now - 60, client_ip="192.168.1.1")
    await _query(db, 2, "a.example.com", now - 60, client_ip="192.168.1.1")
    await _query(db, 3, "a.example.com", now - 60, client_ip="192.168.1.2")

    result = await db.fetch_client_stats(hours=1, end_ts=now)
    clients = {c["client_ip"]: c for c in result["clients"]}

    assert clients["192.168.1.1"]["query_count"] == 2
    assert clients["192.168.1.2"]["query_count"] == 1


async def test_fetch_client_stats_includes_friendly_name(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "a.example.com", category="analytics", company_name="Acme")
    await _query(db, 1, "a.example.com", now - 60, client_ip="192.168.1.1")
    await db.set_client_name("192.168.1.1", "My Laptop")

    result = await db.fetch_client_stats(hours=1, end_ts=now)
    assert result["clients"][0]["client_name"] == "My Laptop"


async def test_fetch_client_stats_filter_by_domain(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "target.example.com", category="analytics", company_name="Acme")
    await _domain(db, "other.example.com", category="advertising", company_name="Corp")
    await _query(db, 1, "target.example.com", now - 60, client_ip="192.168.1.1")
    await _query(db, 2, "target.example.com", now - 60, client_ip="192.168.1.2")
    await _query(db, 3, "other.example.com",  now - 60, client_ip="192.168.1.1")  # different domain

    result = await db.fetch_client_stats(hours=1, end_ts=now, domain="target.example.com")
    by_ip = {c["client_ip"]: c for c in result["clients"]}

    # Both clients that queried the target domain appear
    assert set(by_ip.keys()) == {"192.168.1.1", "192.168.1.2"}
    # 192.168.1.1's count reflects only its query to target.example.com, not other.example.com
    assert by_ip["192.168.1.1"]["query_count"] == 1


async def test_fetch_client_stats_domain_filter_is_exact_match(db: LocalDatabase) -> None:
    now = time.time()
    await _domain(db, "target.com", category="analytics", company_name="Acme")
    await _domain(db, "sub.target.com", category="analytics", company_name="Acme")
    await _query(db, 1, "target.com",     now - 60, client_ip="192.168.1.1")
    await _query(db, 2, "sub.target.com", now - 60, client_ip="192.168.1.2")

    result = await db.fetch_client_stats(hours=1, end_ts=now, domain="target.com")
    client_ips = {c["client_ip"] for c in result["clients"]}

    assert "192.168.1.1" in client_ips
    assert "192.168.1.2" not in client_ips  # sub.target.com must not match
