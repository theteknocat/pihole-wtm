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
    timestamp: int
    domain: str
    client: str
    status: int
    status_label: str
    query_type: str
    reply_type: str | None = None
    reply_time: float | None = None
