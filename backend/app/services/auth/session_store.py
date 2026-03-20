"""
In-memory session store for pihole-wtm authentication.

Sessions are keyed by a random UUID and hold the Pi-hole credentials
needed for the sync service. All session data lives only in memory —
nothing is written to disk. Sessions are lost on server restart, which
is acceptable for a local dashboard.
"""

import secrets
import time
from dataclasses import dataclass, field


@dataclass
class Session:
    """A single authenticated session."""

    session_id: str
    pihole_url: str
    pihole_password: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        """Update last-active timestamp."""
        self.last_active = time.time()


class SessionStore:
    """In-memory session store. Only one active session at a time."""

    def __init__(self, max_idle_seconds: int = 86400) -> None:
        self._session: Session | None = None
        self._max_idle = max_idle_seconds

    def create(self, pihole_url: str, pihole_password: str) -> Session:
        """Create a new session, replacing any existing one."""
        session = Session(
            session_id=secrets.token_urlsafe(32),
            pihole_url=pihole_url,
            pihole_password=pihole_password,
        )
        self._session = session
        return session

    def get(self, session_id: str) -> Session | None:
        """Look up a session by ID. Returns None if expired or not found."""
        if self._session is None or self._session.session_id != session_id:
            return None
        if time.time() - self._session.last_active > self._max_idle:
            self._session = None
            return None
        self._session.touch()
        return self._session

    def get_active(self) -> Session | None:
        """Return the current active session, if any."""
        if self._session is None:
            return None
        if time.time() - self._session.last_active > self._max_idle:
            self._session = None
            return None
        return self._session

    def delete(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        if self._session is not None and self._session.session_id == session_id:
            self._session = None
            return True
        return False

    def clear(self) -> None:
        """Remove all sessions."""
        self._session = None


# Global singleton — imported by auth routes and middleware
session_store = SessionStore()
