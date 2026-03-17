"""
Disconnect.me tracking protection source plugin.

Downloads and parses Disconnect.me's services.json, which maps domains to
tracker categories (Advertising, Analytics, Social, Content, Cryptomining,
Fingerprinting) and company names. Used as a secondary enrichment source
after TrackerDB.

Data is held in memory — no file cache. Refreshed periodically when stale.
"""

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Query

from app.config import settings
from app.models.tracker import TrackerInfo

logger = logging.getLogger(__name__)

_SERVICES_URL = (
    "https://raw.githubusercontent.com/disconnectme/"
    "disconnect-tracking-protection/master/services.json"
)


class DisconnectSource:
    """
    In-memory lookup database built from Disconnect.me's services.json.

    Implements the TrackerSource protocol. All lookups are exact-match only —
    Disconnect.me lists root domains of companies that *operate* ad/tracker
    networks, so subdomain fallback would incorrectly flag legitimate services.

    Lookup is synchronous and O(1) — data is a plain dict keyed by domain.
    """

    source_name = "disconnect"
    label = "Disconnect.me"
    gates = True
    priority = 20

    def __init__(self) -> None:
        self._lookup: dict[str, TrackerInfo] = {}
        self._loaded_at: float | None = None

    @property
    def is_loaded(self) -> bool:
        return self._loaded_at is not None

    @property
    def is_stale(self) -> bool:
        if self._loaded_at is None:
            return True
        if settings.disconnect_update_interval_hours == 0:
            return False
        age_hours = (time.time() - self._loaded_at) / 3600
        return age_hours >= settings.disconnect_update_interval_hours

    # -- Lifecycle ------------------------------------------------------------

    async def initialize(self) -> None:
        """Download and parse services.json into memory."""
        await self._load()

    async def refresh_if_stale(self) -> None:
        """Re-download services.json if the data has become stale."""
        if self.is_stale:
            await self._load()

    # -- Protocol: lookup / enrich --------------------------------------------

    async def lookup_exact(self, domain: str) -> TrackerInfo | None:
        """Exact domain match. Returns None if not loaded or not found."""
        if not self.is_loaded:
            return None
        return self._lookup.get(domain)

    async def enrich(self, domain: str) -> TrackerInfo | None:
        """Same as lookup_exact — Disconnect.me has no fallback strategy."""
        return await self.lookup_exact(domain)

    # -- Health ---------------------------------------------------------------

    async def health_check(self) -> dict:
        return {
            "loaded": self.is_loaded,
            "domain_count": len(self._lookup),
        }

    # -- API routes -----------------------------------------------------------

    def api_router(self) -> APIRouter:
        """Debug/diagnostic endpoints for Disconnect.me."""
        router = APIRouter(
            prefix=f"/api/sources/{self.source_name}",
            tags=[self.source_name],
        )

        @router.get("/status")
        async def status() -> dict[str, Any]:
            return {
                "loaded": self.is_loaded,
                "domain_count": len(self._lookup),
                "loaded_at": self._loaded_at,
            }

        @router.get("/lookup")
        async def lookup(domain: str = Query(...)) -> dict[str, Any]:
            result = await self.lookup_exact(domain)
            if result is None:
                return {"domain": domain, "found": False}
            return {"domain": domain, "found": True, **result.model_dump()}

        return router

    # -- Internal helpers -----------------------------------------------------

    async def _load(self) -> None:
        """Download and parse services.json into memory."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(_SERVICES_URL)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            if self.is_loaded:
                logger.warning("Disconnect.me download failed, keeping existing data: %s", e)
            else:
                logger.error("Disconnect.me unavailable and no data loaded: %s", e)
            return

        lookup: dict[str, TrackerInfo] = {}
        categories = data.get("categories", {})

        for raw_category, company_list in categories.items():
            category = raw_category.lower()
            for company_obj in company_list:
                for company_name, url_to_domains in company_obj.items():
                    for domains in url_to_domains.values():
                        for domain in domains:
                            lookup[domain] = TrackerInfo(
                                tracker_name=company_name,
                                category=category,
                                company_name=company_name,
                                company_country=None,
                            )

        self._lookup = lookup
        self._loaded_at = time.time()
        logger.info(
            "Disconnect.me loaded: %d domains across %d categories",
            len(lookup),
            len(categories),
        )
