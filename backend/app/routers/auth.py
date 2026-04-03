"""
Authentication routes for pihole-wtm.

Login verifies the password against the Pi-hole API. On success,
a session is created and the session ID is set as an HTTP-only cookie.
The Pi-hole password is held in server memory only — never persisted.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.services.auth.config_store import get_pihole_url_from_env
from app.services.auth.middleware import SESSION_COOKIE
from app.services.auth.session_store import session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str
    pihole_url: str | None = None  # Required when no env var is set


class LoginResponse(BaseModel):
    status: str
    pihole_url: str


class AuthStatusResponse(BaseModel):
    authenticated: bool
    pihole_url: str | None = None
    pihole_url_from_env: bool = False


@router.get("/status")
async def auth_status(request: Request) -> AuthStatusResponse:
    """Check if the current request has a valid session."""
    session_id = request.cookies.get(SESSION_COOKIE)
    session = session_store.get(session_id) if session_id else None

    env_url = get_pihole_url_from_env()
    # URL comes from env var, or from the active session if logged in
    url = env_url or (session.pihole_url if session else None)

    return AuthStatusResponse(
        authenticated=session is not None,
        pihole_url=url,
        pihole_url_from_env=env_url is not None,
    )


@router.get("/check-url")
async def check_pihole_url(url: str | None = None) -> dict[str, Any]:
    """
    Check if a Pi-hole URL is reachable. Uses the configured URL if none provided.
    Calls the unauthenticated Pi-hole API info endpoint.
    """
    target_url = url or get_pihole_url_from_env()
    if not target_url:
        return {"reachable": False, "error": "No Pi-hole URL configured"}

    target_url = target_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{target_url}/api/info/version")
            if res.status_code == 200:
                version = (
                    res.json()
                    .get("version", {})
                    .get("core", {})
                    .get("local", {})
                    .get("version")
                )
                return {"reachable": True, "version": version}
            # 401 means Pi-hole is there but requires auth — still reachable
            if res.status_code == 401:
                return {"reachable": True, "version": None}
            return {"reachable": False, "error": f"HTTP {res.status_code}"}
    except httpx.HTTPError as e:
        return {"reachable": False, "error": str(e)}


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    """
    Authenticate using the Pi-hole password.

    On success, creates a server-side session and sets an HTTP-only cookie.
    """
    # Resolve Pi-hole URL: env var takes priority, otherwise use the one from the login form
    url = get_pihole_url_from_env() or (body.pihole_url.rstrip("/") if body.pihole_url else None)

    if not url:
        response.status_code = 400
        return LoginResponse(status="No Pi-hole URL configured", pihole_url="")

    url = url.rstrip("/")

    # Verify credentials against Pi-hole API
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{url}/api/auth",
                json={"password": body.password},
            )
    except httpx.HTTPError as e:
        response.status_code = 502
        return LoginResponse(status=f"Cannot reach Pi-hole: {e}", pihole_url=url)

    if res.status_code != 200:
        response.status_code = 502
        return LoginResponse(
            status=f"Pi-hole returned HTTP {res.status_code}", pihole_url=url
        )

    data = res.json()
    sid = data.get("session", {}).get("sid")
    if not sid:
        response.status_code = 401
        return LoginResponse(
            status="Invalid password", pihole_url=url
        )

    # Invalidate the Pi-hole session we just created for verification —
    # PiholeApiClient will create its own when the sync service starts
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.delete(
                f"{url}/api/auth",
                headers={"X-FTL-SID": sid},
            )
    except httpx.HTTPError:
        pass  # Not critical if cleanup fails

    # Create our session
    session = session_store.create(pihole_url=url, pihole_password=body.password)

    from app.config import settings
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.session_id,
        httponly=True,
        samesite="strict",
        secure=False,  # Local network — no HTTPS typically
        max_age=settings.session_timeout_hours * 3600,
    )

    # Start the sync service with the new session credentials
    # (no-op if already running from env vars)
    from app.main import db, sources
    from app.services.sync_manager import start_sync_from_session
    await start_sync_from_session(session, sources, db)

    logger.info("User authenticated successfully for Pi-hole at %s", url)
    return LoginResponse(status="ok", pihole_url=url)


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    """Delete the current session and clear the cookie."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        session_store.delete(session_id)

    # Stop session-driven sync (no-op if sync is running from env vars)
    from app.services.sync_manager import stop_session_sync
    await stop_session_sync()

    response.delete_cookie(key=SESSION_COOKIE)
    return {"status": "ok"}
