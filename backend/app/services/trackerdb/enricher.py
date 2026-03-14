import logging

from cachetools import LRUCache

from app.models.tracker import TrackerInfo
from app.services.trackerdb.repository import TrackerRepository

logger = logging.getLogger(__name__)

_CACHE_SIZE = 50_000


class TrackerEnricher:
    """
    Enriches a domain with TrackerDB metadata.

    Lookup strategy:
      1. Try exact domain match (e.g. "sub.tracker.com")
      2. Progressively strip subdomains (e.g. "tracker.com")
      3. Return None if no match found

    Results are cached in an LRU cache (50k entries) to avoid
    repeated DB hits for the same domains across queries.
    """

    def __init__(self, repository: TrackerRepository) -> None:
        self._repo = repository
        self._cache: LRUCache = LRUCache(maxsize=_CACHE_SIZE)

    async def enrich(self, domain: str) -> TrackerInfo | None:
        if domain in self._cache:
            return self._cache[domain]

        result = await self._lookup_with_fallback(domain)
        self._cache[domain] = result
        return result

    async def _lookup_with_fallback(self, domain: str) -> TrackerInfo | None:
        # Try the full domain first
        result = await self._repo.lookup_domain(domain)
        if result:
            return result

        # Strip subdomains one level at a time and retry
        parts = domain.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            result = await self._repo.lookup_domain(parent)
            if result:
                logger.debug("Domain %s matched via parent %s", domain, parent)
                return result

        return None

    def invalidate_cache(self) -> None:
        """Clear the LRU cache — call after a TrackerDB update."""
        self._cache.clear()
        logger.info("TrackerEnricher cache invalidated")

    @property
    def cache_info(self) -> dict:
        return {"size": len(self._cache), "maxsize": self._cache.maxsize}
