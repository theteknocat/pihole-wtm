"""
TrackerSource protocol — common interface for tracker/enrichment data sources.

All sources (TrackerDB, Disconnect.me, future additions) implement this
protocol so the sync service can iterate over them uniformly for both
storage gating (exact match) and display enrichment (with fallback).

Sources self-describe their capabilities (gating vs enrichment-only) and
priority order. They can also register their own API routes for
debug/diagnostic endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.models.tracker import TrackerInfo

if TYPE_CHECKING:
    from fastapi import APIRouter


@runtime_checkable
class TrackerSource(Protocol):
    @property
    def source_name(self) -> str:
        """Short identifier used in the domains table (e.g. 'trackerdb', 'disconnect')."""
        ...

    @property
    def gates(self) -> bool:
        """Whether this source participates in allowed-query storage gating."""
        ...

    @property
    def priority(self) -> int:
        """Lower values are tried first during gating and enrichment."""
        ...

    async def initialize(self) -> None:
        """One-time startup: download data, open connections, etc."""
        ...

    async def lookup_exact(self, domain: str) -> TrackerInfo | None:
        """
        Exact domain match only — no subdomain fallback.

        Used for storage gating: decides whether an allowed query is worth
        storing. Exact-match prevents legitimate subdomains (mail.google.com)
        being pulled in because a parent company (google.com) appears in the
        source as an ad-network operator.
        """
        ...

    async def enrich(self, domain: str) -> TrackerInfo | None:
        """
        Full enrichment lookup, may include source-specific fallback strategies
        (e.g. subdomain walking for TrackerDB). Used to populate display
        metadata for already-stored domains.
        """
        ...

    async def refresh_if_stale(self) -> None:
        """Re-download/reload source data if stale. No-op if fresh."""
        ...

    def api_router(self) -> APIRouter | None:
        """Optional FastAPI router for source-specific debug/diagnostic endpoints."""
        ...


def get_tracker_sources() -> list[TrackerSource]:
    """
    Instantiate and return all configured tracker sources, sorted by priority.

    This is the single registration point — add new sources here.
    """
    from app.services.disconnect.source import DisconnectSource
    from app.services.trackerdb.source import TrackerDBSource

    sources: list[TrackerSource] = [
        TrackerDBSource(),
        DisconnectSource(),
    ]
    return sorted(sources, key=lambda s: s.priority)
