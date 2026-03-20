"""
Manages the Pi-hole sync service lifecycle.

Extracted from main.py so that auth routes can import start/stop
without a circular dependency (main imports auth_router, auth
imports sync functions).
"""

import asyncio
import logging
from typing import Any

from app.services.auth.session_store import Session
from app.services.pihole.api_client import PiholeApiClient
from app.services.sync import run_sync_loop

logger = logging.getLogger(__name__)

pihole: PiholeApiClient | None = None
sync_task: asyncio.Task | None = None


async def start_sync_service(session: Session, sources: list[Any], db: Any) -> None:
    """Start the Pi-hole sync service using session credentials."""
    global pihole, sync_task

    # Stop any existing sync
    await stop_sync_service()

    pihole = PiholeApiClient(
        base_url=session.pihole_url,
        password=session.pihole_password,
    )
    sync_task = asyncio.create_task(run_sync_loop(pihole, sources, db))
    logger.info("Sync service started for %s", session.pihole_url)


async def stop_sync_service() -> None:
    """Stop the sync service and clean up the Pi-hole client."""
    global pihole, sync_task

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
