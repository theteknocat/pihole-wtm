"""
Tests for tracker sources (TrackerDB and Disconnect.me) and source registration.

TrackerDBSource tests use a real in-memory SQLite populated with the same
schema as trackerdb.db so the actual SQL queries run without any files on disk.

DisconnectSource tests set the internal _lookup dict directly for lookup
behaviour, and mock httpx for the _load() / refresh tests.
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from app.services.disconnectme.source import DisconnectSource
from app.services.sources import get_tracker_sources
from app.services.trackerdb.source import TrackerDBSource

# ---------------------------------------------------------------------------
# TrackerDB fixtures
# ---------------------------------------------------------------------------

_TRACKERDB_SCHEMA = """
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE companies  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT);
CREATE TABLE trackers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INTEGER REFERENCES categories(id),
    company_id  INTEGER REFERENCES companies(id),
    alias       INTEGER REFERENCES trackers(id)
);
CREATE TABLE tracker_domains (domain TEXT PRIMARY KEY, tracker INTEGER REFERENCES trackers(id));
"""


async def _make_trackerdb(path: Path) -> aiosqlite.Connection:
    """Create a minimal trackerdb.db at path and return an open connection."""
    db = await aiosqlite.connect(str(path))
    db.row_factory = aiosqlite.Row
    await db.executescript(_TRACKERDB_SCHEMA)

    # Seed: one category, one company, two trackers (one aliased), two domains
    await db.executemany("INSERT INTO categories VALUES (?, ?)", [
        (1, "advertising"),
        (2, "analytics"),
    ])
    await db.executemany("INSERT INTO companies VALUES (?, ?, ?)", [
        (1, "Acme Ad Corp", "US"),
        (2, "Tracker Inc",  "GB"),
    ])
    await db.executemany("INSERT INTO trackers VALUES (?, ?, ?, ?, ?)", [
        (1, "AcmeAds",     1, 1, None),   # real tracker
        (2, "AcmeAlias",   None, None, 1), # alias → tracker 1
        (3, "AnalyticsCo", 2, 2, None),
    ])
    await db.executemany("INSERT INTO tracker_domains VALUES (?, ?)", [
        ("ads.acme.com",       1),
        ("alias.acme.com",     2),   # via alias tracker
        ("analytics.corp.com", 3),
    ])
    await db.commit()
    return db


@pytest.fixture
async def trackerdb_source(tmp_path: Path) -> TrackerDBSource:
    """TrackerDBSource with a real in-memory-style DB, no network calls."""
    db_path = tmp_path / "trackerdb.db"
    source = TrackerDBSource()
    source._path = db_path
    source._db = await _make_trackerdb(db_path)
    yield source
    if source._db is not None:
        await source._db.close()


# ---------------------------------------------------------------------------
# TrackerDBSource — lookup_exact()
# ---------------------------------------------------------------------------

async def test_trackerdb_lookup_exact_hit(trackerdb_source: TrackerDBSource) -> None:
    result = await trackerdb_source.lookup_exact("ads.acme.com")
    assert result is not None
    assert result.tracker_name == "AcmeAds"
    assert result.category == "advertising"
    assert result.company_name == "Acme Ad Corp"
    assert result.company_country == "US"


async def test_trackerdb_lookup_exact_miss(trackerdb_source: TrackerDBSource) -> None:
    assert await trackerdb_source.lookup_exact("not-in-db.com") is None


async def test_trackerdb_lookup_exact_no_subdomain_fallback(trackerdb_source: TrackerDBSource) -> None:
    # sub.ads.acme.com is not in the DB; exact lookup must NOT fall back
    assert await trackerdb_source.lookup_exact("sub.ads.acme.com") is None


async def test_trackerdb_lookup_exact_resolves_alias(trackerdb_source: TrackerDBSource) -> None:
    result = await trackerdb_source.lookup_exact("alias.acme.com")
    assert result is not None
    # Should resolve through alias → parent tracker
    assert result.tracker_name == "AcmeAds"
    assert result.category == "advertising"
    assert result.company_name == "Acme Ad Corp"


# ---------------------------------------------------------------------------
# TrackerDBSource — enrich() with subdomain fallback and LRU cache
# ---------------------------------------------------------------------------

async def test_trackerdb_enrich_exact_hit(trackerdb_source: TrackerDBSource) -> None:
    result = await trackerdb_source.enrich("ads.acme.com")
    assert result is not None
    assert result.tracker_name == "AcmeAds"


async def test_trackerdb_enrich_subdomain_fallback(trackerdb_source: TrackerDBSource) -> None:
    # sub.ads.acme.com not in DB; should fall back to ads.acme.com
    result = await trackerdb_source.enrich("sub.ads.acme.com")
    assert result is not None
    assert result.tracker_name == "AcmeAds"


async def test_trackerdb_enrich_miss(trackerdb_source: TrackerDBSource) -> None:
    assert await trackerdb_source.enrich("unknown.example.com") is None


async def test_trackerdb_enrich_caches_result(trackerdb_source: TrackerDBSource) -> None:
    await trackerdb_source.enrich("ads.acme.com")
    # Second call should return from cache — monkey-patch DB to verify no query
    trackerdb_source._db = None  # removing DB would cause a crash if cache is bypassed
    result = await trackerdb_source.enrich("ads.acme.com")
    assert result is not None
    assert result.tracker_name == "AcmeAds"


async def test_trackerdb_enrich_caches_miss(trackerdb_source: TrackerDBSource) -> None:
    await trackerdb_source.enrich("unknown.example.com")
    trackerdb_source._db = None
    result = await trackerdb_source.enrich("unknown.example.com")
    assert result is None


# ---------------------------------------------------------------------------
# TrackerDBSource — guard flags
# ---------------------------------------------------------------------------

async def test_trackerdb_returns_none_while_refreshing(trackerdb_source: TrackerDBSource) -> None:
    trackerdb_source._refreshing = True
    assert await trackerdb_source.lookup_exact("ads.acme.com") is None


async def test_trackerdb_returns_none_after_lookup_failed(trackerdb_source: TrackerDBSource) -> None:
    trackerdb_source._lookup_failed = True
    assert await trackerdb_source.lookup_exact("ads.acme.com") is None


# ---------------------------------------------------------------------------
# TrackerDBSource — health_check()
# ---------------------------------------------------------------------------

async def test_trackerdb_health_check_when_loaded(trackerdb_source: TrackerDBSource) -> None:
    result = await trackerdb_source.health_check()
    assert result["loaded"] is True
    assert result["domain_count"] == 2   # alias tracker has no category_id so its domain isn't counted
    assert result["category_count"] == 2


# ---------------------------------------------------------------------------
# DisconnectSource — lookup_exact() and enrich()
# ---------------------------------------------------------------------------

@pytest.fixture
def disconnect_source() -> DisconnectSource:
    from app.models.tracker import TrackerInfo
    source = DisconnectSource()
    source._lookup = {
        "ads.example.com": TrackerInfo(
            tracker_name="Example Ads",
            category="advertising",
            company_name="Example Corp",
            company_country=None,
        ),
    }
    source._loaded_at = time.time()
    return source


async def test_disconnect_lookup_exact_hit(disconnect_source: DisconnectSource) -> None:
    result = await disconnect_source.lookup_exact("ads.example.com")
    assert result is not None
    assert result.tracker_name == "Example Ads"
    assert result.category == "advertising"


async def test_disconnect_lookup_exact_miss(disconnect_source: DisconnectSource) -> None:
    assert await disconnect_source.lookup_exact("unknown.example.com") is None


async def test_disconnect_lookup_exact_no_subdomain_fallback(disconnect_source: DisconnectSource) -> None:
    # Disconnect.me is exact-only — sub.ads.example.com must not match ads.example.com
    assert await disconnect_source.lookup_exact("sub.ads.example.com") is None


async def test_disconnect_enrich_same_as_lookup_exact(disconnect_source: DisconnectSource) -> None:
    via_lookup = await disconnect_source.lookup_exact("ads.example.com")
    via_enrich = await disconnect_source.enrich("ads.example.com")
    assert via_lookup == via_enrich


async def test_disconnect_lookup_returns_none_when_not_loaded() -> None:
    source = DisconnectSource()  # never loaded
    assert await source.lookup_exact("ads.example.com") is None


# ---------------------------------------------------------------------------
# DisconnectSource — _load() from JSON
# ---------------------------------------------------------------------------

_SERVICES_JSON = {
    "categories": {
        "Advertising": [
            {"Example Ads": {"https://example.com": ["ads.example.com", "track.example.com"]}}
        ],
        "Analytics": [
            {"Stats Corp": {"https://stats.io": ["analytics.stats.io"]}}
        ],
    }
}


def _mock_httpx_load(json_body: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = json_body
    response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=response)
    return mock_client


async def test_disconnect_load_parses_json_correctly() -> None:
    source = DisconnectSource()
    mock = _mock_httpx_load(_SERVICES_JSON)
    with patch("app.services.disconnectme.source.httpx.AsyncClient", return_value=mock):
        await source._load()

    assert source.is_loaded
    assert "ads.example.com" in source._lookup
    assert "track.example.com" in source._lookup
    assert "analytics.stats.io" in source._lookup

    assert source._lookup["ads.example.com"].category == "advertising"
    assert source._lookup["ads.example.com"].company_name == "Example Ads"
    assert source._lookup["analytics.stats.io"].category == "analytics"


async def test_disconnect_load_network_error_keeps_existing_data() -> None:
    import httpx
    source = DisconnectSource()
    source._lookup = {"existing.com": MagicMock()}
    source._loaded_at = time.time()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))

    with patch("app.services.disconnectme.source.httpx.AsyncClient", return_value=mock_client):
        await source._load()

    # Existing data preserved
    assert "existing.com" in source._lookup


async def test_disconnect_refresh_if_stale_reloads_when_stale() -> None:
    source = DisconnectSource()
    source._loaded_at = time.time() - (source.UPDATE_INTERVAL_HOURS + 1) * 3600
    mock = _mock_httpx_load(_SERVICES_JSON)
    with patch("app.services.disconnectme.source.httpx.AsyncClient", return_value=mock):
        await source.refresh_if_stale()

    assert mock.get.call_count == 1


async def test_disconnect_refresh_if_stale_skips_when_fresh() -> None:
    source = DisconnectSource()
    source._loaded_at = time.time()  # just loaded
    mock = _mock_httpx_load(_SERVICES_JSON)
    with patch("app.services.disconnectme.source.httpx.AsyncClient", return_value=mock):
        await source.refresh_if_stale()

    mock.get.assert_not_called()


# ---------------------------------------------------------------------------
# Source registration
# ---------------------------------------------------------------------------

def test_get_tracker_sources_returns_both_sources() -> None:
    sources = get_tracker_sources()
    names = [s.source_name for s in sources]
    assert "trackerdb" in names
    assert "disconnect" in names


def test_get_tracker_sources_sorted_by_priority() -> None:
    sources = get_tracker_sources()
    priorities = [s.priority for s in sources]
    assert priorities == sorted(priorities)
