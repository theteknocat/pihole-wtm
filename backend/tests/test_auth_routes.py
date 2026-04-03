"""
Tests for auth routes (app/routers/auth.py).

Uses the `client` fixture from conftest.py for HTTP calls.

External dependencies are mocked:
- httpx.AsyncClient   — Pi-hole API calls (check-url, login)
- start_sync_from_session / stop_session_sync — sync manager side effects
- get_pihole_url_from_env — env-configured Pi-hole URL
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.services.auth.middleware import SESSION_COOKIE
from app.services.auth.session_store import session_store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_httpx(status_code: int, json_body: dict) -> MagicMock:
    """Return a mock httpx.AsyncClient whose requests return the given response."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=response)
    mock_client.post = AsyncMock(return_value=response)
    mock_client.delete = AsyncMock(return_value=response)
    return mock_client


def _mock_httpx_error() -> MagicMock:
    """Return a mock httpx.AsyncClient that raises a connection error."""
    import httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    return mock_client


@pytest.fixture(autouse=True)
def clear_session_store():
    """Wipe the session_store singleton and suppress the real env URL for every test.
    Individual tests that want an env URL patch it explicitly."""
    session_store.clear()
    with patch("app.routers.auth.get_pihole_url_from_env", return_value=None):
        yield
    session_store.clear()


# ---------------------------------------------------------------------------
# GET /api/auth/status
# ---------------------------------------------------------------------------

async def test_auth_status_unauthenticated(client: AsyncClient) -> None:
    res = await client.get("/api/auth/status")
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is False
    assert body["pihole_url"] is None


async def test_auth_status_authenticated(client: AsyncClient) -> None:
    session = session_store.create("http://pihole.local", "secret")
    client.cookies.set(SESSION_COOKIE, session.session_id)
    res = await client.get("/api/auth/status")
    client.cookies.clear()
    body = res.json()
    assert body["authenticated"] is True
    assert body["pihole_url"] == "http://pihole.local"


async def test_auth_status_invalid_cookie(client: AsyncClient) -> None:
    client.cookies.set(SESSION_COOKIE, "not-a-real-session")
    res = await client.get("/api/auth/status")
    client.cookies.clear()
    body = res.json()
    assert body["authenticated"] is False


async def test_auth_status_reflects_env_url(client: AsyncClient) -> None:
    with patch("app.routers.auth.get_pihole_url_from_env", return_value="http://env-pihole.local"):
        res = await client.get("/api/auth/status")
    body = res.json()
    assert body["pihole_url"] == "http://env-pihole.local"
    assert body["pihole_url_from_env"] is True


# ---------------------------------------------------------------------------
# GET /api/auth/check-url
# ---------------------------------------------------------------------------

async def test_check_url_no_url_configured(client: AsyncClient) -> None:
    # autouse fixture already suppresses env URL
    res = await client.get("/api/auth/check-url")
    body = res.json()
    assert body["reachable"] is False
    assert "No Pi-hole URL configured" in body["error"]


async def test_check_url_reachable(client: AsyncClient) -> None:
    mock = _mock_httpx(200, {"version": {"core": {"local": {"version": "6.0"}}}})
    with patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.get("/api/auth/check-url", params={"url": "http://pihole.local"})
    body = res.json()
    assert body["reachable"] is True
    assert body["version"] == "6.0"


async def test_check_url_returns_reachable_on_401(client: AsyncClient) -> None:
    # 401 means Pi-hole is there but needs auth — still reachable
    mock = _mock_httpx(401, {})
    with patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.get("/api/auth/check-url", params={"url": "http://pihole.local"})
    body = res.json()
    assert body["reachable"] is True
    assert body["version"] is None


async def test_check_url_unreachable(client: AsyncClient) -> None:
    mock = _mock_httpx_error()
    with patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.get("/api/auth/check-url", params={"url": "http://pihole.local"})
    body = res.json()
    assert body["reachable"] is False


async def test_check_url_non_200_non_401(client: AsyncClient) -> None:
    mock = _mock_httpx(503, {})
    with patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.get("/api/auth/check-url", params={"url": "http://pihole.local"})
    body = res.json()
    assert body["reachable"] is False
    assert "503" in body["error"]


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

async def test_login_no_url_returns_400(client: AsyncClient) -> None:
    with patch("app.routers.auth.get_pihole_url_from_env", return_value=None):
        res = await client.post("/api/auth/login", json={"password": "secret"})
    assert res.status_code == 400


async def test_login_unreachable_pihole_returns_502(client: AsyncClient) -> None:
    mock = _mock_httpx_error()
    with patch("app.routers.auth.get_pihole_url_from_env", return_value=None), \
         patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.post("/api/auth/login", json={"password": "secret", "pihole_url": "http://pihole.local"})
    assert res.status_code == 502


async def test_login_wrong_password_returns_401(client: AsyncClient) -> None:
    # Pi-hole returns 200 but no sid → invalid password
    mock = _mock_httpx(200, {"session": {}})
    with patch("app.routers.auth.get_pihole_url_from_env", return_value=None), \
         patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.post("/api/auth/login", json={"password": "wrong", "pihole_url": "http://pihole.local"})
    assert res.status_code == 401
    assert res.json()["status"] == "Invalid password"


async def test_login_success_sets_cookie_and_creates_session(client: AsyncClient) -> None:
    mock = _mock_httpx(200, {"session": {"sid": "pihole-sid-abc"}})
    with patch("app.routers.auth.get_pihole_url_from_env", return_value=None), \
         patch("app.routers.auth.httpx.AsyncClient", return_value=mock), \
         patch("app.services.sync_manager.start_sync_from_session", new_callable=AsyncMock):
        res = await client.post("/api/auth/login", json={"password": "correct", "pihole_url": "http://pihole.local"})

    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert SESSION_COOKIE in res.cookies
    # Session should now exist in the store
    session = session_store.get_active()
    assert session is not None
    assert session.pihole_url == "http://pihole.local"


async def test_login_pihole_non_200_returns_502(client: AsyncClient) -> None:
    mock = _mock_httpx(500, {})
    with patch("app.routers.auth.get_pihole_url_from_env", return_value=None), \
         patch("app.routers.auth.httpx.AsyncClient", return_value=mock):
        res = await client.post("/api/auth/login", json={"password": "secret", "pihole_url": "http://pihole.local"})
    assert res.status_code == 502


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

async def test_logout_clears_session_and_cookie(client: AsyncClient) -> None:
    session = session_store.create("http://pihole.local", "secret")
    client.cookies.set(SESSION_COOKIE, session.session_id)
    with patch("app.services.sync_manager.stop_session_sync", new_callable=AsyncMock):
        res = await client.post("/api/auth/logout")
    client.cookies.clear()
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert session_store.get_active() is None


async def test_logout_without_cookie_is_safe(client: AsyncClient) -> None:
    with patch("app.services.sync_manager.stop_session_sync", new_callable=AsyncMock):
        res = await client.post("/api/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
