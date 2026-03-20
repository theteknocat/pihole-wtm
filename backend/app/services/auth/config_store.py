"""
Pi-hole URL resolver.

Resolves the Pi-hole URL using a two-tier system:
  Tier 1: PIHOLE_API_URL environment variable (takes priority if set).
  Tier 2: user_config table in the local database (saved via login page).
"""

import os


def is_url_from_env() -> bool:
    """Return True if the Pi-hole URL is set via environment variable."""
    return bool(os.environ.get("PIHOLE_API_URL"))


async def get_pihole_url() -> str | None:
    """
    Resolve the Pi-hole URL using the two-tier system.

    Tier 1: PIHOLE_API_URL environment variable.
    Tier 2: user_config table in the local database.
    """
    env_url = os.environ.get("PIHOLE_API_URL")
    if env_url:
        return env_url

    # Tier 2 — database config
    from app.main import db
    return await db.get_config("pihole_url")


async def save_pihole_url(url: str) -> None:
    """Save the Pi-hole URL to the database config."""
    from app.main import db
    await db.set_config("pihole_url", url)
