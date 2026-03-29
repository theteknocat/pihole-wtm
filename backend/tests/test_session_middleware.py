"""
Tests for the require_session FastAPI dependency (app/services/auth/middleware.py).

require_session is a plain async function, so we call it directly rather
than routing HTTP requests through it — keeps these tests fast and focused.
"""

import pytest
from fastapi import HTTPException

from app.services.auth.middleware import require_session
from app.services.auth.session_store import session_store


@pytest.fixture(autouse=True)
def clear_sessions():
    session_store.clear()
    yield
    session_store.clear()


async def test_missing_cookie_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await require_session(pihole_wtm_session=None)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Not authenticated"


async def test_invalid_session_id_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await require_session(pihole_wtm_session="not-a-real-id")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Session expired"


async def test_valid_session_returns_session_object() -> None:
    session = session_store.create("http://pihole.local", "secret")
    result = await require_session(pihole_wtm_session=session.session_id)
    assert result.session_id == session.session_id
    assert result.pihole_url == "http://pihole.local"
