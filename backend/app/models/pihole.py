from pydantic import BaseModel


class SummaryStats(BaseModel):
    total_queries: int
    blocked_queries: int
    blocked_percent: float
    unique_domains: int
    queries_cached: int
    domains_on_blocklist: int


class RawQuery(BaseModel):
    id: int
    timestamp: float
    domain: str
    client: str
    status: str
    status_label: str
    query_type: str
    reply_type: str | None = None
    reply_time: float | None = None


class EnrichedQuery(BaseModel):
    # Core query fields
    id: int
    timestamp: float
    domain: str
    client: str
    status: str
    status_label: str
    query_type: str
    reply_type: str | None = None
    reply_time: float | None = None
    # Tracker enrichment — None if domain not found in TrackerDB
    tracker_name: str | None = None
    category: str | None = None
    company_name: str | None = None
    company_country: str | None = None
