"""
RDAP (Registration Data Access Protocol) company name enrichment.

Used as a background upgrade pass for domains that were enriched only via
the eTLD+1 heuristic. Queries the public RDAP proxy at rdap.org to find
the registered organization name for a domain.

Lookups are performed against the registered domain (eTLD+1) since RDAP
does not accept subdomain queries. Results are cached in-memory so multiple
subdomains of the same registered domain only trigger one RDAP request.
"""

import logging

import httpx
from cachetools import LRUCache

logger = logging.getLogger(__name__)

# Cache: registered_domain → company name (or None if not found / privacy-protected)
_cache: LRUCache = LRUCache(maxsize=5000)


def _registered_domain(domain: str) -> str:
    """
    Extract the registered domain (eTLD+1) for RDAP lookup.
    Simple heuristic — takes the last two labels.
    Known limitation: multi-part TLDs (co.uk, com.au) produce wrong results.
    """
    parts = domain.rstrip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain


def _flatten_entities(entities: list[dict]) -> list[dict]:
    """Recursively collect all entities, including nested ones."""
    result: list[dict] = []
    for entity in entities:
        result.append(entity)
        nested = entity.get("entities")
        if nested:
            result.extend(_flatten_entities(nested))
    return result


def _extract_org(data: dict) -> str | None:
    """
    Parse a registrant organization name from an RDAP response.
    Tries the registrant entity first, then any other entity with vCard data.
    Flattens nested entities so registrants inside registrar entities are found.
    """
    all_entities = _flatten_entities(data.get("entities", []))

    # Prefer registrant role
    ordered = sorted(all_entities, key=lambda e: ("registrant" not in e.get("roles", [])))

    for entity in ordered:
        vcard = entity.get("vcardArray")
        if not vcard or len(vcard) < 2:
            continue
        for field in vcard[1]:
            if field[0] in ("fn", "org") and len(field) >= 4:
                value = field[3]
                if isinstance(value, str) and len(value) >= 2:
                    return value

    return None


async def lookup_company(domain: str) -> str | None:
    """
    Return a registered company name for the given domain, or None if
    unavailable (privacy protection, RDAP error, rate limit, etc.).

    Results are cached in-memory — repeated calls for subdomains of the
    same registered domain are free after the first lookup.
    """
    reg = _registered_domain(domain)

    if reg in _cache:
        return _cache[reg]

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(
                f"https://rdap.org/domain/{reg}",
                headers={"Accept": "application/rdap+json"},
            )
        if response.status_code != 200:
            _cache[reg] = None
            return None

        data = response.json()
    except Exception as e:
        logger.debug("RDAP lookup failed for %s: %s", reg, e)
        _cache[reg] = None
        return None

    company = _extract_org(data)
    _cache[reg] = company
    return company
