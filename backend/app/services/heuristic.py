"""
Heuristic enrichment for domains unrecognised by TrackerDB and Disconnect.me.

Provides two signals:
- Company name: extracted from the registered domain label (eTLD+1 minus TLD)
- Category: inferred from keywords found anywhere in the domain name

Neither signal is as reliable as a proper database, but both are meaningfully
better than showing nothing.
"""

# Keywords that are safe to substring-match anywhere in the domain (6+ chars,
# specific enough to avoid false positives).
_SUBSTRING_KEYWORDS: list[tuple[str, str]] = [
    # Telemetry / crash reporting
    ("telemetry",   "telemetry"),
    ("diagnostic",  "telemetry"),
    ("diagnostics", "telemetry"),
    ("metrics",     "telemetry"),
    ("performance", "telemetry"),
    ("crashes",     "telemetry"),
    # Analytics
    ("analytics",   "analytics"),
    ("tracking",    "analytics"),
    ("tracker",     "analytics"),
    ("collect",     "analytics"),
    ("collector",   "analytics"),
    ("beacon",      "analytics"),
    ("insights",    "analytics"),
    ("measurement", "analytics"),
    # Advertising
    ("adserver",    "advertising"),
    ("advertising", "advertising"),
    ("targeting",   "advertising"),
    ("pixels",      "advertising"),
    # Feedback / surveys
    ("feedback",    "feedback"),
    ("improving",   "feedback"),
    ("improvement", "feedback"),
    ("survey",      "feedback"),
    ("surveys",     "feedback"),
    ("satisfaction", "feedback"),
]

# Short keywords that could cause false positives as substrings (e.g. "ad" in
# "adobe", "log" in "blog"). These are only matched as exact, whole labels
# after splitting on dots, hyphens, and underscores.
_EXACT_KEYWORDS: dict[str, str] = {
    # Telemetry
    "crash":   "telemetry",
    "metric":  "telemetry",
    "perf":    "telemetry",
    "logs":    "telemetry",
    "log":     "telemetry",
    "usage":   "telemetry",
    "report":  "telemetry",
    "reports": "telemetry",
    "ping":    "telemetry",
    # Analytics
    "stats":   "analytics",
    "stat":    "analytics",
    "events":  "analytics",
    "event":   "analytics",
    "data":    "analytics",
    # Advertising
    "ads":     "advertising",
    "ad":      "advertising",
    "pixel":   "advertising",
    "rtb":     "advertising",
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
    Infer a tracker category from keywords in the domain name.

    Uses two matching strategies:
    1. Substring match — longer, unambiguous keywords (e.g. "telemetry",
       "analytics", "advertising") are matched anywhere in the full domain.
    2. Exact label match — short, ambiguous keywords (e.g. "ad", "log", "data")
       are only matched as whole labels after splitting the domain on dots,
       hyphens, and underscores.

    e.g. "telemetry.nvidia.com"          → "telemetry"  (substring)
         "app-analytics-services.com"    → "analytics"  (substring)
         "telemetrydeck.com"             → "telemetry"  (substring)
         "crash-reports.example.com"     → "telemetry"  (exact, "crash")
         "pixel.ads.example.com"         → "advertising" (exact, "ads")
         "feedbackws.icloud.com"         → "feedback"   (substring)

    Returns None if no keyword matches.
    """
    lower = domain.rstrip(".").lower()

    # Substring match for long, unambiguous keywords
    for keyword, category in _SUBSTRING_KEYWORDS:
        if keyword in lower:
            return category

    # Exact label match for short, ambiguous keywords
    labels = lower.replace("-", ".").replace("_", ".").split(".")
    for label in labels:
        if label in _EXACT_KEYWORDS:
            return _EXACT_KEYWORDS[label]

    return None
