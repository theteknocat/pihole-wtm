"""
Manages the Pi-hole sync service lifecycle.

Extracted from main.py so that auth routes can import start/stop
without a circular dependency (main imports auth_router, auth
imports sync functions).

The sync service can be started from two sources:
  - Environment variables (PIHOLE_API_URL + PIHOLE_API_PASSWORD) — runs
    continuously from boot, independent of user sessions.
  - Login session — runs while a user is logged in, stops on logout or
    session expiry.

When started from env vars, login/logout do not affect the sync service.
"""

import asyncio
import logging
from enum import Enum
from typing import Any

from app.services.auth.session_store import Session
from app.services.pihole.api_client import PiholeApiClient
from app.services.sync import run_sync_loop

logger = logging.getLogger(__name__)


class SyncSource(Enum):
    """How the sync service was started."""
    ENV = "env"          # From environment variables (persistent)
    SESSION = "session"  # From a login session (transient)


pihole: PiholeApiClient | None = None
sync_task: asyncio.Task[None] | None = None
sync_source: SyncSource | None = None
_wake_event: asyncio.Event = asyncio.Event()


async def start_sync_from_env(sources: list[Any], db: Any) -> bool:
    """
    Start sync using env var credentials if both URL and password are set.
    Returns True if sync was started, False if credentials are missing.
    """
    from app.config import settings
    if not settings.pihole_api_url or not settings.pihole_api_password:
        return False

    global pihole, sync_task, sync_source
    await _stop()

    pihole = PiholeApiClient(
        base_url=settings.pihole_api_url,
        password=settings.pihole_api_password,
    )
    sync_task = asyncio.create_task(run_sync_loop(pihole, sources, db, _wake_event))
    sync_source = SyncSource.ENV
    logger.info("Sync service started from env vars for %s", settings.pihole_api_url)
    return True


async def start_sync_from_session(session: Session, sources: list[Any], db: Any) -> None:
    """
    Start sync using login session credentials.
    No-op if sync is already running from env vars.
    """
    global pihole, sync_task, sync_source

    # Don't replace env-var-driven sync with session-driven sync
    if sync_source == SyncSource.ENV:
        logger.debug("Sync already running from env vars — skipping session start")
        return

    await _stop()

    pihole = PiholeApiClient(
        base_url=session.pihole_url,
        password=session.pihole_password,
    )
    sync_task = asyncio.create_task(run_sync_loop(pihole, sources, db, _wake_event))
    sync_source = SyncSource.SESSION
    logger.info("Sync service started from session for %s", session.pihole_url)


def trigger_sync() -> None:
    """Signal the sync loop to wake up and run immediately."""
    _wake_event.set()


async def stop_session_sync() -> None:
    """Stop sync only if it was started from a session (not env vars)."""
    if sync_source == SyncSource.ENV:
        logger.debug("Sync running from env vars — not stopping on logout")
        return
    await _stop()


async def stop_sync_service() -> None:
    """Unconditionally stop the sync service (used during shutdown)."""
    await _stop()


async def _stop() -> None:
    """Internal: cancel the sync task and close the Pi-hole client."""
    global pihole, sync_task, sync_source

    if sync_task is not None:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
        sync_task = None

    if pihole is not None:
        await pihole.close()
        pihole = None
        logger.info("Sync service stopped")

    sync_source = None
