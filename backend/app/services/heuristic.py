"""
eTLD+1 heuristic enrichment.

Last-resort company name extraction for domains that neither TrackerDB nor
Disconnect.me recognise. Extracts the second-to-last domain label as a
human-readable company name (e.g. "telemetry.nvidia.com" → "Nvidia").

No category can be inferred — only company_name is set.
"""


def extract_company_name(domain: str) -> str | None:
    """
    Extract a best-guess company name from a domain.

    Returns None if the domain is too short to produce a meaningful name.
    Known limitation: multi-part TLDs (e.g. co.uk) will produce the wrong
    label — this is acceptable for a last-resort heuristic.
    """
    parts = domain.rstrip(".").split(".")
    if len(parts) < 2:
        return None
    name = parts[-2]
    if len(name) < 2:
        return None
    return name.capitalize()
