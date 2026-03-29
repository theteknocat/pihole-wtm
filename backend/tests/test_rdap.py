"""
Tests for RDAP company lookup (app/services/rdap.py).

httpx is mocked throughout — no real network calls are made.
The module-level LRU cache is cleared before each test so results
from one test don't bleed into another.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.rdap as rdap_module
from app.services.rdap import lookup_company


@pytest.fixture(autouse=True)
def clear_rdap_cache():
    rdap_module._cache.clear()
    yield
    rdap_module._cache.clear()


def _mock_httpx(status_code: int, json_body: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=response)
    return mock_client


def _rdap_response(org_name: str) -> dict:
    """Minimal RDAP response with a registrant entity."""
    return {
        "entities": [{
            "roles": ["registrant"],
            "vcardArray": ["vcard", [
                ["version", {}, "text", "4.0"],
                ["fn", {}, "text", org_name],
            ]],
        }]
    }


# ---------------------------------------------------------------------------
# lookup_company() — successful lookups
# ---------------------------------------------------------------------------

async def test_lookup_company_returns_org_name() -> None:
    mock = _mock_httpx(200, _rdap_response("Nvidia Corporation"))
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        result = await lookup_company("telemetry.nvidia.com")
    assert result == "Nvidia Corporation"


async def test_lookup_company_uses_registered_domain_not_subdomain() -> None:
    """Subdomains must be stripped — RDAP only accepts registered domains."""
    mock = _mock_httpx(200, _rdap_response("Example Corp"))
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        await lookup_company("deep.sub.example.com")
    # Verify the request was made for the registered domain
    called_url = mock.get.call_args[0][0]
    assert called_url.endswith("/domain/example.com")


# ---------------------------------------------------------------------------
# lookup_company() — privacy proxy detection
# ---------------------------------------------------------------------------

async def test_lookup_company_returns_none_for_privacy_proxy() -> None:
    mock = _mock_httpx(200, _rdap_response("Domains By Proxy, LLC"))
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        result = await lookup_company("example.com")
    assert result is None


async def test_lookup_company_returns_none_for_redacted() -> None:
    mock = _mock_httpx(200, _rdap_response("REDACTED FOR PRIVACY"))
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        result = await lookup_company("example.com")
    assert result is None


# ---------------------------------------------------------------------------
# lookup_company() — error handling
# ---------------------------------------------------------------------------

async def test_lookup_company_returns_none_for_non_200() -> None:
    mock = _mock_httpx(404, {})
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        result = await lookup_company("example.com")
    assert result is None


async def test_lookup_company_returns_none_on_network_error() -> None:
    import httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))

    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock_client):
        result = await lookup_company("example.com")
    assert result is None


# ---------------------------------------------------------------------------
# LRU cache behaviour
# ---------------------------------------------------------------------------

async def test_lookup_company_caches_result() -> None:
    mock = _mock_httpx(200, _rdap_response("Example Corp"))
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        first = await lookup_company("example.com")
        second = await lookup_company("example.com")

    assert first == second == "Example Corp"
    # Only one HTTP call despite two lookups
    assert mock.get.call_count == 1


async def test_lookup_company_cache_shared_across_subdomains() -> None:
    """Two subdomains of the same registered domain should only make one request."""
    mock = _mock_httpx(200, _rdap_response("Example Corp"))
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        r1 = await lookup_company("a.example.com")
        r2 = await lookup_company("b.example.com")

    assert r1 == r2 == "Example Corp"
    assert mock.get.call_count == 1


async def test_lookup_company_caches_none_on_failure() -> None:
    """A failed lookup should be cached so we don't hammer a failing endpoint."""
    mock = _mock_httpx(404, {})
    with patch("app.services.rdap.httpx.AsyncClient", return_value=mock):
        await lookup_company("example.com")
        await lookup_company("example.com")

    assert mock.get.call_count == 1
