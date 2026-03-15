"""
Disconnect.me tracking protection database.

Downloads and parses Disconnect.me's services.json, which maps domains to
tracker categories (Advertising, Analytics, Social, Content, Cryptomining,
Fingerprinting) and company names. Used as a secondary enrichment source
after TrackerDB.

Data is held in memory — no file cache. Refreshed periodically via the
background sync loop.
"""

import logging
import time

import httpx

from app.config import settings
from app.models.tracker import TrackerInfo

logger = logging.getLogger(__name__)

_SERVICES_URL = (
    "https://raw.githubusercontent.com/disconnectme/"
    "disconnect-tracking-protection/master/services.json"
)


class DisconnectDB:
    """
    In-memory lookup database built from Disconnect.me's services.json.

    Lookup is synchronous and O(1) — data is a plain dict keyed by domain.
    Subdomain fallback strips one level at a time (same strategy as TrackerDB).
    """

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

    async def load(self) -> None:
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

    def lookup(self, domain: str) -> TrackerInfo | None:
        """
        Look up a domain, falling back to parent domains if not found directly.
        Returns None if the domain is not known to Disconnect.me.
        """
        if not self.is_loaded:
            return None

        if domain in self._lookup:
            return self._lookup[domain]

        # Strip subdomains one level at a time
        parts = domain.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            if parent in self._lookup:
                logger.debug("Domain %s matched via parent %s in Disconnect.me", domain, parent)
                return self._lookup[parent]

        return None
