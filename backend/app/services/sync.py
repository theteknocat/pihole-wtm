"""
Background sync service: periodically fetches new queries from Pi-hole,
filters to only relevant ones, and stores them in the local database
with enrichment data from configured tracker sources.

Pi-hole query history is append-only — we only ever need to fetch queries
with an ID greater than the highest one we've already stored.
"""

import asyncio
import logging
import time
from typing import Any

from app.models.pihole import RawQuery
from app.models.tracker import TrackerInfo
from app.services.database import LocalDatabase
from app.services.heuristic import extract_category, extract_company_name
from app.services.pihole.api_client import BLOCKED_STATUSES, PiholeApiClient
from app.services.rdap import lookup_company as rdap_lookup
from app.services.sources import TrackerSource

logger = logging.getLogger(__name__)


def _enrichment_dict(
    domain: str,
    source: str | None,
    info: TrackerInfo | None = None,
    *,
    tracker_name: str | None = None,
    category: str | None = None,
    company_name: str | None = None,
    company_country: str | None = None,
) -> dict[str, Any]:
    """Build an enrichment update dict. Uses TrackerInfo fields if provided, otherwise kwargs."""
    return {
        "domain": domain,
        "tracker_name": info.tracker_name if info else tracker_name,
        "category": info.category if info else category,
        "company_name": info.company_name if info else company_name,
        "company_country": info.company_country if info else company_country,
        "source": source,
    }


async def _enrich_from_sources(
    domain: str,
    sources: list[TrackerSource],
) -> tuple[TrackerInfo | None, str | None]:
    """
    Try each source in priority order, return the first match.
    Returns (TrackerInfo, source_name) or (None, None).
    """
    for source in sources:
        result = await source.enrich(domain)
        if result is not None:
            return result, source.source_name
    return None, None


async def _gate_from_sources(
    domain: str,
    sources: list[TrackerSource],
) -> tuple[TrackerInfo | None, str | None]:
    """
    Exact-match gating: try each gating-enabled source in priority order.
    Returns (TrackerInfo, source_name) or (None, None).
    """
    for source in sources:
        if not source.gates:
            continue
        result = await source.lookup_exact(domain)
        if result is not None:
            return result, source.source_name
    return None, None


async def _process_batch(
    raw_queries: list[RawQuery],
    sources: list[TrackerSource],
    db: LocalDatabase,
    exact_cache: dict[str, tuple[TrackerInfo | None, str | None]],
) -> int:
    """
    Filter, enrich, and persist a batch of raw Pi-hole queries.

    Returns the number of queries stored. The exact_cache is shared across
    batches within a sync cycle so repeated domains aren't re-looked-up.
    """
    # Filter: always store blocked queries; store allowed queries only when the
    # domain is an exact match in any configured source. No subdomain fallback
    # here — fallback would cause legitimate subdomains (mail.google.com,
    # calendar.google.com) to match their parent company's tracker entry and be
    # incorrectly stored as ad-network traffic.
    to_store: list[RawQuery] = []
    allowed_enrichment: dict[int, tuple[TrackerInfo, str | None]] = {}

    for q in raw_queries:
        if q.status in BLOCKED_STATUSES:
            to_store.append(q)
        else:
            if q.domain not in exact_cache:
                exact_cache[q.domain] = await _gate_from_sources(q.domain, sources)
            result, source_name = exact_cache[q.domain]
            if result is not None:
                to_store.append(q)
                allowed_enrichment[q.id] = (result, source_name)

    if not to_store:
        return 0

    # Ensure a domain row exists for each unique domain
    unique_domains = list({q.domain for q in to_store})
    await db.upsert_domains(unique_domains)

    # Enrich blocked queries with full fallback lookup so display metadata
    # (category, company) is populated even for tracker subdomains not
    # explicitly listed. Allowed queries reuse the exact gating result directly.
    blocked = [q for q in to_store if q.id not in allowed_enrichment]
    blocked_results = await asyncio.gather(
        *[_enrich_from_sources(q.domain, sources) for q in blocked]
    )

    # Deduplicate by domain — a domain may appear in both blocked and allowed
    # queries within the same batch. Use a dict so last write wins.
    enrichment_by_domain: dict[str, dict[str, Any]] = {}
    for q, (result, source_name) in zip(blocked, blocked_results, strict=True):
        if result is not None:
            enrichment_by_domain[q.domain] = _enrichment_dict(q.domain, source_name, result)

    for q in to_store:
        if q.id in allowed_enrichment:
            result, source_name = allowed_enrichment[q.id]
            enrichment_by_domain[q.domain] = _enrichment_dict(q.domain, source_name, result)

    enrichment_updates = list(enrichment_by_domain.values())
    if enrichment_updates:
        await db.batch_update_domain_enrichment(enrichment_updates)

    # Insert query rows
    query_rows = [
        {
            "id": q.id,
            "timestamp": q.timestamp,
            "domain": q.domain,
            "client_ip": q.client,
            "status": q.status,
            "query_type": q.query_type,
            "reply_type": q.reply_type,
            "reply_time": q.reply_time,
            "upstream": q.upstream,
            "list_id": q.list_id,
        }
        for q in to_store
    ]
    await db.insert_queries(query_rows)

    return len(to_store)


_BATCH_SIZE = 5000  # queries per processing batch during sync


async def _sync_once(
    pihole: PiholeApiClient,
    sources: list[TrackerSource],
    db: LocalDatabase,
) -> int:
    """
    Run one sync cycle. Fetches queries newer than our last stored ID in
    pages from Pi-hole, processing them in batches so data appears on the
    dashboard progressively rather than all at once.

    Stops fetching once queries fall outside the configured data retention
    period — there's no point pulling in data that would be immediately purged.
    """
    last_id = await db.get_last_query_id()

    # Don't fetch queries older than the retention window
    retention_val = await db.get_config("data_retention_days")
    retention_days = int(retention_val) if retention_val is not None else 7
    cutoff_ts = time.time() - (retention_days * 86400)

    # Shared across batches so repeated domains aren't re-looked-up
    exact_cache: dict[str, tuple[TrackerInfo | None, str | None]] = {}

    total_fetched = 0
    total_stored = 0
    cursor: int | None = None
    pending: list[RawQuery] = []
    highest_id = last_id
    done = False

    while not done:
        batch, _ = await pihole.get_queries(limit=100, cursor=cursor)
        if not batch:
            break

        # Queries come newest-first; separate new from already-seen
        new_in_batch = [q for q in batch if q.id > last_id]

        # Drop queries older than the retention cutoff and stop paging
        within_retention = [q for q in new_in_batch if q.timestamp >= cutoff_ts]
        if len(within_retention) < len(new_in_batch):
            done = True
            new_in_batch = within_retention

        pending.extend(new_in_batch)
        total_fetched += len(new_in_batch)

        # Track the highest ID across all fetched queries
        if new_in_batch:
            highest_id = max(highest_id, max(q.id for q in new_in_batch))

        # If the batch contains any already-seen ID, we've caught up
        if not done and len(new_in_batch) < len(batch):
            done = True

        # Process a batch once we've accumulated enough (or we're done fetching)
        if len(pending) >= _BATCH_SIZE or done:
            if pending:
                stored = await _process_batch(pending, sources, db, exact_cache)
                total_stored += stored
                await db.update_sync_state(highest_id)
                logger.info(
                    "Sync: processed %d queries (%d stored, %d total so far)",
                    len(pending), stored, total_stored,
                )
                pending = []

        if not done:
            # Advance cursor to fetch the next (older) page
            cursor = batch[-1].id

    if total_fetched == 0:
        return 0

    # Update sync cursor to the highest ID even if nothing was stored
    # (so we don't re-examine skipped allowed queries)
    await db.update_sync_state(highest_id)

    if total_stored:
        logger.info(
            "Sync complete: %d Pi-hole queries → %d stored (%d skipped as non-tracker allowed)",
            total_fetched, total_stored, total_fetched - total_stored,
        )

    # Re-enrich any previously stored domains that had no enrichment yet.
    # This catches domains stored before a new source was available.
    await _reenrich_missing(sources, db)

    return total_stored


async def _reenrich_missing(
    sources: list[TrackerSource],
    db: LocalDatabase,
) -> None:
    """Enrich domains that are stored but still have no enrichment data."""
    unenriched = await db.get_unenriched_domains()
    if not unenriched:
        return

    logger.debug("Re-enriching %d unenriched domains", len(unenriched))
    results = await asyncio.gather(
        *[_enrich_from_sources(d, sources) for d in unenriched]
    )

    updates = []
    for domain, (result, source_name) in zip(unenriched, results, strict=True):
        if result is not None:
            updates.append(_enrichment_dict(domain, source_name, result))
        else:
            # eTLD+1 heuristic — company name from registered domain, category from keywords
            company_name = extract_company_name(domain)
            category = extract_category(domain)
            if company_name or category:
                updates.append(_enrichment_dict(
                    domain, "heuristic", category=category, company_name=company_name,
                ))

    if updates:
        await db.batch_update_domain_enrichment(updates)
        still_unenriched = len(unenriched) - len(updates)
        logger.info("Re-enriched %d domains (%d still unenriched)", len(updates), still_unenriched)


async def _rdap_reenrich(db: LocalDatabase) -> None:
    """
    Background upgrade pass: replace heuristic company names with proper
    registered organization names from RDAP, one domain at a time with a
    short delay to stay within rate limits.

    Preserves existing tracker_name and category from the heuristic pass,
    since RDAP only provides a company name.
    """
    rows = await db.get_heuristic_domains()
    if not rows:
        return

    logger.info("RDAP: upgrading %d heuristic-enriched domains", len(rows))
    upgraded = 0

    for row in rows:
        company = await rdap_lookup(row["domain"])
        if company:
            await db.batch_update_domain_enrichment([_enrichment_dict(
                row["domain"], "rdap",
                tracker_name=row["tracker_name"], category=row["category"], company_name=company,
            )])
            upgraded += 1
        else:
            # Mark as failed so we don't retry on every cycle
            await db.batch_update_domain_enrichment([_enrichment_dict(
                row["domain"], "rdap_failed",
                tracker_name=row["tracker_name"],
                category=row["category"],
                company_name=row["company_name"],
            )])
        await asyncio.sleep(0.5)  # be polite to RDAP services

    logger.info("RDAP: upgraded %d / %d domains", upgraded, len(rows))


async def run_sync_loop(
    pihole: PiholeApiClient,
    sources: list[TrackerSource],
    db: LocalDatabase,
    wake_event: asyncio.Event | None = None,
) -> None:
    """
    Long-running background task. Syncs once immediately on startup,
    then repeats on a configurable interval. Also refreshes stale sources
    and runs RDAP upgrade passes periodically.

    Settings are read from the database each cycle so changes take effect
    without a restart.

    If wake_event is provided, setting it will skip the sleep and trigger
    an immediate sync cycle (e.g. after a data reset).
    """
    # Defaults used when no database setting exists
    _DEFAULTS = {
        "sync_interval_seconds": 60,
        "data_retention_days": 7,
    }

    async def _get_setting(key: str) -> int:
        val = await db.get_config(key)
        return int(val) if val is not None else _DEFAULTS[key]

    logger.info("Sync service started")
    _rdap_cycle = 0
    _RDAP_EVERY_N_CYCLES = 10  # run RDAP pass every 10 sync cycles (~10 minutes)

    # Source setting keys mapped to source_name
    _SOURCE_INTERVAL_KEYS = {
        "trackerdb": "trackerdb_update_interval_hours",
        "disconnect": "disconnect_update_interval_hours",
    }

    while True:
        # Update source intervals from database settings, then refresh if stale
        for source in sources:
            interval_key = _SOURCE_INTERVAL_KEYS.get(source.source_name)
            if interval_key:
                val = await db.get_config(interval_key)
                if val is not None:
                    source.UPDATE_INTERVAL_HOURS = int(val)
            await source.refresh_if_stale()

        try:
            stored = await _sync_once(pihole, sources, db)
            if stored:
                logger.debug("Sync cycle complete: %d queries stored", stored)
        except Exception:
            logger.exception("Sync cycle failed — will retry next interval")

        # Purge data older than the configured retention period
        try:
            retention = await _get_setting("data_retention_days")
            q_del, d_del = await db.purge_old_data(retention)
            if q_del or d_del:
                logger.info("Retention: purged %d queries, %d orphaned domains", q_del, d_del)
        except Exception:
            logger.exception("Data retention purge failed — will retry next cycle")

        # Periodically upgrade heuristic domains with RDAP data
        _rdap_cycle += 1
        if _rdap_cycle >= _RDAP_EVERY_N_CYCLES:
            _rdap_cycle = 0
            try:
                await _rdap_reenrich(db)
            except Exception:
                logger.exception("RDAP re-enrichment failed — will retry next cycle")

        interval = await _get_setting("sync_interval_seconds")
        if wake_event:
            # Wait for the interval OR until the event is signalled, whichever
            # comes first. Clear the event so the next cycle sleeps normally.
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=interval)
            except TimeoutError:
                pass
            wake_event.clear()
        else:
            await asyncio.sleep(interval)
