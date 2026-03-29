import time

import pytest

from app.services.auth.session_store import SessionStore


@pytest.fixture
def store() -> SessionStore:
    """A fresh SessionStore for each test."""
    return SessionStore()


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------

def test_create_returns_session_with_correct_fields(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    assert session.pihole_url == "http://pihole.local"
    assert session.pihole_password == "secret"
    assert session.session_id  # non-empty


def test_create_replaces_existing_session(store: SessionStore) -> None:
    first = store.create("http://pihole.local", "pass1")
    second = store.create("http://pihole.local", "pass2")
    assert first.session_id != second.session_id
    # The old session_id should no longer resolve
    assert store.get(first.session_id) is None


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

def test_get_returns_session_for_valid_id(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    result = store.get(session.session_id)
    assert result is not None
    assert result.session_id == session.session_id


def test_get_returns_none_for_wrong_id(store: SessionStore) -> None:
    store.create("http://pihole.local", "secret")
    assert store.get("not-a-real-id") is None


def test_get_returns_none_when_no_session(store: SessionStore) -> None:
    assert store.get("anything") is None


def test_get_expires_idle_session(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    # Wind back last_active so the session appears idle
    store._max_idle = 1  # 1-second timeout
    session.last_active = time.time() - 2
    assert store.get(session.session_id) is None


def test_get_touches_last_active(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    before = session.last_active
    time.sleep(0.01)
    store.get(session.session_id)
    assert session.last_active > before


# ---------------------------------------------------------------------------
# get_active()
# ---------------------------------------------------------------------------

def test_get_active_returns_current_session(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    assert store.get_active() is session


def test_get_active_returns_none_when_empty(store: SessionStore) -> None:
    assert store.get_active() is None


def test_get_active_returns_none_for_expired_session(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    store._max_idle = 1
    session.last_active = time.time() - 2
    assert store.get_active() is None


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

def test_delete_removes_session_and_returns_true(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    assert store.delete(session.session_id) is True
    assert store.get(session.session_id) is None


def test_delete_returns_false_for_wrong_id(store: SessionStore) -> None:
    store.create("http://pihole.local", "secret")
    assert store.delete("wrong-id") is False


def test_delete_returns_false_when_empty(store: SessionStore) -> None:
    assert store.delete("anything") is False


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

def test_clear_removes_active_session(store: SessionStore) -> None:
    session = store.create("http://pihole.local", "secret")
    store.clear()
    assert store.get(session.session_id) is None
    assert store.get_active() is None


def test_clear_is_safe_when_already_empty(store: SessionStore) -> None:
    store.clear()  # should not raise
    assert store.get_active() is None
