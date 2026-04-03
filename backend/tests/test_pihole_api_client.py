"""
Tests for PiholeApiClient (app/services/pihole/api_client.py).

Rather than patching httpx.AsyncClient at the module level, we create
a real PiholeApiClient and swap out its internal _client attribute with
a mock after construction. This keeps the tests readable and avoids
fighting with the constructor.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.pihole.api_client import (
    PiholeApiClient,
    PiholeAuthError,
    PiholeConnectionError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(status_code: int, json_body: dict) -> MagicMock:
    """A mock httpx response."""
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_body
    if status_code >= 400:
        res.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=res,
        )
    else:
        res.raise_for_status = MagicMock()
    return res


def _auth_ok() -> MagicMock:
    return _response(200, {"session": {"sid": "test-sid-123"}})


def _auth_bad_password() -> MagicMock:
    return _response(200, {"session": {}})  # 200 but no sid = wrong password


@pytest.fixture
def pihole() -> PiholeApiClient:
    """A PiholeApiClient with its HTTP transport replaced by a mock."""
    c = PiholeApiClient("http://pihole.local", "secret")
    mock_http = AsyncMock()
    mock_http.aclose = AsyncMock()
    c._client = mock_http
    return c


# ---------------------------------------------------------------------------
# _authenticate()
# ---------------------------------------------------------------------------

async def test_authenticate_sets_sid_on_success(pihole: PiholeApiClient) -> None:
    pihole._client.post.return_value = _auth_ok()
    await pihole._authenticate()
    assert pihole._sid == "test-sid-123"


async def test_authenticate_raises_auth_error_on_bad_password(pihole: PiholeApiClient) -> None:
    pihole._client.post.return_value = _auth_bad_password()
    with pytest.raises(PiholeAuthError):
        await pihole._authenticate()


async def test_authenticate_raises_connection_error_on_http_failure(pihole: PiholeApiClient) -> None:
    pihole._client.post.side_effect = httpx.ConnectError("refused")
    with pytest.raises(PiholeConnectionError):
        await pihole._authenticate()


# ---------------------------------------------------------------------------
# _get()
# ---------------------------------------------------------------------------

async def test_get_authenticates_if_no_sid(pihole: PiholeApiClient) -> None:
    pihole._client.post.return_value = _auth_ok()
    pihole._client.get.return_value = _response(200, {"result": "ok"})

    await pihole._get("/api/test")

    pihole._client.post.assert_called_once()  # auth happened
    pihole._client.get.assert_called_once()


async def test_get_skips_auth_if_sid_already_set(pihole: PiholeApiClient) -> None:
    pihole._sid = "existing-sid"
    pihole._client.get.return_value = _response(200, {"result": "ok"})

    await pihole._get("/api/test")

    pihole._client.post.assert_not_called()  # no re-auth


async def test_get_sends_sid_header(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(200, {})

    await pihole._get("/api/test")

    call_kwargs = pihole._client.get.call_args
    assert call_kwargs.kwargs["headers"]["X-FTL-SID"] == "my-sid"


async def test_get_reauthenticates_on_401(pihole: PiholeApiClient) -> None:
    pihole._sid = "expired-sid"
    expired = _response(401, {})
    expired.raise_for_status = MagicMock()  # 401 is handled before raise_for_status
    fresh = _response(200, {"result": "ok"})

    pihole._client.get.side_effect = [expired, fresh]
    pihole._client.post.return_value = _auth_ok()

    result = await pihole._get("/api/test")

    assert pihole._client.post.call_count == 1   # re-authenticated once
    assert pihole._client.get.call_count == 2    # original + retry
    assert result == {"result": "ok"}


async def test_get_raises_connection_error_on_http_failure(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.side_effect = httpx.ConnectError("refused")
    with pytest.raises(PiholeConnectionError):
        await pihole._get("/api/test")


async def test_get_raises_auth_error_on_non_401_http_error(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(403, {})
    with pytest.raises(PiholeAuthError):
        await pihole._get("/api/test")


# ---------------------------------------------------------------------------
# Double-checked locking — concurrent requests only authenticate once
# ---------------------------------------------------------------------------

async def test_concurrent_requests_authenticate_only_once(pihole: PiholeApiClient) -> None:
    pihole._client.post.return_value = _auth_ok()
    pihole._client.get.return_value = _response(200, {"queries": [], "cursor": None})

    # Fire two requests simultaneously with no sid set
    await asyncio.gather(
        pihole._get("/api/queries"),
        pihole._get("/api/queries"),
    )

    assert pihole._client.post.call_count == 1  # only one auth despite two concurrent calls


# ---------------------------------------------------------------------------
# get_summary()
# ---------------------------------------------------------------------------

async def test_get_summary_parses_response(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(200, {
        "queries": {
            "total": 5000,
            "blocked": 500,
            "percent_blocked": 10.0,
            "unique_domains": 300,
            "cached": 200,
        },
        "gravity": {"domains_being_blocked": 99000},
    })

    summary = await pihole.get_summary()

    assert summary.total_queries == 5000
    assert summary.blocked_queries == 500
    assert summary.blocked_percent == 10.0
    assert summary.unique_domains == 300
    assert summary.queries_cached == 200
    assert summary.domains_on_blocklist == 99000


# ---------------------------------------------------------------------------
# get_queries()
# ---------------------------------------------------------------------------

def _raw_query_payload(id: int, domain: str, status: str = "FORWARDED") -> dict:
    return {
        "id": id,
        "time": 1700000000.0 + id,
        "domain": domain,
        "client": {"ip": "192.168.1.1"},
        "status": status,
        "type": "A",
        "reply": {"type": "IP", "time": 0.001},
        "upstream": "8.8.8.8",
        "list_id": None,
    }


async def test_get_queries_maps_fields_correctly(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(200, {
        "queries": [_raw_query_payload(42, "example.com", "GRAVITY")],
        "cursor": None,
    })

    queries, next_cursor = await pihole.get_queries()

    assert len(queries) == 1
    q = queries[0]
    assert q.id == 42
    assert q.domain == "example.com"
    assert q.client == "192.168.1.1"
    assert q.status == "GRAVITY"
    assert q.status_label == "blocked (gravity)"
    assert q.query_type == "A"
    assert next_cursor is None


async def test_get_queries_returns_cursor_when_more_pages(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(200, {
        "queries": [_raw_query_payload(1, "a.com"), _raw_query_payload(2, "b.com")],
        "cursor": 99,
    })

    _, next_cursor = await pihole.get_queries(limit=2)
    assert next_cursor == 99


async def test_get_queries_sends_cursor_param(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(200, {"queries": [], "cursor": None})

    await pihole.get_queries(cursor=50, from_ts=1700000000)

    params = pihole._client.get.call_args.kwargs["params"]
    assert params["cursor"] == 50
    assert params["from"] == 1700000000


async def test_get_queries_unknown_status_falls_back_to_lowercase(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    payload = _raw_query_payload(1, "example.com")
    payload["status"] = "SOME_NEW_STATUS"
    pihole._client.get.return_value = _response(200, {"queries": [payload], "cursor": None})

    queries, _ = await pihole.get_queries()
    assert queries[0].status_label == "some new status"


# ---------------------------------------------------------------------------
# test_connection()
# ---------------------------------------------------------------------------

async def test_test_connection_returns_version(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.get.return_value = _response(200, {
        "version": {"core": {"local": {"version": "6.0.1"}}}
    })

    result = await pihole.test_connection()

    assert result["connected"] is True
    assert result["version"] == "6.0.1"


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------

async def test_close_deletes_pihole_session(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.delete = AsyncMock(return_value=_response(200, {}))

    await pihole.close()

    pihole._client.delete.assert_called_once()
    delete_call = pihole._client.delete.call_args
    assert delete_call.kwargs["headers"]["X-FTL-SID"] == "my-sid"
    pihole._client.aclose.assert_called_once()


async def test_close_skips_delete_if_no_sid(pihole: PiholeApiClient) -> None:
    pihole._client.delete = AsyncMock()

    await pihole.close()

    pihole._client.delete.assert_not_called()
    pihole._client.aclose.assert_called_once()


async def test_close_tolerates_http_error_on_delete(pihole: PiholeApiClient) -> None:
    pihole._sid = "my-sid"
    pihole._client.delete = AsyncMock(side_effect=httpx.ConnectError("gone"))

    await pihole.close()  # should not raise

    pihole._client.aclose.assert_called_once()
