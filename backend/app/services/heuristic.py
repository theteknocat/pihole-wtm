"""
Heuristic enrichment for domains unrecognised by TrackerDB and Disconnect.me.

Provides two signals:
- Company name: extracted from the registered domain label (eTLD+1 minus TLD)
- Category: inferred from subdomain labels that are well-known tracking keywords

Neither signal is as reliable as a proper database, but both are meaningfully
better than showing nothing.
"""

# Subdomain labels that strongly indicate a tracking/telemetry purpose.
# Keys are lowercase label strings; values are the category to assign.
_SUBDOMAIN_CATEGORIES: dict[str, str] = {
    # Telemetry / crash reporting
    "telemetry":   "telemetry",
    "metrics":     "telemetry",
    "metric":      "telemetry",
    "crash":       "telemetry",
    "crashes":     "telemetry",
    "diagnostic":  "telemetry",
    "diagnostics": "telemetry",
    "perf":        "telemetry",
    "performance": "telemetry",
    "logs":        "telemetry",
    "log":         "telemetry",
    "usage":       "telemetry",
    "report":      "telemetry",
    "reports":     "telemetry",
    "ping":        "telemetry",
    # Analytics
    "analytics":   "analytics",
    "tracking":    "analytics",
    "tracker":     "analytics",
    "stats":       "analytics",
    "stat":        "analytics",
    "collect":     "analytics",
    "collector":   "analytics",
    "beacon":      "analytics",
    "events":      "analytics",
    "event":       "analytics",
    "data":        "analytics",
    "insights":    "analytics",
    "measurement": "analytics",
    # Advertising
    "ads":         "advertising",
    "ad":          "advertising",
    "adserver":    "advertising",
    "pixel":       "advertising",
    "pixels":      "advertising",
    "rtb":         "advertising",
    "targeting":   "advertising",
}


def extract_company_name(domain: str) -> str | None:
    """
    Extract a best-guess company name from the registered domain label.

    e.g. "telemetry.nvidia.com" → "Nvidia"

    Returns None if the domain is too short to produce a meaningful name.
    Known limitation: multi-part TLDs (co.uk, com.au) produce the wrong label.
    """
    parts = domain.rstrip(".").split(".")
    if len(parts) < 2:
        return None
    name = parts[-2]
    if len(name) < 2:
        return None
    return name.capitalize()


def extract_category(domain: str) -> str | None:
    """
    Infer a tracker category from subdomain labels.

    Checks each subdomain label (and hyphen/underscore-separated parts of it)
    against a known mapping of tracking-related keywords.

    e.g. "telemetry.nvidia.com"      → "telemetry"
         "crash-reports.example.com" → "telemetry"
         "pixel.ads.example.com"     → "advertising"

    Returns None if no subdomain label matches a known tracking keyword.
    Only subdomain labels are checked — the registered domain and TLD are skipped.
    """
    parts = domain.rstrip(".").split(".")
    # Subdomains are everything except the last two labels (SLD + TLD)
    subdomains = parts[:-2]

    for label in subdomains:
        # Check the full label
        if label in _SUBDOMAIN_CATEGORIES:
            return _SUBDOMAIN_CATEGORIES[label]
        # Also check parts split by hyphens/underscores
        # e.g. "crash-reports" → ["crash", "reports"]
        for part in label.replace("-", " ").replace("_", " ").split():
            if part in _SUBDOMAIN_CATEGORIES:
                return _SUBDOMAIN_CATEGORIES[part]

    return None
