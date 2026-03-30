"""
Tests for the sync service (app/services/sync.py).

Focuses on the three core processing functions:
- _enrich_from_sources()  — priority ordering and fallback chain
- _gate_from_sources()    — exact-match filtering, gates flag
- _process_batch()        — full batch filter / enrich / persist logic

Uses the in-memory `db` fixture from conftest.py.
Mock sources are plain objects implementing the TrackerSource protocol.
"""

import time

import pytest

from app.models.pihole import RawQuery
from app.models.tracker import TrackerInfo
from app.services.database import LocalDatabase
from app.services.sync import _enrich_from_sources, _gate_from_sources, _process_batch


# ---------------------------------------------------------------------------
# Mock source helper
# ---------------------------------------------------------------------------

class MockSource:
    """Minimal TrackerSource implementation for testing."""

    def __init__(
        self,
        name: str = "mock",
        *,
        gates: bool = True,
        priority: int = 10,
        enrich_result: TrackerInfo | None = None,
        lookup_result: TrackerInfo | None = None,
    ) -> None:
        self.source_name = name
        self.label = name
        self.gates = gates
        self.priority = priority
        self._enrich_result = enrich_result
        self._lookup_result = lookup_result

    async def enrich(self, domain: str) -> TrackerInfo | None:
        return self._enrich_result

    async def lookup_exact(self, domain: str) -> TrackerInfo | None:
        return self._lookup_result

    async def refresh_if_stale(self) -> None:
        pass

    async def health_check(self) -> dict:
        return {}

    def api_router(self):
        return None


def _tracker(
    name: str = "Test Tracker",
    category: str = "advertising",
    company: str = "Test Corp",
) -> TrackerInfo:
    return TrackerInfo(
        tracker_name=name,
        category=category,
        company_name=company,
        company_country="US",
    )


def _query(
    id: int,
    domain: str,
    status: str = "FORWARDED",
    client: str = "192.168.1.1",
) -> RawQuery:
    return RawQuery(
        id=id,
        timestamp=time.time(),
        domain=domain,
        client=client,
        status=status,
        status_label="",
        query_type="A",
    )


# ---------------------------------------------------------------------------
# _enrich_from_sources()
# ---------------------------------------------------------------------------

async def test_enrich_returns_first_matching_source() -> None:
    info = _tracker()
    sources = [
        MockSource("first",  priority=10, enrich_result=info),
        MockSource("second", priority=20, enrich_result=_tracker("Other")),
    ]
    result, source_name = await _enrich_from_sources("example.com", sources)
    assert result == info
    assert source_name == "first"


async def test_enrich_falls_back_to_next_source() -> None:
    info = _tracker()
    sources = [
        MockSource("first",  priority=10, enrich_result=None),
        MockSource("second", priority=20, enrich_result=info),
    ]
    result, source_name = await _enrich_from_sources("example.com", sources)
    assert result == info
    assert source_name == "second"


async def test_enrich_returns_none_when_no_source_matches() -> None:
    sources = [
        MockSource("a", enrich_result=None),
        MockSource("b", enrich_result=None),
    ]
    result, source_name = await _enrich_from_sources("example.com", sources)
    assert result is None
    assert source_name is None


async def test_enrich_returns_none_for_empty_source_list() -> None:
    result, source_name = await _enrich_from_sources("example.com", [])
    assert result is None
    assert source_name is None


# ---------------------------------------------------------------------------
# _gate_from_sources()
# ---------------------------------------------------------------------------

async def test_gate_returns_first_matching_source() -> None:
    info = _tracker()
    sources = [
        MockSource("first",  gates=True, lookup_result=info),
        MockSource("second", gates=True, lookup_result=_tracker("Other")),
    ]
    result, source_name = await _gate_from_sources("example.com", sources)
    assert result == info
    assert source_name == "first"


async def test_gate_skips_non_gating_sources() -> None:
    info = _tracker()
    sources = [
        MockSource("enrichment_only", gates=False, lookup_result=info),
        MockSource("gating",          gates=True,  lookup_result=info),
    ]
    result, source_name = await _gate_from_sources("example.com", sources)
    assert source_name == "gating"


async def test_gate_returns_none_when_no_match() -> None:
    sources = [MockSource("a", gates=True, lookup_result=None)]
    result, source_name = await _gate_from_sources("example.com", sources)
    assert result is None
    assert source_name is None


async def test_gate_returns_none_when_all_sources_non_gating() -> None:
    sources = [MockSource("a", gates=False, lookup_result=_tracker())]
    result, source_name = await _gate_from_sources("example.com", sources)
    assert result is None


# ---------------------------------------------------------------------------
# _process_batch()
# ---------------------------------------------------------------------------

async def test_process_batch_stores_blocked_queries(db: LocalDatabase) -> None:
    queries = [_query(1, "ads.example.com", status="GRAVITY")]
    sources = [MockSource(enrich_result=_tracker())]

    stored = await _process_batch(queries, sources, db, {})

    assert stored == 1
    results, _ = await db.fetch_queries(limit=10)
    assert len(results) == 1
    assert results[0]["domain"] == "ads.example.com"


async def test_process_batch_stores_allowed_tracker_queries(db: LocalDatabase) -> None:
    info = _tracker()
    queries = [_query(1, "ads.example.com", status="FORWARDED")]
    sources = [MockSource(gates=True, enrich_result=info, lookup_result=info)]

    stored = await _process_batch(queries, sources, db, {})

    assert stored == 1


async def test_process_batch_filters_non_tracker_allowed_queries(db: LocalDatabase) -> None:
    queries = [_query(1, "news.example.com", status="FORWARDED")]
    sources = [MockSource(gates=True, lookup_result=None)]  # not in any tracker source

    stored = await _process_batch(queries, sources, db, {})

    assert stored == 0
    results, _ = await db.fetch_queries(limit=10)
    assert results == []


async def test_process_batch_mixed_blocked_and_allowed(db: LocalDatabase) -> None:
    info = _tracker()
    queries = [
        _query(1, "ads.example.com",  status="GRAVITY"),    # blocked → stored
        _query(2, "track.example.com", status="FORWARDED"), # allowed tracker → stored
        _query(3, "news.example.com",  status="FORWARDED"), # allowed non-tracker → filtered
    ]
    # Source matches "ads" and "track" but not "news"
    class SelectiveSource(MockSource):
        async def lookup_exact(self, domain: str) -> TrackerInfo | None:
            return info if "news" not in domain else None
        async def enrich(self, domain: str) -> TrackerInfo | None:
            return info if "news" not in domain else None

    sources = [SelectiveSource(gates=True)]
    stored = await _process_batch(queries, sources, db, {})

    assert stored == 2


async def test_process_batch_empty_returns_zero(db: LocalDatabase) -> None:
    stored = await _process_batch([], [], db, {})
    assert stored == 0


async def test_process_batch_applies_enrichment_to_blocked_domains(db: LocalDatabase) -> None:
    info = _tracker(name="AcmeAds", category="advertising", company="Acme")
    queries = [_query(1, "ads.example.com", status="GRAVITY")]
    sources = [MockSource(enrich_result=info)]

    await _process_batch(queries, sources, db, {})

    results, _ = await db.fetch_queries(limit=10)
    assert results[0]["tracker_name"] == "AcmeAds"
    assert results[0]["category"] == "advertising"
    assert results[0]["company_name"] == "Acme"


async def test_process_batch_applies_gating_enrichment_to_allowed_domains(db: LocalDatabase) -> None:
    info = _tracker(name="TrackCo", category="analytics", company="Track Corp")
    queries = [_query(1, "track.example.com", status="FORWARDED")]
    sources = [MockSource(gates=True, enrich_result=info, lookup_result=info)]

    await _process_batch(queries, sources, db, {})

    results, _ = await db.fetch_queries(limit=10)
    assert results[0]["tracker_name"] == "TrackCo"


async def test_process_batch_reuses_exact_cache(db: LocalDatabase) -> None:
    """The exact_cache should be populated so repeated domains skip re-lookup."""
    call_count = 0

    class CountingSource(MockSource):
        async def lookup_exact(self, domain: str) -> TrackerInfo | None:
            nonlocal call_count
            call_count += 1
            return _tracker()

    queries = [
        _query(1, "ads.example.com", status="FORWARDED"),
        _query(2, "ads.example.com", status="FORWARDED"),  # same domain again
    ]
    exact_cache: dict = {}
    sources = [CountingSource(gates=True, enrich_result=_tracker())]

    await _process_batch(queries, sources, db, exact_cache)

    assert call_count == 1  # only looked up once despite two queries for same domain


async def test_process_batch_deduplicates_enrichment_by_domain(db: LocalDatabase) -> None:
    """A domain appearing in both blocked and allowed queries should only produce one enrichment row."""
    info = _tracker()
    queries = [
        _query(1, "ads.example.com", status="GRAVITY"),
        _query(2, "ads.example.com", status="FORWARDED"),
    ]
    sources = [MockSource(gates=True, enrich_result=info, lookup_result=info)]

    stored = await _process_batch(queries, sources, db, {})
    assert stored == 2  # both stored (blocked + allowed tracker)

    # Only one domain row should exist
    results, _ = await db.fetch_queries(limit=10)
    domains = {r["domain"] for r in results}
    assert domains == {"ads.example.com"}
