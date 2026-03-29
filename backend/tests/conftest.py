"""
Shared pytest fixtures for pihole-wtm backend tests.

Two core fixtures are provided:

- db     — a fully-initialised in-memory LocalDatabase, torn down after each test.
           Use this for testing database methods directly.

- client — an async HTTP test client for the FastAPI app. The lifespan is
           replaced with a no-op (no tracker sources, no sync service starts),
           main.db is wired to the in-memory test database, and require_session
           is overridden so routes don't need a real session cookie.
           Use this for testing API endpoints.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.main import app
from app.services.auth.middleware import require_session
from app.services.auth.session_store import Session
from app.services.database import LocalDatabase


@pytest.fixture
async def db() -> AsyncGenerator[LocalDatabase, None]:
    """Fully-initialised in-memory database, torn down after each test."""
    database = LocalDatabase(path=":memory:")
    await database.init()
    yield database
    await database.close()


@pytest.fixture
async def client(db: LocalDatabase) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP test client with:
    - No-op lifespan (skips tracker source init and sync startup)
    - main.db wired to the in-memory test database
    - require_session overridden to return a fake authenticated session
    """
    # Wire the test database into the module so routes use it
    main_module.db = db
    main_module.sources = []

    # Bypass auth for all protected routes
    fake_session = Session(
        session_id="test-session-id",
        pihole_url="http://pihole.test",
        pihole_password="testpassword",
    )
    app.dependency_overrides[require_session] = lambda: fake_session

    # Replace the app lifespan so no real startup work runs
    @asynccontextmanager
    async def noop_lifespan(_app: object) -> AsyncGenerator[None, None]:
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.router.lifespan_context = original_lifespan
    app.dependency_overrides.clear()
