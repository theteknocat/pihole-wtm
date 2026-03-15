"""
Local SQLite database for storing and querying enriched Pi-hole query data.

Pi-hole query history is append-only: once a query is recorded it never changes.
We sync new queries from Pi-hole periodically, enrich them once, and serve all
dashboard data from here — avoiding repeated live API calls and enrichment passes.
"""

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from app.config import settings
from app.services.pihole.api_client import BLOCKED_STATUSES, QUERY_STATUS_LABELS

logger = logging.getLogger(__name__)

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS domains (
    domain              TEXT PRIMARY KEY,
    tracker_name        TEXT,
    category            TEXT,
    company_name        TEXT,
    company_country     TEXT,
    enrichment_source   TEXT,
    enriched_at         REAL,
    needs_reenrichment  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS queries (
    id          INTEGER PRIMARY KEY,
    timestamp   REAL NOT NULL,
    domain      TEXT NOT NULL REFERENCES domains(domain),
    client_ip   TEXT,
    client_name TEXT,
    status      TEXT NOT NULL,
    query_type  TEXT,
    reply_type  TEXT,
    reply_time  REAL,
    upstream    TEXT,
    list_id     INTEGER
);

CREATE TABLE IF NOT EXISTS sync_state (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    last_query_id   INTEGER NOT NULL DEFAULT 0,
    last_synced_at  REAL
);

CREATE INDEX IF NOT EXISTS idx_queries_timestamp ON queries(timestamp);
CREATE INDEX IF NOT EXISTS idx_queries_status    ON queries(status);
CREATE INDEX IF NOT EXISTS idx_queries_domain    ON queries(domain);
CREATE INDEX IF NOT EXISTS idx_queries_client    ON queries(client_ip);
CREATE INDEX IF NOT EXISTS idx_domains_category  ON domains(category);
CREATE INDEX IF NOT EXISTS idx_domains_company   ON domains(company_name);
"""

# Blocked status placeholders for SQL IN clauses
_BLOCKED_IN = ",".join(f"'{s}'" for s in BLOCKED_STATUSES)


class LocalDatabase:
    def __init__(self, path: str = settings.local_db_path) -> None:
        self._path = path

    @asynccontextmanager
    async def _conn(self):
        """Open a database connection with foreign keys enforced."""
        async with aiosqlite.connect(self._path) as db:
            await db.execute("PRAGMA foreign_keys=ON")
            yield db

    async def init(self) -> None:
        """Create schema and seed sync_state if this is a fresh database."""
        async with self._conn() as db:
            await db.executescript(_SCHEMA)
            # Seed sync_state row if missing (fresh DB)
            await db.execute(
                "INSERT OR IGNORE INTO sync_state (id, last_query_id) VALUES (1, 0)"
            )
            await db.commit()
        logger.info("Local database initialised at %s", self._path)

    # -------------------------------------------------------------------------
    # Sync state
    # -------------------------------------------------------------------------

    async def get_last_query_id(self) -> int:
        async with self._conn() as db:
            async with db.execute("SELECT last_query_id FROM sync_state WHERE id = 1") as cur:
                row = await cur.fetchone()
                return row[0] if row else 0

    async def update_sync_state(self, last_query_id: int) -> None:
        async with self._conn() as db:
            await db.execute(
                "UPDATE sync_state SET last_query_id = ?, last_synced_at = ? WHERE id = 1",
                (last_query_id, time.time()),
            )
            await db.commit()

    # -------------------------------------------------------------------------
    # Domain / enrichment
    # -------------------------------------------------------------------------

    async def upsert_domains(self, domains: list[str]) -> None:
        """Ensure a domain row exists for each domain (no-op if already present)."""
        async with self._conn() as db:
            await db.executemany(
                "INSERT OR IGNORE INTO domains (domain) VALUES (?)",
                [(d,) for d in domains],
            )
            await db.commit()

    async def batch_update_domain_enrichment(
        self,
        updates: list[dict[str, Any]],
    ) -> None:
        """
        Batch-update enrichment for multiple domains in a single DB write.
        Each item in `updates` must have: domain, tracker_name, category,
        company_name, company_country, source (all nullable except domain/source).
        """
        now = time.time()
        rows = [
            (
                u["tracker_name"], u["category"], u["company_name"],
                u["company_country"], u["source"], now, u["domain"],
            )
            for u in updates
        ]
        async with self._conn() as db:
            await db.executemany(
                """UPDATE domains
                   SET tracker_name = ?, category = ?, company_name = ?,
                       company_country = ?, enrichment_source = ?,
                       enriched_at = ?, needs_reenrichment = 0
                   WHERE domain = ?""",
                rows,
            )
            await db.commit()

    async def get_unenriched_domains(self) -> list[str]:
        """Return domains that have been stored but not yet enriched."""
        async with self._conn() as db:
            async with db.execute(
                "SELECT domain FROM domains WHERE enriched_at IS NULL OR needs_reenrichment = 1"
            ) as cur:
                rows = await cur.fetchall()
                return [r[0] for r in rows]

    # -------------------------------------------------------------------------
    # Query insertion
    # -------------------------------------------------------------------------

    async def insert_queries(self, rows: list[dict[str, Any]]) -> None:
        """Insert new query rows. Skips any that already exist (by Pi-hole ID)."""
        async with self._conn() as db:
            await db.executemany(
                """INSERT OR IGNORE INTO queries
                   (id, timestamp, domain, client_ip, client_name, status,
                    query_type, reply_type, reply_time, upstream, list_id)
                   VALUES
                   (:id, :timestamp, :domain, :client_ip, :client_name, :status,
                    :query_type, :reply_type, :reply_time, :upstream, :list_id)""",
                rows,
            )
            await db.commit()

    # -------------------------------------------------------------------------
    # API query methods
    # -------------------------------------------------------------------------

    async def fetch_queries(
        self,
        limit: int = 100,
        cursor: int | None = None,
        status_type: str | None = None,
        tracker_only: bool = False,
    ) -> tuple[list[dict[str, Any]], int | None]:
        """
        Fetch enriched queries from the local DB, newest first.
        cursor is the lowest query ID seen so far (fetch rows with id < cursor).
        """
        conditions = []
        params: list[Any] = []

        if cursor is not None:
            conditions.append("q.id < ?")
            params.append(cursor)

        if status_type == "blocked":
            conditions.append(f"q.status IN ({_BLOCKED_IN})")
        elif status_type == "allowed":
            conditions.append(f"q.status NOT IN ({_BLOCKED_IN})")

        if tracker_only:
            conditions.append("d.category IS NOT NULL")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)

        sql = f"""
            SELECT q.id, q.timestamp, q.domain, q.client_ip, q.client_name,
                   q.status, q.query_type, q.reply_type, q.reply_time,
                   q.upstream, q.list_id,
                   d.tracker_name, d.category, d.company_name, d.company_country
            FROM queries q
            LEFT JOIN domains d ON q.domain = d.domain
            {where}
            ORDER BY q.id DESC
            LIMIT ?
        """

        async with self._conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()

        results = []
        next_cursor = None
        for row in rows:
            status = row["status"]
            results.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "domain": row["domain"],
                "client": row["client_ip"],
                "client_name": row["client_name"],
                "status": status,
                "status_label": QUERY_STATUS_LABELS.get(status, status.lower().replace("_", " ")),
                "query_type": row["query_type"],
                "reply_type": row["reply_type"],
                "reply_time": row["reply_time"],
                "upstream": row["upstream"],
                "list_id": row["list_id"],
                "tracker_name": row["tracker_name"],
                "category": row["category"],
                "company_name": row["company_name"],
                "company_country": row["company_country"],
            })

        if len(rows) == limit:
            next_cursor = rows[-1]["id"]

        return results, next_cursor

    async def fetch_tracker_stats(self, hours: int = 24) -> dict[str, Any]:
        """
        Aggregate tracker stats over the given time window.
        Returns the same shape as the old get_tracker_stats() response.
        """
        from_ts = time.time() - hours * 3600

        sql = f"""
            SELECT
                COALESCE(d.category, 'Unknown')     AS category,
                COALESCE(d.company_name, 'Unknown') AS company_name,
                d.tracker_name,
                q.domain,
                COUNT(*)                            AS query_count,
                SUM(CASE WHEN q.status IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS blocked_count,
                SUM(CASE WHEN q.status NOT IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS allowed_count
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            WHERE q.timestamp >= ?
            GROUP BY d.category, d.company_name, q.domain
            ORDER BY query_count DESC
        """

        async with self._conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, (from_ts,)) as cur:
                rows = await cur.fetchall()

        # Aggregate into the nested category → company → domains structure
        # category_data: {category: {company: {total, blocked, allowed, domains: {domain: count}}}}
        category_data: dict[str, dict[str, dict[str, Any]]] = defaultdict(
            lambda: defaultdict(lambda: {"total": 0, "blocked": 0, "allowed": 0, "domains": {}})
        )

        total_queries = 0
        for row in rows:
            cat = row["category"]
            company = row["company_name"]
            qc = row["query_count"]
            total_queries += qc
            entry = category_data[cat][company]
            entry["total"] += qc
            entry["blocked"] += row["blocked_count"]
            entry["allowed"] += row["allowed_count"]
            entry["domains"][row["domain"]] = qc

        # Only count categories with actual TrackerDB data — 'Unknown' means
        # no TrackerDB match (blocked domain not in the database).
        tracker_total = sum(
            entry["total"]
            for cat, companies in category_data.items()
            if cat != "Unknown"
            for entry in companies.values()
        )

        by_category = []
        for cat, companies in sorted(
            category_data.items(), key=lambda x: -sum(e["total"] for e in x[1].values())
        ):
            company_list = []
            for company, entry in sorted(companies.items(), key=lambda x: -x[1]["total"]):
                top_domains = sorted(
                    [{"domain": d, "query_count": c} for d, c in entry["domains"].items()],
                    key=lambda x: -x["query_count"],
                )[:10]
                company_list.append({
                    "company_name": company,
                    "query_count": entry["total"],
                    "blocked_count": entry["blocked"],
                    "allowed_count": entry["allowed"],
                    "top_domains": top_domains,
                })
            cat_total = sum(e["total"] for e in companies.values())
            by_category.append({
                "category": cat,
                "query_count": cat_total,
                "blocked_count": sum(e["blocked"] for e in companies.values()),
                "allowed_count": sum(e["allowed"] for e in companies.values()),
                "companies": company_list,
            })

        return {
            "window_hours": hours,
            "total_queries": total_queries,
            "tracker_queries": tracker_total,
            "tracker_percent": round(tracker_total / total_queries * 100, 1) if total_queries else 0.0,
            "truncated": False,
            "by_category": by_category,
        }

    async def get_sync_status(self) -> dict[str, Any]:
        async with self._conn() as db:
            async with db.execute(
                "SELECT last_query_id, last_synced_at FROM sync_state WHERE id = 1"
            ) as cur:
                row = await cur.fetchone()
            async with db.execute("SELECT COUNT(*) FROM queries") as cur:
                count_row = await cur.fetchone()

        return {
            "last_query_id": row[0] if row else 0,
            "last_synced_at": row[1] if row else None,
            "stored_queries": count_row[0] if count_row else 0,
        }
