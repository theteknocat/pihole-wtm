"""
Session dependency for FastAPI route protection.

Use `require_session` as a dependency on any route that needs authentication.
Returns the active Session object or raises 401.
"""

from fastapi import Cookie, HTTPException

from app.services.auth.session_store import Session, session_store

SESSION_COOKIE = "pihole_wtm_session"


async def require_session(
    pihole_wtm_session: str | None = Cookie(default=None),
) -> Session:
    """FastAPI dependency that enforces an active session."""
    if pihole_wtm_session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = session_store.get(pihole_wtm_session)
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired")

    return session
