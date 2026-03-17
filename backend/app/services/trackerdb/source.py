"""
TrackerDB source — Ghostery's trackerdb.db as a tracker source plugin.

Downloads the SQLite database from GitHub Releases on startup, queries it
for domain → tracker metadata, and exposes debug/diagnostic API routes.
"""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import aiosqlite
import httpx
from cachetools import LRUCache
from fastapi import APIRouter, Query

from app.config import settings
from app.models.tracker import TrackerInfo

logger = logging.getLogger(__name__)

_CACHE_SIZE = 50_000

_GITHUB_API = "https://api.github.com/repos/ghostery/trackerdb/releases"

# Tables and columns our queries depend on — used to validate a downloaded DB
_REQUIRED_SCHEMA: dict[str, set[str]] = {
    "tracker_domains": {"domain", "tracker"},
    "trackers": {"id", "name", "category_id", "company_id", "alias"},
    "categories": {"id", "name"},
    "companies": {"id", "name", "country"},
}

# Follow alias one level: if a tracker is an alias for another,
# use the parent's category and company.
_LOOKUP_SQL = """
SELECT
    COALESCE(parent.name, t.name)           AS tracker_name,
    COALESCE(pc.name,     c.name)           AS category,
    COALESCE(pco.name,    co.name)          AS company_name,
    COALESCE(pco.country, co.country)       AS company_country
FROM tracker_domains td
JOIN trackers t ON td.tracker = t.id
LEFT JOIN trackers  parent ON t.alias = parent.id
LEFT JOIN categories c   ON t.category_id      = c.id
LEFT JOIN categories pc  ON parent.category_id = pc.id
LEFT JOIN companies  co  ON t.company_id       = co.id
LEFT JOIN companies  pco ON parent.company_id  = pco.id
WHERE td.domain = ?
LIMIT 1
"""

_CATEGORIES_SQL = """
SELECT c.name, COUNT(td.domain) AS domain_count
FROM categories c
LEFT JOIN trackers t ON t.category_id = c.id
LEFT JOIN tracker_domains td ON td.tracker = t.id
GROUP BY c.id, c.name
ORDER BY domain_count DESC
"""


class TrackerDbLoadError(Exception):
    pass


class TrackerDBSource:
    """
    Enriches domains with TrackerDB metadata (Ghostery's trackerdb.db).

    Implements the TrackerSource protocol with two lookup strategies:
      - lookup_exact(): direct DB hit, no fallback — for storage gating
      - enrich(): subdomain fallback (sub.tracker.com → tracker.com) + LRU
        cache — for display enrichment of already-stored domains

    Manages its own lifecycle: downloads the DB on initialize(), validates
    the schema, and exposes debug routes via api_router().
    """

    source_name = "trackerdb"
    label = "TrackerDB (Ghostery)"
    gates = True
    priority = 10

    def __init__(self) -> None:
        self._path = Path(settings.trackerdb_path)
        self._cache: LRUCache = LRUCache(maxsize=_CACHE_SIZE)

    # -- Lifecycle ------------------------------------------------------------

    async def initialize(self) -> None:
        """Download trackerdb.db from GitHub Releases if missing or stale."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self._is_stale():
            logger.debug("TrackerDB is up to date at %s", self._path)
            return

        logger.info("TrackerDB is missing or stale — downloading from GitHub Releases")
        try:
            download_url, tag = await self._get_download_url()
            logger.info("Downloading TrackerDB release %s", tag)
            await self._download(download_url)
            logger.info("TrackerDB updated to release %s (%s)", tag, self._path)
        except Exception as e:
            if self._path.exists():
                logger.warning("TrackerDB download failed, keeping existing file: %s", e)
            else:
                raise TrackerDbLoadError(f"TrackerDB unavailable and no local copy: {e}") from e

    async def refresh_if_stale(self) -> None:
        """Re-download TrackerDB if the file has become stale."""
        if not self._is_stale():
            return
        mtime_before = self._path.stat().st_mtime if self._path.exists() else None
        await self.initialize()
        mtime_after = self._path.stat().st_mtime if self._path.exists() else None
        if mtime_after != mtime_before:
            self._cache.clear()
            logger.info("TrackerDB refreshed and cache invalidated")

    # -- Protocol: lookup / enrich --------------------------------------------

    async def lookup_exact(self, domain: str) -> TrackerInfo | None:
        """
        Exact-match lookup only — no subdomain fallback.

        Used for storage gating to avoid pulling in legitimate service domains
        (e.g. mail.google.com) via a parent company's tracker entry (google.com).
        Does not use or populate the LRU cache, which stores fallback results.
        """
        return await self._lookup_domain(domain)

    async def enrich(self, domain: str) -> TrackerInfo | None:
        """Full enrichment with subdomain fallback and LRU cache."""
        if domain in self._cache:
            return self._cache[domain]

        result = await self._lookup_with_fallback(domain)
        self._cache[domain] = result
        return result

    # -- Health ---------------------------------------------------------------

    async def health_check(self) -> dict:
        loaded = self._path.exists()
        categories = await self.get_categories() if loaded else []
        domain_count = sum(c["domain_count"] for c in categories)
        return {
            "loaded": loaded,
            "domain_count": domain_count,
            "category_count": len(categories),
        }

    # -- API routes -----------------------------------------------------------

    def api_router(self) -> APIRouter:
        """Debug/diagnostic endpoints for TrackerDB."""
        router = APIRouter(
            prefix=f"/api/sources/{self.source_name}",
            tags=[self.source_name],
        )

        @router.get("/status")
        async def status() -> dict[str, Any]:
            return {
                "loaded": self._path.exists(),
                "cache": {"size": len(self._cache), "maxsize": self._cache.maxsize},
                "categories": await self.get_categories(),
            }

        @router.get("/lookup")
        async def lookup(domain: str = Query(...)) -> dict[str, Any]:
            result = await self.enrich(domain)
            if result is None:
                return {"domain": domain, "found": False}
            return {"domain": domain, "found": True, **result.model_dump()}

        return router

    # -- TrackerDB-specific ---------------------------------------------------

    async def get_categories(self) -> list[dict[str, Any]]:
        """Return all TrackerDB categories with their domain counts."""
        try:
            async with aiosqlite.connect(str(self._path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(_CATEGORIES_SQL) as cursor:
                    rows = await cursor.fetchall()
                    return [{"category": row["name"], "domain_count": row["domain_count"]} for row in rows]
        except Exception as e:
            logger.warning("TrackerDB categories query failed: %s", e)
            return []

    # -- Internal helpers -----------------------------------------------------

    def _is_stale(self) -> bool:
        if not self._path.exists():
            return True
        if settings.trackerdb_update_interval_hours == 0:
            return False
        age_hours = (time.time() - self._path.stat().st_mtime) / 3600
        return age_hours >= settings.trackerdb_update_interval_hours

    async def _get_download_url(self) -> tuple[str, str]:
        """Return (download_url, tag_name) for the configured release."""
        release = settings.trackerdb_release
        if release == "latest":
            url = f"{_GITHUB_API}/latest"
        else:
            url = f"{_GITHUB_API}/tags/{release}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()

        data = response.json()
        tag = data["tag_name"]
        for asset in data.get("assets", []):
            if asset["name"] == "trackerdb.db":
                return asset["browser_download_url"], tag

        raise TrackerDbLoadError(f"No trackerdb.db asset found in release {tag}")

    @staticmethod
    def _validate_schema(db_path: Path) -> list[str]:
        """Check that the DB has the tables and columns we depend on."""
        errors: list[str] = []
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}

                for table, required_cols in _REQUIRED_SCHEMA.items():
                    if table not in existing_tables:
                        errors.append(f"Missing table: {table}")
                        continue
                    cursor.execute(f"PRAGMA table_info({table})")  # noqa: S608
                    existing_cols = {row[1] for row in cursor.fetchall()}
                    missing = required_cols - existing_cols
                    if missing:
                        errors.append(f"Table '{table}' missing columns: {missing}")
        except sqlite3.Error as e:
            errors.append(f"SQLite error during schema validation: {e}")
        return errors

    async def _download(self, url: str) -> None:
        """Download a file to self._path, writing atomically via a .tmp file."""
        tmp = self._path.with_suffix(".db.tmp")
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                with tmp.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

        errors = self._validate_schema(tmp)
        if errors:
            tmp.unlink(missing_ok=True)
            raise TrackerDbLoadError(
                f"Downloaded TrackerDB failed schema validation: {'; '.join(errors)}"
            )
        tmp.rename(self._path)

    async def _lookup_domain(self, domain: str) -> TrackerInfo | None:
        """Return tracker info for an exact domain match, or None."""
        try:
            async with aiosqlite.connect(str(self._path)) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(_LOOKUP_SQL, (domain,)) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        return None
                    return TrackerInfo(
                        tracker_name=row["tracker_name"],
                        category=row["category"] or "misc",
                        company_name=row["company_name"],
                        company_country=row["company_country"],
                    )
        except Exception as e:
            logger.warning("TrackerDB lookup failed for %s: %s", domain, e)
            return None

    async def _lookup_with_fallback(self, domain: str) -> TrackerInfo | None:
        result = await self._lookup_domain(domain)
        if result:
            return result

        # Strip subdomains one level at a time and retry
        parts = domain.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            result = await self._lookup_domain(parent)
            if result:
                logger.debug("Domain %s matched via parent %s", domain, parent)
                return result

        return None
