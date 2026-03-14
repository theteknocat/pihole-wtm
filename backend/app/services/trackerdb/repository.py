import logging
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings
from app.models.tracker import TrackerInfo

logger = logging.getLogger(__name__)

# Follow alias one level: if a tracker is an alias for another,
# use the parent's category and company.
LOOKUP_SQL = """
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

CATEGORIES_SQL = """
SELECT c.name, COUNT(td.domain) AS domain_count
FROM categories c
LEFT JOIN trackers t ON t.category_id = c.id
LEFT JOIN tracker_domains td ON td.tracker = t.id
GROUP BY c.id, c.name
ORDER BY domain_count DESC
"""


class TrackerRepository:
    def __init__(self) -> None:
        self._path = str(Path(settings.trackerdb_path))

    async def lookup_domain(self, domain: str) -> TrackerInfo | None:
        """Return tracker info for an exact domain match, or None."""
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(LOOKUP_SQL, (domain,)) as cursor:
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

    async def get_categories(self) -> list[dict[str, Any]]:
        """Return all categories with their domain counts."""
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(CATEGORIES_SQL) as cursor:
                    rows = await cursor.fetchall()
                    return [{"category": row["name"], "domain_count": row["domain_count"]} for row in rows]
        except Exception as e:
            logger.warning("TrackerDB categories query failed: %s", e)
            return []
