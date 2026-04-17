"""
Local SQLite database for storing and querying enriched Pi-hole query data.

Pi-hole query history is append-only: once a query is recorded it never changes.
We sync new queries from Pi-hole periodically, enrich them once, and serve all
dashboard data from here — avoiding repeated live API calls and enrichment passes.
"""

import json
import logging
import time
from collections import defaultdict
from typing import Any

import aiosqlite

from app.config import DATA_DIR
from app.services.pihole.api_client import BLOCKED_STATUSES, QUERY_STATUS_LABELS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema migrations — forward-only, version-stamped
#
# Each entry is (version, description, sql). On startup, init() checks the
# current schema_version and applies any migrations with a higher version
# number in order. Migration 1 is the initial schema — there is no separate
# "bootstrap" path.
#
# Rules for adding migrations:
#   - Append a new tuple; never modify existing entries.
#   - Use IF NOT EXISTS / IF EXISTS where possible so migrations are safe.
# ---------------------------------------------------------------------------

_MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "initial schema",
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            id      INTEGER PRIMARY KEY DEFAULT 1,
            version INTEGER NOT NULL
        );

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
        """,
    ),
    (
        2,
        "add user_config table",
        """
        CREATE TABLE IF NOT EXISTS user_config (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        );
        """,
    ),
    (
        3,
        "replace client_name column with client_names table",
        """
        ALTER TABLE queries DROP COLUMN client_name;

        CREATE TABLE IF NOT EXISTS client_names (
            client_ip   TEXT PRIMARY KEY,
            name        TEXT NOT NULL
        );
        """,
    ),
]


async def _get_schema_version(db: aiosqlite.Connection) -> int:
    """Return current schema version, or 0 if the version table doesn't exist."""
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ) as cur:
        if not await cur.fetchone():
            return 0
    async with db.execute("SELECT version FROM schema_version WHERE id = 1") as cur:
        row = await cur.fetchone()
        return row[0] if row else 0


async def _apply_migrations(db: aiosqlite.Connection) -> None:
    """Run any pending migrations and update the stored schema version."""
    current = await _get_schema_version(db)

    for version, description, sql in _MIGRATIONS:
        if version <= current:
            continue
        logger.info("Applying migration %d: %s", version, description)
        await db.executescript(sql)
        await db.execute(
            "INSERT OR REPLACE INTO schema_version (id, version) VALUES (1, ?)",
            (version,),
        )
        await db.commit()

    final = await _get_schema_version(db)
    logger.info("Database schema at version %d", final)

# Blocked status placeholders for SQL IN clauses
_BLOCKED_IN = ",".join(f"'{s}'" for s in BLOCKED_STATUSES)


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcard characters so they match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class LocalDatabase:
    def __init__(self, path: str | None = None) -> None:
        self._path = path or str(DATA_DIR / "pihole_wtm.db")
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Open the persistent connection, apply migrations, and seed sync_state."""
        self._db = await aiosqlite.connect(self._path)
        self._db.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await _apply_migrations(self._db)
        # Seed sync_state row if missing (fresh DB)
        await self._conn.execute(
            "INSERT OR IGNORE INTO sync_state (id, last_query_id) VALUES (1, 0)"
        )
        await self._conn.commit()
        logger.info("Local database initialised at %s", self._path)

    async def close(self) -> None:
        """Close the persistent database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        """Return the open connection, raising if init() has not been called."""
        if self._db is None:
            raise RuntimeError("Database not initialised — call init() first")
        return self._db

    # -------------------------------------------------------------------------
    # Sync state
    # -------------------------------------------------------------------------

    async def get_last_query_id(self) -> int:
        async with self._conn.execute("SELECT last_query_id FROM sync_state WHERE id = 1") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    async def update_sync_state(self, last_query_id: int) -> None:
        await self._conn.execute(
            "UPDATE sync_state SET last_query_id = ?, last_synced_at = ? WHERE id = 1",
            (last_query_id, time.time()),
        )
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # Domain / enrichment
    # -------------------------------------------------------------------------

    async def upsert_domains(self, domains: list[str]) -> None:
        """Ensure a domain row exists for each domain (no-op if already present)."""
        await self._conn.executemany(
            "INSERT OR IGNORE INTO domains (domain) VALUES (?)",
            [(d,) for d in domains],
        )
        await self._conn.commit()

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
        await self._conn.executemany(
            """UPDATE domains
               SET tracker_name = ?, category = ?, company_name = ?,
                   company_country = ?, enrichment_source = ?,
                   enriched_at = ?, needs_reenrichment = 0
               WHERE domain = ?""",
            rows,
        )
        await self._conn.commit()

    async def get_unenriched_domains(self) -> list[str]:
        """Return domains that have been stored but not yet enriched."""
        async with self._conn.execute(
            "SELECT domain FROM domains WHERE enriched_at IS NULL OR needs_reenrichment = 1"
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def flag_heuristic_uncategorized_for_reenrichment(self) -> int:
        """
        Mark heuristic-enriched domains that have no category for re-enrichment.
        Called on startup so that newly added subdomain keyword mappings are
        applied to domains that were previously enriched without a category.
        Returns the number of domains flagged.
        """
        cursor = await self._conn.execute(
            """UPDATE domains SET needs_reenrichment = 1
               WHERE enrichment_source = 'heuristic' AND category IS NULL"""
        )
        await self._conn.commit()
        return cursor.rowcount

    async def flag_for_reenrichment(self, domain: str | None = None) -> int:
        """
        Mark one or all heuristic-enriched and rdap_failed domains for re-enrichment.
        The sync service will re-process them on the next cycle.
        Returns the number of domains flagged.
        """
        params: list[Any] = []
        if domain is not None:
            where = "domain = ?"
            params.append(domain)
        else:
            where = "enrichment_source IN ('heuristic', 'rdap_failed')"

        # ruff: disable[S608]
        sql = f"""
            UPDATE domains SET needs_reenrichment = 1
               WHERE {where}
        """
        # ruff: enable[S608]

        cursor = await self._conn.execute(sql, params)

        await self._conn.commit()
        return cursor.rowcount

    async def get_heuristic_domains(self) -> list[dict[str, Any]]:
        """Return domains enriched only via the eTLD+1 heuristic — candidates for RDAP upgrade."""
        async with self._conn.execute(
            "SELECT domain, tracker_name, category, company_name"
            " FROM domains WHERE enrichment_source = 'heuristic'"
        ) as cur:
            rows = await cur.fetchall()
            return [
                {
                    "domain": r["domain"],
                    "tracker_name": r["tracker_name"],
                    "category": r["category"],
                    "company_name": r["company_name"],
                }
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Query insertion
    # -------------------------------------------------------------------------

    async def insert_queries(self, rows: list[dict[str, Any]]) -> None:
        """Insert new query rows. Skips any that already exist (by Pi-hole ID)."""
        await self._conn.executemany(
            """INSERT OR IGNORE INTO queries
               (id, timestamp, domain, client_ip, status,
                query_type, reply_type, reply_time, upstream, list_id)
               VALUES
               (:id, :timestamp, :domain, :client_ip, :status,
                :query_type, :reply_type, :reply_time, :upstream, :list_id)""",
            rows,
        )
        await self._conn.commit()

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

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT q.id, q.timestamp, q.domain, q.client_ip,
                   cn.name AS client_name,
                   q.status, q.query_type, q.reply_type, q.reply_time,
                   d.tracker_name, d.category, d.company_name, d.company_country
            FROM queries q
            LEFT JOIN domains d ON q.domain = d.domain
            LEFT JOIN client_names cn ON q.client_ip = cn.client_ip
            {where}
            ORDER BY q.id DESC
            LIMIT ?
        """
        # ruff: enable[S608]

        async with self._conn.execute(sql, params) as cur:
            rows = list(await cur.fetchall())

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
                "tracker_name": row["tracker_name"],
                "category": row["category"],
                "company_name": row["company_name"],
                "company_country": row["company_country"],
            })

        if len(rows) == limit:
            next_cursor = rows[-1]["id"]

        return results, next_cursor

    async def fetch_queries_grouped(
        self,
        limit: int = 10,
        status_type: str | None = None,
        tracker_only: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent queries grouped by consecutive same-domain runs.
        Fetches a pool of (limit * 5) raw rows and collapses consecutive
        runs of the same domain into a single row with a query_count.
        """
        pool = limit * 5
        conditions: list[str] = []
        params: list[Any] = []

        if status_type == "blocked":
            conditions.append(f"q.status IN ({_BLOCKED_IN})")
        elif status_type == "allowed":
            conditions.append(f"q.status NOT IN ({_BLOCKED_IN})")

        if tracker_only:
            conditions.append("d.category IS NOT NULL")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # ruff: disable[S608]
        sql = f"""
            WITH base AS (
                SELECT q.id, q.timestamp, q.domain,
                    d.tracker_name, d.category, d.company_name, d.company_country
                FROM queries q
                LEFT JOIN domains d ON q.domain = d.domain
                LEFT JOIN client_names cn ON q.client_ip = cn.client_ip
                {where}
                ORDER BY q.id DESC
                LIMIT ?
            ),
            bounded AS (
                SELECT *,
                    CASE WHEN LAG(domain) OVER (ORDER BY id DESC)
                        IS DISTINCT FROM domain THEN 1 ELSE 0 END AS is_boundary
                FROM base
            ),
            islands AS (
                SELECT *,
                    SUM(is_boundary) OVER (
                        ORDER BY id DESC ROWS UNBOUNDED PRECEDING
                    ) AS island_id
                FROM bounded
            )
            SELECT
                domain,
                MAX(timestamp)    AS timestamp,
                COUNT(*)          AS query_count,
                MAX(company_name) AS company_name,
                MAX(tracker_name) AS tracker_name,
                MAX(category)     AS category,
                MAX(company_country) AS company_country
            FROM islands
            GROUP BY island_id
            ORDER BY island_id ASC
            LIMIT ?
        """
        # ruff: enable[S608]

        params.extend([pool, limit])

        async with self._conn.execute(sql, params) as cur:
            rows = list(await cur.fetchall())

        return [
            {
                "domain": row["domain"],
                "timestamp": row["timestamp"],
                "query_count": row["query_count"],
                "company_name": row["company_name"],
                "tracker_name": row["tracker_name"],
                "category": row["category"],
                "company_country": row["company_country"],
            }
            for row in rows
        ]

    async def _apply_exclusions(
        self, conditions: list[str], params: list[Any],
    ) -> None:
        """Load user exclusion settings and append WHERE clauses in place."""
        raw = await self.get_all_config()
        for key, col in (
            ("excluded_categories", "COALESCE(d.category, 'Uncategorized')"),
            ("excluded_companies", "COALESCE(d.company_name, 'Unknown')"),
            ("excluded_domains", "q.domain"),
        ):
            values = json.loads(raw.get(key, "[]"))
            if values:
                placeholders = ",".join("?" for _ in values)
                conditions.append(f"{col} NOT IN ({placeholders})")
                params.extend(values)

    async def fetch_tracker_stats(
        self,
        hours: int = 24,
        end_ts: float | None = None,
        client_ip: str | None = None,
        include_timeline: bool = False,
    ) -> dict[str, Any]:
        """
        Aggregate tracker stats over the given time window.
        Optionally filter to a single client device by IP.
        When include_timeline=True, also returns bucketed timeline series for
        category and company dimensions (used by the device stats dialog).
        """
        result = await self._fetch_tracker_breakdown(
            hours=hours, end_ts=end_ts, client_ip=client_ip
        )
        if include_timeline:
            timeline = await self._fetch_tracker_timeline(
                hours=hours, end_ts=end_ts, client_ip=client_ip
            )
            result.update(timeline)
        return result

    async def _fetch_tracker_breakdown(
        self,
        hours: int = 24,
        end_ts: float | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Core tracker breakdown query: returns category/company counts for the
        given time window, optionally filtered to one client IP.
        """
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600
        conditions = ["q.timestamp >= ?", "q.timestamp <= ?"]
        params: list[Any] = [from_ts, anchor]

        if client_ip:
            conditions.append("q.client_ip = ?")
            params.append(client_ip)

        await self._apply_exclusions(conditions, params)

        where = "WHERE " + " AND ".join(conditions)

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT
                COALESCE(d.category, 'Uncategorized')     AS category,
                COALESCE(d.company_name, 'Unknown')       AS company_name,
                d.tracker_name,
                q.domain,
                COUNT(*)                            AS query_count,
                SUM(CASE WHEN q.status IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS blocked_count,
                SUM(CASE WHEN q.status NOT IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS allowed_count
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            {where}
            GROUP BY d.category, d.company_name, q.domain
            ORDER BY query_count DESC
        """
        # ruff: enable[S608]

        async with self._conn.execute(sql, params) as cur:
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

        # Only count categories with actual enrichment data — 'Uncategorized'
        # means the domain had no category from any enrichment source.
        tracker_total = sum(
            entry["total"]
            for cat, companies in category_data.items()
            if cat != "Uncategorized"
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
            "tracker_percent": round(tracker_total / total_queries * 100, 1)
            if total_queries
            else 0.0,
            "truncated": False,
            "by_category": by_category,
        }

    async def _fetch_tracker_timeline(
        self,
        hours: int = 24,
        end_ts: float | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Return per-category and per-company tracker query counts bucketed over
        time. Uses the same adaptive bucket sizing as fetch_timeline_stats.
        All companies are returned; the frontend applies the top-N + Other cap.
        """
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600

        if hours <= 24:
            bucket_seconds = 3600
        elif hours <= 168:
            bucket_seconds = 6 * 3600
        elif hours <= 720:
            bucket_seconds = 24 * 3600
        else:
            bucket_seconds = 72 * 3600

        conditions = ["q.timestamp >= ?", "q.timestamp <= ?"]
        params: list[Any] = [from_ts, anchor]

        if client_ip:
            conditions.append("q.client_ip = ?")
            params.append(client_ip)

        await self._apply_exclusions(conditions, params)

        where = "WHERE " + " AND ".join(conditions)

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT
                COALESCE(d.category, 'Uncategorized')   AS category,
                COALESCE(d.company_name, 'Unknown')     AS company_name,
                CAST((q.timestamp - ?) / ? AS INTEGER)  AS bucket,
                COUNT(*)                                AS count
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            {where}
            GROUP BY category, company_name, bucket
            ORDER BY category, company_name, bucket
        """
        # ruff: enable[S608]

        params = [from_ts, bucket_seconds] + params

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()

        num_buckets = hours * 3600 // bucket_seconds + 1
        bucket_timestamps = [from_ts + i * bucket_seconds for i in range(num_buckets)]

        # Accumulate counts into per-category and per-company dicts keyed by bucket index
        cat_buckets: dict[str, list[int]] = {}
        co_buckets: dict[str, list[int]] = {}

        for row in rows:
            cat = row["category"]
            company = row["company_name"]
            b = int(row["bucket"])
            if b < 0 or b >= num_buckets:
                continue

            if cat not in cat_buckets:
                cat_buckets[cat] = [0] * num_buckets
            cat_buckets[cat][b] += row["count"]

            if company not in co_buckets:
                co_buckets[company] = [0] * num_buckets
            co_buckets[company][b] += row["count"]

        by_category_timeline = [
            {"category": cat, "counts": counts}
            for cat, counts in cat_buckets.items()
        ]
        by_company_timeline = [
            {"company_name": co, "counts": counts}
            for co, counts in co_buckets.items()
        ]

        return {
            "bucket_seconds": bucket_seconds,
            "bucket_timestamps": bucket_timestamps,
            "by_category_timeline": by_category_timeline,
            "by_company_timeline": by_company_timeline,
        }

    async def search_domains(
        self, query: str, hours: int = 24, end_ts: float | None = None, limit: int = 20
    ) -> list[str]:
        """Return domain names matching the query substring within the time window."""
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600
        sql = """
            SELECT DISTINCT q.domain
            FROM queries q
            WHERE q.timestamp >= ? AND q.timestamp <= ? AND q.domain LIKE ? ESCAPE '\\'
            ORDER BY q.domain
            LIMIT ?
        """
        async with self._conn.execute(
            sql, [from_ts, anchor, f"%{_escape_like(query)}%", limit]
        ) as cur:
            return [row[0] for row in await cur.fetchall()]

    async def fetch_domain_stats(
        self,
        hours: int = 24,
        end_ts: float | None = None,
        category: str | None = None,
        company: str | None = None,
        client_ip: str | None = None,
        domain: str | None = None,
        domain_exact: bool = False,
    ) -> dict[str, Any]:
        """
        Return per-domain query counts for the given time window, optionally
        filtered to a single tracker category, company, or client device.
        """
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600
        conditions = ["q.timestamp >= ?", "q.timestamp <= ?"]
        params: list[Any] = [from_ts, anchor]

        if client_ip is not None:
            conditions.append("q.client_ip = ?")
            params.append(client_ip)

        if category is not None:
            conditions.append("COALESCE(d.category, 'Uncategorized') = ?")
            params.append(category)
        if company is not None:
            conditions.append("COALESCE(d.company_name, 'Unknown') = ?")
            params.append(company)
        if domain is not None:
            if domain_exact:
                conditions.append("q.domain = ?")
                params.append(domain)
            else:
                conditions.append("q.domain LIKE ? ESCAPE '\\'")
                params.append(f"%{_escape_like(domain)}%")

        await self._apply_exclusions(conditions, params)

        where = "WHERE " + " AND ".join(conditions)

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT
                q.domain,
                COALESCE(d.category, 'Uncategorized')   AS category,
                COALESCE(d.company_name, 'Unknown')     AS company_name,
                d.tracker_name,
                d.enrichment_source,
                d.needs_reenrichment,
                COUNT(*)                                AS query_count,
                SUM(CASE WHEN q.status IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS blocked_count,
                SUM(CASE WHEN q.status NOT IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS allowed_count
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            {where}
            GROUP BY q.domain
            ORDER BY query_count DESC
        """
        # ruff: enable[S608]

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()

        return {
            "window_hours": hours,
            "filter_category": category,
            "filter_company": company,
            "domains": [
                {
                    "domain": row["domain"],
                    "category": row["category"],
                    "company_name": row["company_name"],
                    "tracker_name": row["tracker_name"],
                    "can_reenrich": row["needs_reenrichment"] == 0 and
                    row["enrichment_source"] == "rdap_failed",
                    "rdap_pending": row["needs_reenrichment"] == 1 or
                    row["enrichment_source"] == "heuristic",
                    "query_count": row["query_count"],
                    "blocked_count": row["blocked_count"],
                    "allowed_count": row["allowed_count"],
                    "block_rate": round(row["blocked_count"] / row["query_count"] * 100, 1)
                    if row["query_count"] else 0.0,
                }
                for row in rows
            ],
        }

    async def fetch_client_stats(
        self,
        hours: int = 24,
        end_ts: float | None = None,
        category: str | None = None,
        company: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """
        Return per-client query counts for the given time window,
        optionally filtered to a single category, company, or domain.
        Joins client_names to include user-defined friendly names.
        """
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600
        conditions = ["q.timestamp >= ?", "q.timestamp <= ?"]
        params: list[Any] = [from_ts, anchor]

        if category is not None:
            conditions.append("COALESCE(d.category, 'Uncategorized') = ?")
            params.append(category)
        if company is not None:
            conditions.append("COALESCE(d.company_name, 'Unknown') = ?")
            params.append(company)
        if domain is not None:
            conditions.append("q.domain = ?")
            params.append(domain)
        else:
            # Apply global exclusions ONLY when a domain is not
            # specified.
            await self._apply_exclusions(conditions, params)

        where = "WHERE " + " AND ".join(conditions)

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT
                q.client_ip,
                cn.name AS client_name,
                COUNT(*)                                AS query_count,
                SUM(CASE WHEN q.status IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS blocked_count,
                SUM(CASE WHEN q.status NOT IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS allowed_count
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            LEFT JOIN client_names cn ON q.client_ip = cn.client_ip
            {where}
            GROUP BY q.client_ip
            ORDER BY query_count DESC
        """
        # ruff: enable[S608]

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()

        return {
            "window_hours": hours,
            "clients": [
                {
                    "client_ip": row["client_ip"],
                    "client_name": row["client_name"],
                    "query_count": row["query_count"],
                    "blocked_count": row["blocked_count"],
                    "allowed_count": row["allowed_count"],
                    "block_rate": round(row["blocked_count"] / row["query_count"] * 100, 1)
                    if row["query_count"] else 0.0,
                }
                for row in rows
            ],
        }

    async def fetch_timeline_stats(
        self,
        hours: int = 24,
        end_ts: float | None = None,
    ) -> dict[str, Any]:
        """
        Return query counts bucketed over time for the given window.
        Bucket size adapts to the window length.
        """
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600

        # Choose bucket size in seconds based on window length
        if hours <= 24:
            bucket_seconds = 3600       # 1 hour
        elif hours <= 168:
            bucket_seconds = 6 * 3600   # 6 hours
        elif hours <= 720:
            bucket_seconds = 24 * 3600  # 1 day
        else:
            bucket_seconds = 72 * 3600  # 3 days

        conditions = ["q.timestamp >= ?", "q.timestamp <= ?"]
        params: list[Any] = [from_ts, anchor]

        await self._apply_exclusions(conditions, params)

        where = "WHERE " + " AND ".join(conditions)

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT
                CAST((q.timestamp - ?) / ? AS INTEGER) AS bucket,
                COUNT(*)                                AS total,
                SUM(CASE WHEN q.status IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS blocked,
                SUM(CASE WHEN q.status NOT IN ({_BLOCKED_IN}) THEN 1 ELSE 0 END) AS allowed
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            {where}
            GROUP BY bucket
            ORDER BY bucket
        """
        # ruff: enable[S608]

        params = [from_ts, bucket_seconds] + params

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()

        # Build a complete series including empty buckets.
        # +1 to include the current partial bucket (e.g. 25 hourly buckets
        # for a 24h window, so the chart extends to the current hour).
        num_buckets = hours * 3600 // bucket_seconds + 1
        bucket_map = {row["bucket"]: row for row in rows}
        buckets = []
        for i in range(num_buckets):
            row = bucket_map.get(i)
            buckets.append({
                "timestamp": from_ts + i * bucket_seconds,
                "total": row["total"] if row else 0,
                "blocked": row["blocked"] if row else 0,
                "allowed": row["allowed"] if row else 0,
            })

        return {
            "window_hours": hours,
            "bucket_seconds": bucket_seconds,
            "buckets": buckets,
        }

    async def fetch_client_timeline_stats(
        self,
        hours: int = 24,
        end_ts: float | None = None,
    ) -> dict[str, Any]:
        """
        Return per-client query counts bucketed over time.
        Same bucketing as fetch_timeline_stats but grouped by client_ip.
        """
        anchor = end_ts or time.time()
        from_ts = anchor - hours * 3600

        if hours <= 24:
            bucket_seconds = 3600
        elif hours <= 168:
            bucket_seconds = 6 * 3600
        elif hours <= 720:
            bucket_seconds = 24 * 3600
        else:
            bucket_seconds = 72 * 3600

        conditions = ["q.timestamp >= ?", "q.timestamp <= ?"]
        params: list[Any] = [from_ts, anchor]

        await self._apply_exclusions(conditions, params)

        where = "WHERE " + " AND ".join(conditions)

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"""
            SELECT
                q.client_ip,
                cn.name AS client_name,
                CAST((q.timestamp - ?) / ? AS INTEGER) AS bucket,
                COUNT(*) AS count
            FROM queries q
            JOIN domains d ON q.domain = d.domain
            LEFT JOIN client_names cn ON q.client_ip = cn.client_ip
            {where}
            GROUP BY q.client_ip, bucket
            ORDER BY q.client_ip, bucket
        """
        # ruff: enable[S608]

        params = [from_ts, bucket_seconds] + params

        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()

        # Build per-client bucket maps
        num_buckets = hours * 3600 // bucket_seconds + 1
        client_data: dict[str, dict[str, Any]] = {}
        for row in rows:
            ip = row["client_ip"]
            if ip not in client_data:
                client_data[ip] = {
                    "client_ip": ip,
                    "client_name": row["client_name"],
                    "bucket_map": {},
                    "total": 0,
                }
            client_data[ip]["bucket_map"][row["bucket"]] = row["count"]
            client_data[ip]["total"] += row["count"]

        # Build complete bucket series for each client, sorted by total descending
        clients = []
        for info in sorted(client_data.values(), key=lambda c: -c["total"]):
            buckets = []
            for i in range(num_buckets):
                buckets.append({
                    "timestamp": from_ts + i * bucket_seconds,
                    "count": info["bucket_map"].get(i, 0),
                })
            clients.append({
                "client_ip": info["client_ip"],
                "client_name": info["client_name"],
                "total": info["total"],
                "buckets": buckets,
            })

        return {
            "window_hours": hours,
            "bucket_seconds": bucket_seconds,
            "clients": clients,
        }

    async def purge_old_data(self, retention_days: int) -> tuple[int, int]:
        """
        Delete queries older than retention_days and remove orphaned domains.
        Returns (queries_deleted, domains_deleted).
        """
        cutoff = time.time() - retention_days * 86400
        cursor = await self._conn.execute(
            "DELETE FROM queries WHERE timestamp < ?", (cutoff,)
        )
        queries_deleted = cursor.rowcount

        cursor = await self._conn.execute(
            """DELETE FROM domains
               WHERE domain NOT IN (SELECT DISTINCT domain FROM queries)"""
        )
        domains_deleted = cursor.rowcount

        await self._conn.commit()
        return queries_deleted, domains_deleted

    async def reset(self) -> None:
        """Delete all synced queries and domains, and reset the sync cursor to zero."""
        await self._conn.execute("DELETE FROM queries")
        await self._conn.execute("DELETE FROM domains")
        await self._conn.execute(
            "UPDATE sync_state SET last_query_id = 0, last_synced_at = NULL WHERE id = 1"
        )
        await self._conn.commit()
        logger.info("Database reset: all queries and domains deleted, sync cursor zeroed")

    # -------------------------------------------------------------------------
    # User configuration
    # -------------------------------------------------------------------------

    async def get_config(self, key: str) -> str | None:
        """Get a single config value by key."""
        async with self._conn.execute(
            "SELECT value FROM user_config WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

    async def get_all_config(self) -> dict[str, str]:
        """Return all config key-value pairs."""
        async with self._conn.execute("SELECT key, value FROM user_config") as cur:
            rows = await cur.fetchall()
            return {r[0]: r[1] for r in rows}

    async def set_config(self, key: str, value: str) -> None:
        """Set a config value (upsert)."""
        await self._conn.execute(
            "INSERT OR REPLACE INTO user_config (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._conn.commit()

    async def set_config_bulk(self, items: dict[str, str]) -> None:
        """Set multiple config values in a single transaction."""
        await self._conn.executemany(
            "INSERT OR REPLACE INTO user_config (key, value) VALUES (?, ?)",
            list(items.items()),
        )
        await self._conn.commit()

    async def delete_config(self, key: str) -> None:
        """Remove a config key."""
        await self._conn.execute("DELETE FROM user_config WHERE key = ?", (key,))
        await self._conn.commit()

    async def get_available_categories(self) -> list[str]:
        """Return distinct category values from enriched domains."""
        async with self._conn.execute(
            "SELECT DISTINCT category FROM domains WHERE category IS NOT NULL ORDER BY category"
        ) as cur:
            return [r[0] for r in await cur.fetchall()]

    async def get_available_companies(self) -> list[str]:
        """Return distinct company names from enriched domains."""
        async with self._conn.execute(
            "SELECT DISTINCT company_name FROM domains"
            " WHERE company_name IS NOT NULL ORDER BY company_name"
        ) as cur:
            return [r[0] for r in await cur.fetchall()]

    # -------------------------------------------------------------------------
    # Client names
    # -------------------------------------------------------------------------

    async def get_client_names(self) -> dict[str, str]:
        """Return all client IP → name mappings."""
        async with self._conn.execute(
            "SELECT client_ip, name FROM client_names ORDER BY name"
        ) as cur:
            return {r[0]: r[1] for r in await cur.fetchall()}

    async def get_clients(self) -> list[dict[str, Any]]:
        """Return all distinct client IPs with query counts and any assigned names."""
        async with self._conn.execute("""
            SELECT q.client_ip, cn.name AS client_name, COUNT(*) AS query_count
            FROM queries q
            LEFT JOIN client_names cn ON q.client_ip = cn.client_ip
            GROUP BY q.client_ip
            ORDER BY query_count DESC
        """) as cur:
            return [
                {"client_ip": r["client_ip"], "client_name": r["client_name"],
                 "query_count": r["query_count"]}
                for r in await cur.fetchall()
            ]

    async def set_client_name(self, client_ip: str, name: str) -> None:
        """Set or update a client name for an IP."""
        await self._conn.execute(
            "INSERT OR REPLACE INTO client_names (client_ip, name) VALUES (?, ?)",
            (client_ip, name),
        )
        await self._conn.commit()

    async def delete_client_name(self, client_ip: str) -> None:
        """Remove a client name mapping."""
        await self._conn.execute("DELETE FROM client_names WHERE client_ip = ?", (client_ip,))
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # Sync status
    # -------------------------------------------------------------------------

    async def get_sync_status(self) -> dict[str, Any]:
        async with self._conn.execute(
            "SELECT last_query_id, last_synced_at FROM sync_state WHERE id = 1"
        ) as cur:
            row = await cur.fetchone()

        # Count queries with exclusions applied
        conditions: list[str] = []
        params: list[Any] = []
        await self._apply_exclusions(conditions, params)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # ruff: disable[S608]
        # Dynamic SQL uses f-strings for structure only;
        # all user input goes through parameterised queries.
        sql = f"SELECT COUNT(*) FROM queries q JOIN domains d ON q.domain = d.domain {where}"
        # ruff: enable[S608]

        async with self._conn.execute(sql, params) as cur:
            count_row = await cur.fetchone()

        return {
            "last_query_id": row[0] if row else 0,
            "last_synced_at": row[1] if row else None,
            "stored_queries": count_row[0] if count_row else 0,
        }

    async def get_data_range(self) -> dict[str, Any]:
        """Return the timestamp of the oldest and newest stored query."""
        async with self._conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM queries"
        ) as cur:
            row = await cur.fetchone()
        return {
            "oldest_ts": row[0] if row else None,
            "newest_ts": row[1] if row else None,
        }
