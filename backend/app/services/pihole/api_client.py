import asyncio
import logging
from typing import Any

import httpx

from app.models.pihole import RawQuery, SummaryStats

logger = logging.getLogger(__name__)

# Pi-hole v6 status strings that represent a blocked query
BLOCKED_STATUSES: frozenset[str] = frozenset({
    "GRAVITY",
    "REGEX_PI",
    "DENYLIST",
    "GRAVITY_CNAME",
    "REGEX_CNAME",
    "DENYLIST_CNAME",
    "RATE_LIMITED",
})

# Pi-hole v6 query status strings → human-readable labels
QUERY_STATUS_LABELS: dict[str, str] = {
    "FORWARDED": "allowed (forwarded)",
    "CACHE": "allowed (cached)",
    "CACHE_STALE": "allowed (cache stale)",
    "SPECIAL_DOMAIN": "allowed (special domain)",
    "GRAVITY": "blocked (gravity)",
    "REGEX_PI": "blocked (regex)",
    "DENYLIST": "blocked (denylist)",
    "GRAVITY_CNAME": "blocked (CNAME gravity)",
    "REGEX_CNAME": "blocked (CNAME regex)",
    "DENYLIST_CNAME": "blocked (CNAME denylist)",
    "RATE_LIMITED": "blocked (rate limited)",
    "RETRIED": "retried",
    "RETRIED_DNSSEC": "retried (DNSSEC)",
    "IN_PROGRESS": "in progress",
    "DBBUSY": "db busy",
}


class PiholeAuthError(Exception):
    pass


class PiholeConnectionError(Exception):
    pass


class PiholeApiClient:
    def __init__(self, base_url: str, password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._password = password
        self._sid: str | None = None
        self._client = httpx.AsyncClient(timeout=10.0)
        self._auth_lock = asyncio.Lock()

    async def _authenticate(self) -> None:
        """Obtain a session token from the Pi-hole v6 API."""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/auth",
                json={"password": self._password},
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise PiholeConnectionError(f"Failed to connect to Pi-hole: {e}") from e

        data = response.json()
        sid = data.get("session", {}).get("sid")
        if not sid:
            raise PiholeAuthError("Authentication failed — check your Pi-hole password")

        self._sid = sid
        logger.info("Authenticated with Pi-hole at %s", self._base_url)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make an authenticated GET request, re-authenticating if the session has expired."""
        if self._sid is None:
            async with self._auth_lock:
                if self._sid is None:  # re-check after acquiring lock
                    await self._authenticate()

        sid = self._sid
        if sid is None:
            raise PiholeAuthError("Authentication completed but session ID was not set")

        try:
            response = await self._client.get(
                f"{self._base_url}{path}",
                params=params,
                headers={"X-FTL-SID": sid},
            )
        except httpx.HTTPError as e:
            raise PiholeConnectionError(f"Pi-hole request failed: {e}") from e

        if response.status_code == 401:
            # Session expired — re-authenticate and retry once
            logger.debug("Session expired, re-authenticating")
            self._sid = None
            async with self._auth_lock:
                if self._sid is None:
                    await self._authenticate()
            retry_sid = self._sid or ""
            try:
                response = await self._client.get(
                    f"{self._base_url}{path}",
                    params=params,
                    headers={"X-FTL-SID": retry_sid},
                )
            except httpx.HTTPError as e:
                raise PiholeConnectionError(f"Pi-hole request failed: {e}") from e

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise PiholeAuthError(
                f"Pi-hole API returned {response.status_code} — check credentials"
            ) from e

        return response.json()

    async def get_summary(self) -> SummaryStats:
        """Fetch summary statistics from Pi-hole."""
        data = await self._get("/api/stats/summary")
        queries = data.get("queries", {})
        return SummaryStats(
            total_queries=queries.get("total", 0),
            blocked_queries=queries.get("blocked", 0),
            blocked_percent=queries.get("percent_blocked", 0.0),
            unique_domains=queries.get("unique_domains", 0),
            queries_cached=queries.get("cached", 0),
            domains_on_blocklist=data.get("gravity", {}).get("domains_being_blocked", 0),
        )

    async def get_queries(
        self,
        limit: int = 100,
        cursor: int | None = None,
        from_ts: int | None = None,
    ) -> tuple[list[RawQuery], int | None]:
        """
        Fetch recent DNS queries from Pi-hole.

        Returns a tuple of (queries, next_cursor).
        next_cursor is None when there are no more results.
        """
        params: dict[str, Any] = {"length": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if from_ts is not None:
            params["from"] = from_ts

        data = await self._get("/api/queries", params=params)

        queries = []
        for q in data.get("queries", []):
            status = q.get("status", "UNKNOWN")
            queries.append(
                RawQuery(
                    id=q.get("id", 0),
                    timestamp=q.get("time", 0),
                    domain=q.get("domain", ""),
                    client=q.get("client", {}).get("ip", ""),
                    status=status,
                    status_label=QUERY_STATUS_LABELS.get(status, status.lower().replace("_", " ")),
                    query_type=q.get("type", ""),
                    reply_type=q.get("reply", {}).get("type"),
                    reply_time=q.get("reply", {}).get("time"),
                    upstream=q.get("upstream"),
                    list_id=q.get("list_id"),
                )
            )

        next_cursor = data.get("cursor")
        return queries, next_cursor

    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity and authentication, returning version info on success."""
        data = await self._get("/api/info/version")
        return {
            "connected": True,
            "version": data.get("version", {}).get("core", {}).get("local", {}).get("version"),
        }

    async def close(self) -> None:
        """Delete the Pi-hole session and close the HTTP client."""
        if self._sid:
            try:
                await self._client.delete(
                    f"{self._base_url}/api/auth",
                    headers={"X-FTL-SID": self._sid},
                )
            except httpx.HTTPError:
                pass
        await self._client.aclose()
