"""
Background sync service: periodically fetches new queries from Pi-hole,
filters to only relevant ones, and stores them in the local database
with enrichment data from configured tracker sources.

Pi-hole query history is append-only — we only ever need to fetch queries
with an ID greater than the highest one we've already stored.
"""

import asyncio
import logging

from app.config import settings
from app.models.pihole import RawQuery
from app.models.tracker import TrackerInfo
from app.services.database import LocalDatabase
from app.services.heuristic import extract_category, extract_company_name
from app.services.pihole.api_client import BLOCKED_STATUSES, PiholeApiClient
from app.services.rdap import lookup_company as rdap_lookup
from app.services.sources import TrackerSource

logger = logging.getLogger(__name__)


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


async def _sync_once(
    pihole: PiholeApiClient,
    sources: list[TrackerSource],
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

    # Filter: always store blocked queries; store allowed queries only when the
    # domain is an exact match in any configured source. No subdomain fallback
    # here — fallback would cause legitimate subdomains (mail.google.com,
    # calendar.google.com) to match their parent company's tracker entry and be
    # incorrectly stored as ad-network traffic.
    #
    # A per-cycle cache avoids repeated lookups for the same domain within one
    # batch. The gating result is reused directly for allowed-query enrichment,
    # eliminating a redundant second lookup.
    to_store: list[RawQuery] = []
    allowed_enrichment: dict[int, tuple[TrackerInfo, str]] = {}  # query id → (result, source)
    _exact_cache: dict[str, tuple[TrackerInfo | None, str | None]] = {}

    for q in new_queries:
        if q.status in BLOCKED_STATUSES:
            to_store.append(q)
        else:
            if q.domain not in _exact_cache:
                _exact_cache[q.domain] = await _gate_from_sources(q.domain, sources)
            result, source_name = _exact_cache[q.domain]
            if result is not None:
                to_store.append(q)
                allowed_enrichment[q.id] = (result, source_name)

    if not to_store:
        await db.update_sync_state(max(q.id for q in new_queries))
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
    enrichment_by_domain: dict[str, dict] = {}
    for q, (result, source_name) in zip(blocked, blocked_results):
        if result is not None:
            enrichment_by_domain[q.domain] = {
                "domain": q.domain,
                "tracker_name": result.tracker_name,
                "category": result.category,
                "company_name": result.company_name,
                "company_country": result.company_country,
                "source": source_name,
            }

    for q in to_store:
        if q.id in allowed_enrichment:
            result, source_name = allowed_enrichment[q.id]
            enrichment_by_domain[q.domain] = {
                "domain": q.domain,
                "tracker_name": result.tracker_name,
                "category": result.category,
                "company_name": result.company_name,
                "company_country": result.company_country,
                "source": source_name,
            }

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
    # This catches domains stored before a new source was available.
    await _reenrich_missing(sources, db)

    return len(to_store)


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
    for domain, (result, source_name) in zip(unenriched, results):
        if result is not None:
            updates.append({
                "domain": domain,
                "tracker_name": result.tracker_name,
                "category": result.category,
                "company_name": result.company_name,
                "company_country": result.company_country,
                "source": source_name,
            })
        else:
            # eTLD+1 heuristic — company name from registered domain, category from subdomain keywords
            company_name = extract_company_name(domain)
            category = extract_category(domain)
            if company_name or category:
                updates.append({
                    "domain": domain,
                    "tracker_name": None,
                    "category": category,
                    "company_name": company_name,
                    "company_country": None,
                    "source": "heuristic",
                })

    if updates:
        await db.batch_update_domain_enrichment(updates)
        logger.info("Re-enriched %d domains (%d still unenriched)", len(updates), len(unenriched) - len(updates))


async def _rdap_reenrich(db: LocalDatabase) -> None:
    """
    Background upgrade pass: replace heuristic company names with proper
    registered organization names from RDAP, one domain at a time with a
    short delay to stay within rate limits.
    """
    domains = await db.get_heuristic_domains()
    if not domains:
        return

    logger.info("RDAP: upgrading %d heuristic-enriched domains", len(domains))
    upgraded = 0

    for domain in domains:
        company = await rdap_lookup(domain)
        if company:
            await db.batch_update_domain_enrichment([{
                "domain": domain,
                "tracker_name": None,
                "category": None,
                "company_name": company,
                "company_country": None,
                "source": "rdap",
            }])
            upgraded += 1
        await asyncio.sleep(0.5)  # be polite to RDAP services

    logger.info("RDAP: upgraded %d / %d domains", upgraded, len(domains))


async def run_sync_loop(
    pihole: PiholeApiClient,
    sources: list[TrackerSource],
    db: LocalDatabase,
) -> None:
    """
    Long-running background task. Syncs once immediately on startup,
    then repeats every sync_interval_seconds. Also refreshes stale sources
    and runs RDAP upgrade passes periodically.
    """
    logger.info("Sync service started (interval: %ds)", settings.sync_interval_seconds)
    _rdap_cycle = 0
    _RDAP_EVERY_N_CYCLES = 10  # run RDAP pass every 10 sync cycles (~10 minutes)

    while True:
        # Refresh any sources whose data has become stale
        for source in sources:
            await source.refresh_if_stale()

        try:
            stored = await _sync_once(pihole, sources, db)
            if stored:
                logger.debug("Sync cycle complete: %d queries stored", stored)
        except Exception:
            logger.exception("Sync cycle failed — will retry next interval")

        # Periodically upgrade heuristic domains with RDAP data
        _rdap_cycle += 1
        if _rdap_cycle >= _RDAP_EVERY_N_CYCLES:
            _rdap_cycle = 0
            try:
                await _rdap_reenrich(db)
            except Exception:
                logger.exception("RDAP re-enrichment failed — will retry next cycle")

        await asyncio.sleep(settings.sync_interval_seconds)
