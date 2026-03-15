"""
Background sync service: periodically fetches new queries from Pi-hole,
filters to only relevant ones, and stores them in the local database
with enrichment data from TrackerDB and Disconnect.me.

Pi-hole query history is append-only — we only ever need to fetch queries
with an ID greater than the highest one we've already stored.
"""

import asyncio
import logging

from app.config import settings
from app.models.pihole import RawQuery
from app.models.tracker import TrackerInfo
from app.services.database import LocalDatabase
from app.services.disconnect.loader import DisconnectDB
from app.services.pihole.api_client import BLOCKED_STATUSES, PiholeApiClient
from app.services.trackerdb.enricher import TrackerEnricher

logger = logging.getLogger(__name__)


def _enrich_domain(
    domain: str,
    trackerdb_result: TrackerInfo | None,
    disconnect_db: DisconnectDB,
) -> tuple[TrackerInfo | None, str | None]:
    """
    Return (TrackerInfo, source) using TrackerDB first, then Disconnect.me.
    source is "trackerdb" or "disconnect", or None if neither matched.
    """
    if trackerdb_result is not None:
        return trackerdb_result, "trackerdb"
    result = disconnect_db.lookup(domain)
    if result is not None:
        return result, "disconnect"
    return None, None


async def _sync_once(
    pihole: PiholeApiClient,
    enricher: TrackerEnricher,
    disconnect_db: DisconnectDB,
    db: LocalDatabase,
) -> int:
    """
    Run one sync cycle. Fetches all queries newer than our last stored ID,
    filters to relevant ones (blocked + known-tracker allowed), enriches,
    and persists. Returns the number of new queries stored.
    """
    last_id = await db.get_last_query_id()

    # Collect all new queries by paging backwards through Pi-hole until we
    # reach a query ID we've already seen. Cap at 500 pages (50k queries)
    # to avoid runaway fetching on a Pi-hole with a very large history.
    _MAX_PAGES = 500
    new_queries: list[RawQuery] = []
    cursor: int | None = None

    for _ in range(_MAX_PAGES):
        batch, _ = await pihole.get_queries(limit=100, cursor=cursor)
        if not batch:
            break

        # Queries come newest-first; separate new from already-seen
        new_in_batch = [q for q in batch if q.id > last_id]
        new_queries.extend(new_in_batch)

        # If the batch contains any already-seen ID, we've caught up
        if len(new_in_batch) < len(batch):
            break

        # Advance cursor to fetch the next (older) page
        cursor = batch[-1].id
    else:
        logger.warning("Sync hit page cap (%d pages) — some older queries may be skipped", _MAX_PAGES)

    if not new_queries:
        return 0

    # Filter: keep blocked queries always; allowed queries only if a known tracker
    to_store = []
    for q in new_queries:
        if q.status in BLOCKED_STATUSES:
            to_store.append(q)
        else:
            tb_result = await enricher.enrich(q.domain)
            _, source = _enrich_domain(q.domain, tb_result, disconnect_db)
            if source is not None:
                to_store.append(q)

    if not to_store:
        await db.update_sync_state(max(q.id for q in new_queries))
        return 0

    # Ensure a domain row exists for each unique domain
    unique_domains = list({q.domain for q in to_store})
    await db.upsert_domains(unique_domains)

    # Enrich all domains concurrently via TrackerDB, then fall back to Disconnect.me
    trackerdb_results = await asyncio.gather(*[enricher.enrich(q.domain) for q in to_store])

    enrichment_updates = []
    for q, tb_result in zip(to_store, trackerdb_results):
        result, source = _enrich_domain(q.domain, tb_result, disconnect_db)
        if result is not None:
            enrichment_updates.append({
                "domain": q.domain,
                "tracker_name": result.tracker_name,
                "category": result.category,
                "company_name": result.company_name,
                "company_country": result.company_country,
                "source": source,
            })

    if enrichment_updates:
        await db.batch_update_domain_enrichment(enrichment_updates)

    # Insert query rows
    query_rows = [
        {
            "id": q.id,
            "timestamp": q.timestamp,
            "domain": q.domain,
            "client_ip": q.client,
            "client_name": q.client_name,
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

    # Update the sync cursor to the highest ID we processed from Pi-hole
    # (not just to_store — we don't want to re-examine skipped allowed queries)
    await db.update_sync_state(max(q.id for q in new_queries))

    logger.info(
        "Sync: %d new Pi-hole queries → %d stored (%d skipped as non-tracker allowed)",
        len(new_queries),
        len(to_store),
        len(new_queries) - len(to_store),
    )

    # Re-enrich any previously stored domains that had no enrichment yet.
    # This catches domains stored before Disconnect.me was available.
    await _reenrich_missing(enricher, disconnect_db, db)

    return len(to_store)


async def _reenrich_missing(
    enricher: TrackerEnricher,
    disconnect_db: DisconnectDB,
    db: LocalDatabase,
) -> None:
    """Enrich domains that are stored but still have no enrichment data."""
    unenriched = await db.get_unenriched_domains()
    if not unenriched:
        return

    logger.debug("Re-enriching %d unenriched domains", len(unenriched))
    trackerdb_results = await asyncio.gather(*[enricher.enrich(d) for d in unenriched])

    updates = []
    for domain, tb_result in zip(unenriched, trackerdb_results):
        result, source = _enrich_domain(domain, tb_result, disconnect_db)
        if result is not None:
            updates.append({
                "domain": domain,
                "tracker_name": result.tracker_name,
                "category": result.category,
                "company_name": result.company_name,
                "company_country": result.company_country,
                "source": source,
            })

    if updates:
        await db.batch_update_domain_enrichment(updates)
        logger.info("Re-enriched %d domains (%d still unenriched)", len(updates), len(unenriched) - len(updates))


async def run_sync_loop(
    pihole: PiholeApiClient,
    enricher: TrackerEnricher,
    disconnect_db: DisconnectDB,
    db: LocalDatabase,
) -> None:
    """
    Long-running background task. Syncs once immediately on startup,
    then repeats every sync_interval_seconds. Also refreshes Disconnect.me
    data when it becomes stale.
    """
    logger.info("Sync service started (interval: %ds)", settings.sync_interval_seconds)

    while True:
        # Refresh Disconnect.me if stale
        if disconnect_db.is_stale:
            await disconnect_db.load()

        try:
            stored = await _sync_once(pihole, enricher, disconnect_db, db)
            if stored:
                logger.debug("Sync cycle complete: %d queries stored", stored)
        except Exception:
            logger.exception("Sync cycle failed — will retry next interval")

        await asyncio.sleep(settings.sync_interval_seconds)
