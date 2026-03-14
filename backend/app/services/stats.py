import asyncio
import logging
import time
from collections import defaultdict
from typing import Any

from app.services.pihole.api_client import PiholeApiClient
from app.services.trackerdb.enricher import TrackerEnricher

logger = logging.getLogger(__name__)

_PAGE_SIZE = 1000
_MAX_PAGES = 50  # safety cap — limits queries fetched to 50k per call


async def get_tracker_stats(
    pihole: PiholeApiClient,
    enricher: TrackerEnricher,
    hours: int = 24,
) -> dict[str, Any]:
    """
    Fetch all Pi-hole queries within the given time window, enrich with
    TrackerDB data, and return aggregated stats grouped by category and company.
    """
    until_ts = time.time()
    from_ts = until_ts - hours * 3600

    # Paginate through Pi-hole query log, stopping when we leave the time window.
    # Pi-hole's returned cursor points to the newest query in the batch (upper bound),
    # so we compute the next cursor ourselves using the oldest query ID in each batch.
    all_queries = []
    cursor: int | None = None
    truncated = False
    for _ in range(_MAX_PAGES):
        batch, _ = await pihole.get_queries(limit=_PAGE_SIZE, cursor=cursor, from_ts=int(from_ts))
        if not batch:
            break

        # Queries are returned newest-first; stop when we pass the window boundary
        if batch[-1].timestamp < from_ts:
            all_queries.extend(q for q in batch if q.timestamp >= from_ts)
            break

        all_queries.extend(batch)
        cursor = batch[-1].id  # oldest ID in batch → next page goes further back
    else:
        # Loop exhausted _MAX_PAGES without hitting the time boundary
        truncated = True
        logger.warning(
            "Stats query hit page cap (%d queries) — results for %dh window may be incomplete",
            len(all_queries),
            hours,
        )

    logger.debug("Fetched %d queries for %dh window (truncated=%s)", len(all_queries), hours, truncated)

    total = len(all_queries)

    # Enrich all domains concurrently
    tracker_results = await asyncio.gather(*[enricher.enrich(q.domain) for q in all_queries])

    # Aggregate: category → company → domain → count
    stats: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    tracker_total = 0

    for q, t in zip(all_queries, tracker_results):
        if t is None:
            continue
        tracker_total += 1
        category = t.category or "Unknown"
        company = t.company_name or "Unknown"
        stats[category][company][q.domain] += 1

    # Build response, sorted by query_count descending at every level
    def category_total(companies: dict[str, dict[str, int]]) -> int:
        return sum(sum(domains.values()) for domains in companies.values())

    by_category = []
    for category, companies in sorted(stats.items(), key=lambda x: -category_total(x[1])):
        company_list = []
        for company, domains in sorted(companies.items(), key=lambda x: -sum(x[1].values())):
            top_domains = sorted(
                [{"domain": d, "query_count": c} for d, c in domains.items()],
                key=lambda x: -x["query_count"],
            )[:10]
            company_list.append(
                {
                    "company_name": company,
                    "query_count": sum(domains.values()),
                    "top_domains": top_domains,
                }
            )
        by_category.append(
            {
                "category": category,
                "query_count": category_total(companies),
                "companies": company_list,
            }
        )

    return {
        "window_hours": hours,
        "total_queries": total,
        "tracker_queries": tracker_total,
        "tracker_percent": round(tracker_total / total * 100, 1) if total else 0.0,
        "truncated": truncated,
        "by_category": by_category,
    }
