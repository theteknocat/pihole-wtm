import pytest

from app.services.heuristic import extract_category, extract_company_name

# ---------------------------------------------------------------------------
# extract_company_name()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain, expected", [
    ("telemetry.nvidia.com",    "Nvidia"),
    ("analytics.google.com",   "Google"),
    ("example.com",            "Example"),
    ("sub.sub.example.co",     "Example"),
])
def test_extract_company_name_returns_capitalised_second_level_label(domain: str, expected: str) -> None:
    assert extract_company_name(domain) == expected


def test_extract_company_name_returns_none_for_single_label() -> None:
    assert extract_company_name("localhost") is None


def test_extract_company_name_returns_none_for_single_char_label() -> None:
    # e.g. "a.com" — "a" is too short to be meaningful
    assert extract_company_name("a.com") is None


def test_extract_company_name_strips_trailing_dot() -> None:
    assert extract_company_name("telemetry.nvidia.com.") == "Nvidia"


# ---------------------------------------------------------------------------
# extract_category() — substring matches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain, expected", [
    ("telemetry.nvidia.com",            "telemetry"),
    ("diagnostics.apple.com",           "telemetry"),
    ("metrics.example.com",             "telemetry"),
    ("performance.example.com",         "telemetry"),
    ("analytics.google.com",           "analytics"),
    ("app-analytics-services.com",     "analytics"),
    ("telemetrydeck.com",              "telemetry"),   # substring inside single label
    ("tracking.example.com",           "analytics"),
    ("beacon.example.com",             "analytics"),
    ("insights.example.com",           "analytics"),
    ("adserver.example.com",           "advertising"),
    ("advertising.example.com",        "advertising"),
    ("targeting.example.com",          "advertising"),
    ("feedback.example.com",           "feedback"),
    ("feedbackws.icloud.com",          "feedback"),    # substring inside label
    ("survey.example.com",             "feedback"),
])
def test_extract_category_substring_matches(domain: str, expected: str) -> None:
    assert extract_category(domain) == expected


# ---------------------------------------------------------------------------
# extract_category() — exact label matches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain, expected", [
    ("crash-reports.example.com",  "telemetry"),    # "crash" exact label
    ("app-log.example.com",        "telemetry"),    # "log" exact label
    ("usage.example.com",          "telemetry"),    # "usage" exact label
    ("ping.example.com",           "telemetry"),    # "ping" exact label
    ("stats.example.com",          "analytics"),    # "stats" exact label
    ("pixel.ads.example.com",      "advertising"),  # "pixel" exact label (first match)
    ("rtb.example.com",            "advertising"),  # "rtb" exact label
    ("ad.example.com",             "advertising"),  # "ad" exact label
])
def test_extract_category_exact_label_matches(domain: str, expected: str) -> None:
    assert extract_category(domain) == expected


# ---------------------------------------------------------------------------
# extract_category() — should NOT match (false-positive guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("domain", [
    "adobe.com",        # contains "ad" but not as a whole label
    "blog.example.com", # contains "log" but not as a whole label
    "example.com",      # no keywords at all
    "cdn.example.com",  # generic CDN domain, no keyword
])
def test_extract_category_no_false_positives(domain: str) -> None:
    assert extract_category(domain) is None


# ---------------------------------------------------------------------------
# extract_category() — edge cases
# ---------------------------------------------------------------------------

def test_extract_category_is_case_insensitive() -> None:
    assert extract_category("TELEMETRY.NVIDIA.COM") == "telemetry"


def test_extract_category_strips_trailing_dot() -> None:
    assert extract_category("telemetry.nvidia.com.") == "telemetry"


def test_extract_category_returns_none_for_plain_domain() -> None:
    assert extract_category("example.com") is None
