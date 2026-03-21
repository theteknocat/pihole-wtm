"""
Pi-hole URL resolver.

Returns the Pi-hole URL from the PIHOLE_API_URL environment variable,
or None if not set. When no env var is configured, the URL is provided
by the user at login and held in the session (memory only).
"""

import os


def get_pihole_url_from_env() -> str | None:
    """Return the Pi-hole URL from env var, or None if not set."""
    url = os.environ.get("PIHOLE_API_URL")
    return url if url else None
